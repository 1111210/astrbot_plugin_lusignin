# astrbot_plugin_lusignin

AstrBot 签到插件，面向 aiocqhttp 对话场景。

## 功能

- 在收到消息时检测是否包含后台配置的关键词（如“签到”）。
- 命中关键词后自动完成当日签到，并持久化保存签到日期。
- 生成当月月历图片，已签到的日期会打勾。
- 同一聊天中发送月历图片和签到提示（支持 `{{user}}`、`{{times}}` 占位符）。
- 当天重复签到不会重复写入数据，并给出“重复签到”提示。
- 支持补签指令：`/补签 日期`，例如 `/补签 20`。
  - 补签前必须先完成今日正常签到。
  - 每天只能补签一次。
  - 只能补签本月已达到且未签到的日期。
- 未命中关键词时不拦截事件，AstrBot 默认逻辑照常接管。
- 命中关键词后由插件完成回复并终止本次事件继续传播，避免默认 LLM 或其他插件重复回复。
- 内置 Droid Sans Fallback 中文字体与 DejaVu Sans Bold Unicode 回退字体，月历图片不依赖系统字体环境。

## 配置

| 配置项 | 说明 |
| --- | --- |
| `keywords` | 触发签到的关键词列表，消息包含任意一个即触发 |
| `success_message` | 签到成功提示，支持 `{{user}}`、`{{times}}` |
| `duplicate_message` | 重复签到提示，支持 `{{user}}`、`{{times}}` |
| `makeup_success_message` | 补签成功提示，支持 `{{user}}`、`{{date}}`、`{{times}}` |
| `makeup_duplicate_message` | 每天重复补签提示，支持 `{{user}}` |
| `makeup_fail_message` | 补签失败提示，支持 `{{user}}`、`{{reason}}` |

## 自定义日期背景

月历日期背景从以下 PNG 文件读取，每次生成图片时都会重新加载，可直接替换文件自定义：

- `assets/date_bg_normal.png`：未签到日期背景，默认为透明
- `assets/date_bg_signed.png`：已签到日期背景，默认带绿色对勾
- `assets/date_bg_makeup.png`：补签日期背景，默认与正常签到背景一致

建议图片尺寸为 `120×84`，插件会自动缩放到日期格大小。

## 开源许可

- 项目代码：AGPL-3.0
- `DroidSansFallbackFull.ttf`：Apache License 2.0
- `DejaVuSans.ttf` / `DejaVuSans-Bold.ttf`：Bitstream Vera License（宽松许可）
- 日期背景 PNG：本插件原创资源

以上字体许可文件分别保存在 `assets/LICENSE-DroidSansFallback.txt` 和 `assets/LICENSE-DejaVu.txt`。

## 数据位置

签到数据保存在 `data/plugin_data/astrbot_plugin_lusignin/signin_data.json`。

---

本程序由AI生成，但已经过功能测试
