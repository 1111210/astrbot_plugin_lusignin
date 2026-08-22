"""
AstrBot 签到插件（Lusignin）

- 面向 aiocqhttp 对话场景
- 收到消息后若包含后台配置的关键词，则自动签到并发送当月月历图片
- 未包含关键词时不拦截事件，交由 AstrBot 默认逻辑继续处理
"""

from __future__ import annotations

import calendar
import json
import os
import re
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

BUNDLED_FONT_PATH = Path(__file__).resolve().parent / "assets" / "DroidSansFallbackFull.ttf"
BUNDLED_FALLBACK_FONT_PATH = Path(__file__).resolve().parent / "assets" / "DejaVuSans.ttf"
BUNDLED_FALLBACK_BOLD_FONT_PATH = Path(__file__).resolve().parent / "assets" / "DejaVuSans-Bold.ttf"
DATE_BG_NORMAL_PATH = Path(__file__).resolve().parent / "assets" / "date_bg_normal.png"
DATE_BG_SIGNED_PATH = Path(__file__).resolve().parent / "assets" / "date_bg_signed.png"
DATE_BG_MAKEUP_PATH = Path(__file__).resolve().parent / "assets" / "date_bg_makeup.png"
DEJAVU_COVERAGE_RANGES = [
    (32, 126), (160, 745), (748, 750), (755, 755), (759, 759), (768, 847),
    (849, 851), (855, 856), (858, 858), (860, 866), (880, 887), (890, 895),
    (900, 906), (908, 908), (910, 929), (931, 1317), (1329, 1366), (1369, 1375),
    (1377, 1415), (1417, 1418), (1456, 1475), (1478, 1479), (1488, 1514),
    (1520, 1524), (1542, 1543), (1545, 1546), (1548, 1548), (1557, 1557),
    (1563, 1563), (1567, 1567), (1569, 1594), (1600, 1621), (1623, 1623),
    (1626, 1626), (1632, 1648), (1652, 1652), (1657, 1727), (1734, 1736),
    (1739, 1740), (1742, 1742), (1744, 1744), (1749, 1749), (1776, 1785),
    (1984, 2023), (2027, 2037), (2040, 2042), (3647, 3647), (3713, 3714),
    (3716, 3716), (3719, 3720), (3722, 3722), (3725, 3725), (3732, 3735),
    (3737, 3743), (3745, 3747), (3749, 3749), (3751, 3751), (3754, 3755),
    (3757, 3769), (3771, 3773), (3776, 3780), (3782, 3782), (3784, 3789),
    (3792, 3801), (3804, 3805), (4256, 4293), (4304, 4348), (5121, 5127),
    (5129, 5147), (5149, 5173), (5175, 5194), (5196, 5202), (5204, 5309),
    (5312, 5354), (5356, 5383), (5392, 5438), (5440, 5456), (5458, 5482),
    (5492, 5509), (5514, 5526), (5536, 5551), (5598, 5598), (5601, 5601),
    (5702, 5703), (5742, 5750), (5760, 5788), (7424, 7444), (7446, 7459),
    (7462, 7470), (7472, 7515), (7517, 7530), (7543, 7544), (7547, 7547),
    (7549, 7549), (7557, 7557), (7579, 7615), (7620, 7625), (7680, 7931),
    (7936, 7957), (7960, 7965), (7968, 8005), (8008, 8013), (8016, 8023),
    (8025, 8025), (8027, 8027), (8029, 8029), (8031, 8061), (8064, 8116),
    (8118, 8132), (8134, 8147), (8150, 8155), (8157, 8175), (8178, 8180),
    (8182, 8190), (8192, 8292), (8298, 8305), (8308, 8334), (8336, 8348),
    (8352, 8373), (8376, 8378), (8381, 8381), (8400, 8401), (8406, 8407),
    (8411, 8412), (8417, 8417), (8448, 8457), (8459, 8521), (8523, 8523),
    (8526, 8526), (8528, 8581), (8585, 8585), (8592, 8977), (8984, 8985),
    (8988, 8993), (8996, 9000), (9003, 9004), (9075, 9077), (9082, 9082),
    (9085, 9085), (9095, 9095), (9108, 9108), (9115, 9134), (9166, 9167),
    (9187, 9187), (9189, 9189), (9192, 9192), (9250, 9251), (9312, 9321),
    (9472, 9884), (9886, 9912), (9920, 9923), (9954, 9954), (9985, 9988),
    (9990, 9993), (9996, 10023), (10025, 10059), (10061, 10061), (10063, 10066),
    (10070, 10070), (10072, 10078), (10081, 10132), (10136, 10159), (10161, 10174),
    (10181, 10182), (10208, 10208), (10214, 10219), (10224, 10495), (10502, 10503),
    (10506, 10507), (10560, 10561), (10627, 10628), (10702, 10709), (10731, 10731),
    (10746, 10747), (10752, 10754), (10764, 10780), (10799, 10799), (10858, 10859),
    (10877, 10912), (10926, 10938), (11001, 11002), (11008, 11034), (11039, 11044),
    (11091, 11092), (11360, 11383), (11385, 11391), (11520, 11557), (11568, 11621),
    (11631, 11631), (11800, 11800), (11807, 11807), (11810, 11813), (11822, 11822),
    (19904, 19967), (42192, 42239), (42564, 42567), (42572, 42573), (42576, 42577),
    (42580, 42583), (42594, 42606), (42634, 42637), (42644, 42645), (42648, 42649),
    (42760, 42774), (42779, 42783), (42786, 42795), (42800, 42817), (42822, 42827),
    (42830, 42835), (42838, 42839), (42852, 42855), (42880, 42883), (42889, 42894),
    (42896, 42897), (42912, 42922), (43000, 43007), (61184, 61209), (62464, 62502),
    (62504, 62529), (63173, 63173), (64256, 64262), (64275, 64279), (64285, 64310),
    (64312, 64316), (64318, 64318), (64320, 64321), (64323, 64324), (64326, 64335),
    (64338, 64419), (64426, 64429), (64467, 64476), (64478, 64479), (64484, 64489),
    (64508, 64511), (65024, 65039), (65056, 65059), (65136, 65140), (65142, 65276),
    (65279, 65279), (65529, 65533), (66304, 66334), (66336, 66339), (119552, 119638),
    (120120, 120121), (120123, 120126), (120128, 120132), (120134, 120134),
    (120138, 120144), (120146, 120171), (120276, 120327), (120662, 120719),
    (120792, 120801), (120812, 120821), (127024, 127123), (127136, 127150),
    (127153, 127166), (127169, 127183), (127185, 127199), (127761, 127768),
    (128045, 128046), (128049, 128049), (128053, 128053), (128512, 128547),
    (128549, 128555), (128557, 128576), (128579, 128579),
]


