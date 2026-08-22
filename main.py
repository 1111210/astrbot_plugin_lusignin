"""
AstrBot 签到插件（Lusignin）

- 面向 aiocqhttp 对话场景
- 收到消息后若包含后台配置的关键词，则自动签到并发送当月月历图片
- 未包含关键词时不拦截事件，交由 AstrBot 默认逻辑继续处理
"""

from __future__ import annotations

import calendar
import glob
import json
import os
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path
from astrbot.api import logger

PLUGIN_NAME = "astrbot_plugin_lusignin"

TZ_BEIJING = timezone(timedelta(hours=8))

DEFAULT_KEYWORDS = ["签到", "打卡"]
DEFAULT_SUCCESS_MESSAGE = "{{user}} 签到成功！你本月已经签到 {{times}} 次。"
DEFAULT_DUPLICATE_MESSAGE = "{{user}} 今天已经签过到啦（重复签到）！你本月已经签到 {{times}} 次。"

# 模块级配置缓存。KeywordFilter 在装饰器阶段被实例化，无法直接拿到插件实例，
# 因此通过这个全局配置在插件 __init__ 时更新，过滤器运行时读取最新关键词。
_CURRENT_CONFIG: dict[str, Any] = {
    "keywords": DEFAULT_KEYWORDS,
    "success_message": DEFAULT_SUCCESS_MESSAGE,
    "duplicate_message": DEFAULT_DUPLICATE_MESSAGE,
}


def _get_keywords() -> list[str]:
    value = _CURRENT_CONFIG.get("keywords", DEFAULT_KEYWORDS)
    if isinstance(value, str):
        # 兼容手工把 list 配成逗号分隔字符串的情况
        parts = value.replace("，", ",").replace("\n", ",").split(",")
        return [p.strip() for p in parts if p.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(k).strip() for k in value if str(k).strip()]
    return list(DEFAULT_KEYWORDS)


def _get_message_text(key: str, default: str) -> str:
    value = _CURRENT_CONFIG.get(key, default)
    return value if isinstance(value, str) and value.strip() else default


class KeywordFilter(filter.CustomFilter):
    """只有消息包含任一配置关键词时才通过过滤器。"""

    def filter(self, event: AstrMessageEvent, cfg: Any) -> bool:
        text = event.get_message_str() or ""
        keywords = _get_keywords()
        return any(keyword and keyword in text for keyword in keywords)


class LusigninPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context, config)

        global _CURRENT_CONFIG
        _CURRENT_CONFIG.clear()
        _CURRENT_CONFIG.update(
            {
                "keywords": DEFAULT_KEYWORDS,
                "success_message": DEFAULT_SUCCESS_MESSAGE,
                "duplicate_message": DEFAULT_DUPLICATE_MESSAGE,
            }
        )
        _CURRENT_CONFIG.update(config or {})

        self.config = config if config is not None else {}
        self.data_dir = Path(get_astrbot_plugin_data_path()) / PLUGIN_NAME
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_file = self.data_dir / "signin_data.json"
        self._save_lock = threading.Lock()
        self._cjk_font_cache: str | None = None
        self.user_data: dict[str, dict[str, Any]] = self._load_data()

        logger.info(f"[{PLUGIN_NAME}] 签到插件已加载，数据文件: {self.data_file}")

    # ---------- 数据持久化 ----------

    def _load_data(self) -> dict[str, dict[str, Any]]:
        if not self.data_file.exists():
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"[{PLUGIN_NAME}] 读取签到数据失败: {e}")
        return {}

    def _save_data(self) -> None:
        with self._save_lock:
            tmp_file = self.data_file.with_suffix(".json.tmp")
            try:
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(self.user_data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_file, self.data_file)
            except OSError as e:
                logger.error(f"[{PLUGIN_NAME}] 保存签到数据失败: {e}")
                try:
                    if tmp_file.exists():
                        tmp_file.unlink()
                except OSError:
                    pass

    def _get_user_key(self, event: AstrMessageEvent) -> str:
        sender_id = event.get_sender_id()
        if not sender_id:
            sender_id = event.get_session_id() or event.unified_msg_origin
        return f"{event.get_platform_name()}:{sender_id}"

    def _ensure_user(self, user_key: str, user_name: str) -> dict[str, Any]:
        user = self.user_data.setdefault(
            user_key,
            {"name": user_name or "匿名用户", "sign_dates": []},
        )
        if "sign_dates" not in user or not isinstance(user["sign_dates"], list):
            user["sign_dates"] = []
        if "name" not in user:
            user["name"] = user_name or "匿名用户"
        return user

    def _month_sign_count(self, user: dict[str, Any], year: int, month: int) -> int:
        prefix = f"{year:04d}-{month:02d}"
        return len({d for d in user.get("sign_dates", []) if isinstance(d, str) and d.startswith(prefix)})

    # ---------- 消息处理 ----------

    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.custom_filter(KeywordFilter)
    async def on_message(self, event: AstrMessageEvent):
        """包含关键词时执行签到，并发送月历图片和签到提示。"""
        # 若配置对象在热重载前已被更新，尽量同步到过滤器缓存
        global _CURRENT_CONFIG
        _CURRENT_CONFIG.update(self.config)

        user_name = event.get_sender_name() or "匿名用户"
        user_key = self._get_user_key(event)
        user = self._ensure_user(user_key, user_name)

        now = datetime.now(TZ_BEIJING)
        today = now.strftime("%Y-%m-%d")
        year, month = now.year, now.month

        is_first_sign = today not in user["sign_dates"]

        if is_first_sign:
            user["sign_dates"].append(today)
            # 去重并排序，保证月历上的打勾稳定
            user["sign_dates"] = sorted({d for d in user["sign_dates"] if isinstance(d, str)})
            user["name"] = user_name
            self._save_data()
            template = _get_message_text("success_message", DEFAULT_SUCCESS_MESSAGE)
        else:
            # 重复签到：不重复写入持久化数据，只更新内存中的昵称（下次真正签到时再落盘）
            user["name"] = user_name
            template = _get_message_text("duplicate_message", DEFAULT_DUPLICATE_MESSAGE)

        times = self._month_sign_count(user, year, month)
        text = template.replace("{{user}}", user_name).replace("{{times}}", str(times))

        image_path = self._generate_calendar_image(year, month, user_name, set(user["sign_dates"]))
        if image_path:
            event.track_temporary_local_file(image_path)
            yield event.make_result().file_image(image_path).message(text).stop_event()
        else:
            # 图片生成失败时至少发送文字提示
            yield event.plain_result(text).stop_event()

    # ---------- 月历图片 ----------

    def _generate_calendar_image(
        self,
        year: int,
        month: int,
        user_name: str,
        signed_dates: set[str],
    ) -> str | None:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.error(f"[{PLUGIN_NAME}] 未安装 Pillow，无法生成月历图片")
            return None

        try:
            font_path = self._find_cjk_font()
            title_font = self._load_font(font_path, 40)
            header_font = self._load_font(font_path, 30)
            day_font = self._load_font(font_path, 30)

            margin = 36
            cell_w = 128
            cell_h = 88
            title_h = 110
            header_h = 74
            max_weeks = 6

            width = margin * 2 + cell_w * 7
            height = title_h + header_h + cell_h * max_weeks + margin * 2

            img = Image.new("RGB", (width, height), "white")
            draw = ImageDraw.Draw(img)

            # 标题：2026年8月  用户名
            title = f"{year}年{month}月  {user_name}"
            self._draw_centered(draw, title, width // 2, margin + title_h // 2, title_font, (40, 40, 40))

            # 星期表头：日 一 二 三 四 五 六（周日开头）
            weekdays = ["日", "一", "二", "三", "四", "五", "六"]
            for col, weekday in enumerate(weekdays):
                x = margin + col * cell_w + cell_w // 2
                y = margin + title_h + header_h // 2
                self._draw_centered(draw, weekday, x, y, header_font, (120, 120, 120))

            first_weekday_monday0 = calendar.monthrange(year, month)[0]
            # 转换为周日起始的列：周一=1 ... 周六=6，周日=0
            first_col = (first_weekday_monday0 + 1) % 7
            days_in_month = calendar.monthrange(year, month)[1]

            for day in range(1, days_in_month + 1):
                col = (first_col + day - 1) % 7
                row = (first_col + day - 1) // 7
                x = margin + col * cell_w + cell_w // 2
                y = margin + title_h + header_h + row * cell_h + cell_h // 2

                date_str = f"{year:04d}-{month:02d}-{day:02d}"
                self._draw_centered(draw, str(day), x, y, day_font, (30, 30, 30))

                if date_str in signed_dates:
                    # 在日期右上侧画一个绿色对勾，不依赖字体是否包含 ✓ 字形
                    self._draw_check(draw, x + 28, y - 18, 20, (76, 175, 80))

            # 保存到系统临时目录，发送后由 AstrBot 清理
            filename = f"astrbot_lusignin_{time.time_ns()}.png"
            image_path = os.path.join(tempfile.gettempdir(), filename)
            img.save(image_path, "PNG")
            return image_path
        except Exception as e:
            logger.error(f"[{PLUGIN_NAME}] 生成月历图片失败: {e}")
            return None

    def _load_font(self, font_path: str | None, size: int):
        from PIL import ImageFont

        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    def _find_cjk_font(self) -> str | None:
        """查找一个支持中文/Unicode 的字体文件，并缓存结果。"""
        if self._cjk_font_cache:
            return self._cjk_font_cache

        path = self._search_cjk_font()
        self._cjk_font_cache = path
        return path

    def _search_cjk_font(self) -> str | None:
        # 1) 常见固定路径
        candidates = [
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
            "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
            "/usr/share/fonts/truetype/arphic/ukai.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyh.ttf",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path

        # 2) Linux/macOS 使用 fontconfig 列出真正支持中文的字体
        try:
            import subprocess

            for lang in ("zh-cn", "zh", "ja", "ko"):
                try:
                    proc = subprocess.run(
                        ["fc-list", f":lang={lang}", "file"],
                        capture_output=True,
                        text=True,
                        timeout=3,
                        check=False,
                    )
                    for line in proc.stdout.splitlines():
                        font_path = line.split(":", 1)[0].strip()
                        if font_path and os.path.exists(font_path):
                            return font_path
                except Exception:
                    continue
        except Exception:
            pass

        # 3) 使用 glob 扫描常见字体目录
        patterns = []
        if os.name == "nt":
            fonts_dir = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")
            patterns = [
                os.path.join(fonts_dir, "msyh*"),
                os.path.join(fonts_dir, "simhei*"),
                os.path.join(fonts_dir, "simsun*"),
                os.path.join(fonts_dir, "Deng*"),
                os.path.join(fonts_dir, "NotoSans*"),
                os.path.join(fonts_dir, "SourceHanSans*"),
            ]
        else:
            patterns = [
                "/usr/share/fonts/**/*CJK*",
                "/usr/share/fonts/**/*cjk*",
                "/usr/share/fonts/**/*wqy*",
                "/usr/share/fonts/**/*WenQuanYi*",
                "/usr/share/fonts/**/*NotoSans*",
                "/usr/share/fonts/**/*DroidSansFallback*",
                "/usr/share/fonts/**/*uming*",
                "/usr/share/fonts/**/*ukai*",
                "/System/Library/Fonts/**/*PingFang*",
                "/System/Library/Fonts/**/*Hiragino*",
                "/System/Library/Fonts/**/*STHeiti*",
                "/Library/Fonts/**/*NotoSansCJK*",
                "/Library/Fonts/**/*Arial Unicode*",
            ]

        for pattern in patterns:
            try:
                for font_path in glob.glob(pattern, recursive=True):
                    if os.path.isfile(font_path):
                        return font_path
            except Exception:
                continue

        return None

    @staticmethod
    def _draw_centered(draw, text: str, cx: int, cy: int, font, fill):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except AttributeError:
            tw = draw.textlength(text, font=font)
            th = font.size
        draw.text((cx - tw / 2, cy - th / 2), text, font=font, fill=fill)

    @staticmethod
    def _draw_check(draw, x: int, y: int, size: int, fill):
        """用线段画一个简易对勾。"""
        mid_x = int(x + size * 0.35)
        start_y = int(y + size * 0.5)
        end_y = int(y + size)
        draw.line([(x, start_y), (mid_x, end_y)], fill=fill, width=3)
        draw.line([(mid_x, end_y), (int(x + size), y)], fill=fill, width=3)

    async def terminate(self) -> None:
        logger.info(f"[{PLUGIN_NAME}] 签到插件已卸载")