TZ_BEIJING = timezone(timedelta(hours=8))

DEFAULT_KEYWORDS = ["签到", "打卡"]
DEFAULT_SUCCESS_MESSAGE = "{{user}} 签到成功！你本月已经签到 {{times}} 次。"
DEFAULT_DUPLICATE_MESSAGE = "{{user}} 今天已经签过到啦（重复签到）！你本月已经签到 {{times}} 次。"
DEFAULT_MAKEUP_SUCCESS_MESSAGE = "{{user}} 补签成功！已补签 {{date}}。你本月已经签到 {{times}} 次。"
DEFAULT_MAKEUP_DUPLICATE_MESSAGE = "{{user}} 今天已经补签过了，不能重复补签。"
DEFAULT_MAKEUP_FAIL_MESSAGE = "{{user}} 补签失败：{{reason}}"

# 模块级配置缓存。KeywordFilter 在装饰器阶段被实例化，无法直接拿到插件实例，
# 因此通过这个全局配置在插件 __init__ 时更新，过滤器运行时读取最新关键词。
_CURRENT_CONFIG: dict[str, Any] = {
    "keywords": DEFAULT_KEYWORDS,
    "success_message": DEFAULT_SUCCESS_MESSAGE,
    "duplicate_message": DEFAULT_DUPLICATE_MESSAGE,
    "makeup_success_message": DEFAULT_MAKEUP_SUCCESS_MESSAGE,
    "makeup_duplicate_message": DEFAULT_MAKEUP_DUPLICATE_MESSAGE,
    "makeup_fail_message": DEFAULT_MAKEUP_FAIL_MESSAGE,
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
                "makeup_success_message": DEFAULT_MAKEUP_SUCCESS_MESSAGE,
                "makeup_duplicate_message": DEFAULT_MAKEUP_DUPLICATE_MESSAGE,
                "makeup_fail_message": DEFAULT_MAKEUP_FAIL_MESSAGE,
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
            {
                "name": user_name or "匿名用户",
                "sign_dates": [],
                "makeup_dates": [],
                "last_makeup_date": "",
            },
        )
        if "sign_dates" not in user or not isinstance(user["sign_dates"], list):
            user["sign_dates"] = []
        if "makeup_dates" not in user or not isinstance(user["makeup_dates"], list):
            user["makeup_dates"] = []
        if "last_makeup_date" not in user:
            user["last_makeup_date"] = ""
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

        image_path = self._generate_calendar_image(
            year,
            month,
            user_name,
            set(user["sign_dates"]),
            set(user.get("makeup_dates", [])),
        )
        if image_path:
            event.track_temporary_local_file(image_path)
            yield event.make_result().file_image(image_path).message(text).stop_event()
        else:
            # 图片生成失败时至少发送文字提示
            yield event.plain_result(text).stop_event()

    @filter.command("补签")
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def makeup(self, event: AstrMessageEvent, day: int = None):
        """补签指令：/补签 20，只能补签本月已到达且未签到的日期。"""
        global _CURRENT_CONFIG
        _CURRENT_CONFIG.update(self.config)

        user_name = event.get_sender_name() or "匿名用户"
        user_key = self._get_user_key(event)
        user = self._ensure_user(user_key, user_name)

        now = datetime.now(TZ_BEIJING)
        today_str = now.strftime("%Y-%m-%d")
        year, month, today_day = now.year, now.month, now.day

        # 兼容参数解析失败时手动从消息中提取数字
        if day is None:
            match = re.search(r"(?:补签|makeup)\s*(\d{1,2})", event.message_str or "")
            if match:
                day = int(match.group(1))

        if day is None:
            yield event.plain_result(
                self._format_makeup_message(
                    _get_message_text("makeup_fail_message", DEFAULT_MAKEUP_FAIL_MESSAGE),
                    user_name,
                    reason="请提供补签日期，例如：/补签 20",
                )
            )
            return

        days_in_month = calendar.monthrange(year, month)[1]
        if day < 1 or day > days_in_month:
            yield event.plain_result(
                self._format_makeup_message(
                    _get_message_text("makeup_fail_message", DEFAULT_MAKEUP_FAIL_MESSAGE),
                    user_name,
                    reason=f"补签日期无效，请输入本月 1-{days_in_month} 之间的日期",
                )
            )
            return

        if day > today_day:
            yield event.plain_result(
                self._format_makeup_message(
                    _get_message_text("makeup_fail_message", DEFAULT_MAKEUP_FAIL_MESSAGE),
                    user_name,
                    reason="只能补签本月已达到的日期",
                )
            )
            return

        if day == today_day:
            yield event.plain_result(
                self._format_makeup_message(
                    _get_message_text("makeup_fail_message", DEFAULT_MAKEUP_FAIL_MESSAGE),
                    user_name,
                    reason="今天已正常签到，无需补签",
                )
            )
            return

        # 规则 1：今天正常签到后方可补签
        if today_str not in user["sign_dates"]:
            yield event.plain_result(
                self._format_makeup_message(
                    _get_message_text("makeup_fail_message", DEFAULT_MAKEUP_FAIL_MESSAGE),
                    user_name,
                    reason="请先完成今日签到后再补签",
                )
            )
            return

        # 规则 2：每天只能补签一次
        if user.get("last_makeup_date") == today_str:
            times = self._month_sign_count(user, year, month)
            yield event.plain_result(
                self._format_makeup_message(
                    _get_message_text("makeup_duplicate_message", DEFAULT_MAKEUP_DUPLICATE_MESSAGE),
                    user_name,
                    times=times,
                )
            )
            return

        target_str = f"{year:04d}-{month:02d}-{day:02d}"
        if target_str in user["sign_dates"]:
            yield event.plain_result(
                self._format_makeup_message(
                    _get_message_text("makeup_fail_message", DEFAULT_MAKEUP_FAIL_MESSAGE),
                    user_name,
                    reason="该日期已经签到，无需补签",
                )
            )
            return

        # 执行补签
        user["sign_dates"].append(target_str)
        user["sign_dates"] = sorted({d for d in user["sign_dates"] if isinstance(d, str)})
        user["makeup_dates"] = sorted(
            set(user.get("makeup_dates", [])) | {target_str}
        )
        user["last_makeup_date"] = today_str
        user["name"] = user_name
        self._save_data()

        times = self._month_sign_count(user, year, month)
        date_text = f"{month}月{day}日"
        text = self._format_makeup_message(
            _get_message_text("makeup_success_message", DEFAULT_MAKEUP_SUCCESS_MESSAGE),
            user_name,
            times=times,
            date_text=date_text,
        )

        image_path = self._generate_calendar_image(
            year,
            month,
            user_name,
            set(user["sign_dates"]),
            set(user.get("makeup_dates", [])),
        )
        if image_path:
            event.track_temporary_local_file(image_path)
            yield event.make_result().file_image(image_path).message(text).stop_event()
        else:
            yield event.plain_result(text).stop_event()

    @staticmethod
    def _format_makeup_message(
        template: str,
        user_name: str,
        times: int | None = None,
        date_text: str | None = None,
        reason: str | None = None,
    ) -> str:
        text = template.replace("{{user}}", user_name)
        if times is not None:
            text = text.replace("{{times}}", str(times))
        if date_text is not None:
            text = text.replace("{{date}}", date_text)
        if reason is not None:
            text = text.replace("{{reason}}", reason)
        return text

    # ---------- 月历图片 ----------

    def _generate_calendar_image(
        self,
        year: int,
        month: int,
        user_name: str,
        signed_dates: set[str],
        makeup_dates: set[str] | None = None,
    ) -> str | None:
        makeup_dates = makeup_dates or set()
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.error(f"[{PLUGIN_NAME}] 未安装 Pillow，无法生成月历图片")
            return None

        try:
            cjk_font_path = self._find_cjk_font()
            fallback_font_path = str(BUNDLED_FALLBACK_BOLD_FONT_PATH)

            title_cjk_font = self._load_font(cjk_font_path, 58)
            title_fallback_font = self._load_font(fallback_font_path, 58)
            header_cjk_font = self._load_font(cjk_font_path, 44)
            header_fallback_font = self._load_font(fallback_font_path, 44)
            day_cjk_font = self._load_font(cjk_font_path, 50)
            day_fallback_font = self._load_font(fallback_font_path, 50)

            margin = 16
            cell_w = 120
            cell_h = 78
            title_h = 88
            header_h = 56
            max_weeks = 6

            width = margin * 2 + cell_w * 7
            height = title_h + header_h + cell_h * max_weeks + margin * 2

            img = Image.new("RGB", (width, height), "white")
            draw = ImageDraw.Draw(img)

            # 每次生成都从 PNG 文件读取日期背景图，方便用户替换自定义背景
            bg_normal = self._load_date_bg(DATE_BG_NORMAL_PATH, cell_w, cell_h)
            bg_signed = self._load_date_bg(DATE_BG_SIGNED_PATH, cell_w, cell_h)
            bg_makeup = self._load_date_bg(DATE_BG_MAKEUP_PATH, cell_w, cell_h)

            # 标题：2026年8月  用户名
            title = f"{year}年{month}月  {user_name}"
            self._draw_centered(draw, title, width // 2, margin + title_h // 2, title_cjk_font, title_fallback_font, (40, 40, 40))

            # 星期表头：日 一 二 三 四 五 六（周日开头）
            weekdays = ["日", "一", "二", "三", "四", "五", "六"]
            for col, weekday in enumerate(weekdays):
                x = margin + col * cell_w + cell_w // 2
                y = margin + title_h + header_h // 2
                self._draw_centered(draw, weekday, x, y, header_cjk_font, header_fallback_font, (120, 120, 120))

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
                cell_left = x - cell_w // 2
                cell_top = y - cell_h // 2

                if date_str in signed_dates:
                    if date_str in makeup_dates and bg_makeup is not None:
                        img.paste(bg_makeup, (cell_left, cell_top), bg_makeup)
                    elif bg_signed is not None:
                        img.paste(bg_signed, (cell_left, cell_top), bg_signed)
                    else:
                        # 兼容 PNG 缺失时的程序化兜底
                        draw.rectangle(
                            [
                                cell_left + 6,
                                cell_top + 6,
                                cell_left + cell_w - 6,
                                cell_top + cell_h - 6,
                            ],
                            fill=(232, 247, 232),
                        )
                        self._draw_check_background(
                            draw,
                            x,
                            y,
                            min(cell_w, cell_h) * 0.66,
                            (120, 200, 120),
                        )
                else:
                    if bg_normal is not None:
                        img.paste(bg_normal, (cell_left, cell_top), bg_normal)

                self._draw_centered(draw, str(day), x, y, day_cjk_font, day_fallback_font, (30, 30, 30))

            # 保存到系统临时目录，发送后由 AstrBot 清理
            filename = f"astrbot_lusignin_{time.time_ns()}.png"
            image_path = os.path.join(tempfile.gettempdir(), filename)
            img.save(image_path, "PNG")
            return image_path
        except Exception as e:
            logger.error(f"[{PLUGIN_NAME}] 生成月历图片失败: {e}")
            return None

    def _load_date_bg(self, path, cell_w: int, cell_h: int):
        """读取日期背景 PNG。每次生成月历都会重新读取，支持用户直接替换图片。"""
        try:
            from PIL import Image

            if not os.path.exists(path):
                return None
            bg = Image.open(path).convert("RGBA")
            if bg.size != (cell_w, cell_h):
                bg = bg.resize((cell_w, cell_h), Image.LANCZOS)
            return bg
        except Exception as e:
            logger.warning(f"[{PLUGIN_NAME}] 读取日期背景图失败 {path}: {e}")
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
        """直接使用插件内置的中文字体，不依赖系统字体。"""
        if self._cjk_font_cache:
            return self._cjk_font_cache

        font_path = str(BUNDLED_FONT_PATH)
        if os.path.exists(font_path):
            self._cjk_font_cache = font_path
            return font_path

        self._cjk_font_cache = None
        return None

    @staticmethod
    def _draw_centered(draw, text: str, cx: int, cy: int, cjk_font, fallback_font, fill):
        """居中绘制文本，并智能切换中文字体与 Unicode 回退字体。"""
        runs = LusigninPlugin._split_font_runs(text, cjk_font, fallback_font)
        total_w = 0.0
        for run_text, run_font in runs:
            try:
                total_w += draw.textlength(run_text, font=run_font)
            except AttributeError:
                bbox = draw.textbbox((0, 0), run_text, font=run_font)
                total_w += bbox[2] - bbox[0]

        try:
            font_size = max(getattr(cjk_font, "size", 12), getattr(fallback_font, "size", 12))
        except Exception:
            font_size = 12

        x = cx - total_w / 2
        y = cy - font_size / 2
        for run_text, run_font in runs:
            draw.text(
                (x, y),
                run_text,
                font=run_font,
                fill=fill,
                stroke_width=2,
                stroke_fill=fill,
            )
            try:
                x += draw.textlength(run_text, font=run_font)
            except AttributeError:
                bbox = draw.textbbox((0, 0), run_text, font=run_font)
                x += bbox[2] - bbox[0]

    @staticmethod
    def _split_font_runs(text: str, cjk_font, fallback_font):
        """将文本按 DejaVu 覆盖范围拆分成连续片段，DejaVu 不覆盖的字符回退到 Droid。"""
        runs: list[tuple[str, object]] = []
        current_chars: list[str] = []
        current_font = None

        for ch in text:
            # 主动判断字符是否在 DejaVu 的覆盖范围内，避免依赖缺字时报错/占位符
            font = fallback_font if LusigninPlugin._is_dejavu_covered(ch) else cjk_font
            if current_font is None:
                current_font = font
            if font is not current_font:
                if current_chars:
                    runs.append(("".join(current_chars), current_font))
                current_chars = [ch]
                current_font = font
            else:
                current_chars.append(ch)

        if current_chars:
            runs.append(("".join(current_chars), current_font))
        return runs

    @staticmethod
    def _is_dejavu_covered(ch: str) -> bool:
        cp = ord(ch)
        for start, end in DEJAVU_COVERAGE_RANGES:
            if start <= cp <= end:
                return True
        return False

    @staticmethod
    def _is_cjk_char(ch: str) -> bool:
        cp = ord(ch)
        return (
            0x1100 <= cp <= 0x11FF
            or 0x2E80 <= cp <= 0x2EFF
            or 0x3000 <= cp <= 0x303F
            or 0x3040 <= cp <= 0x30FF
            or 0x3100 <= cp <= 0x312F
            or 0x3130 <= cp <= 0x318F
            or 0x31A0 <= cp <= 0x31BF
            or 0x31C0 <= cp <= 0x31EF
            or 0x3200 <= cp <= 0x32FF
            or 0x3300 <= cp <= 0x33FF
            or 0x3400 <= cp <= 0x4DBF
            or 0x4E00 <= cp <= 0x9FFF
            or 0xA000 <= cp <= 0xA48F
            or 0xA490 <= cp <= 0xA4CF
            or 0xAC00 <= cp <= 0xD7AF
            or 0xF900 <= cp <= 0xFAFF
            or 0xFE30 <= cp <= 0xFE4F
            or 0xFF00 <= cp <= 0xFFEF
            or 0x20000 <= cp <= 0x2A6DF
            or 0x2A700 <= cp <= 0x2B73F
            or 0x2B740 <= cp <= 0x2B81F
            or 0x2B820 <= cp <= 0x2CEAF
            or 0x2F800 <= cp <= 0x2FA1F
        )

    @staticmethod
    def _draw_check_background(draw, cx: int, cy: int, size: float, fill):
        """在日期格中央绘制一个较大的对勾，作为签到日期背景。"""
        size = max(20, int(size))
        line_width = max(6, int(size * 0.16))
        x0 = cx - size * 0.5
        y0 = cy - size * 0.5

        draw.line(
            [
                (int(x0 + size * 0.08), int(cy)),
                (int(x0 + size * 0.38), int(cy + size * 0.34)),
            ],
            fill=fill,
            width=line_width,
        )
        draw.line(
            [
                (int(x0 + size * 0.38), int(cy + size * 0.34)),
                (int(x0 + size * 0.94), int(cy - size * 0.30)),
            ],
            fill=fill,
            width=line_width,
        )

    async def terminate(self) -> None:
        logger.info(f"[{PLUGIN_NAME}] 签到插件已卸载")
