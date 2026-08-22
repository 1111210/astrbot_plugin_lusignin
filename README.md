# astrbot_plugin_lusignin

AstrBot 签到插件，面向 aiocqhttp 对话场景。

## 功能

- 在收到消息时检测是否包含后台配置的关键词（如“签到”）。
- 命中关键词后自动完成当日签到，并持久化保存签到日期。
- 生成当月月历图片，已签到的日期会打勾。
- 同一聊天中发送月历图片和签到提示（支持 `{{user}}`、`{{times}}` 占位符）。
- 当天重复签到不会重复写入数据，并给出“重复签到”提示。
- 未命中关键词时不拦截事件，AstrBot 默认逻辑照常接管。
- 命中关键词后由插件完成回复并终止本次事件继续传播，避免默认 LLM 或其他插件重复回复。
- 内置 Droid Sans Fallback 中文字体与 FreeSans Unicode 回退字体，月历图片不依赖系统字体环境。

## 配置

| 配置项 | 说明 |
| --- | --- |
| `keywords` | 触发签到的关键词列表，消息包含任意一个即触发 |
| `success_message` | 签到成功提示，支持 `{{user}}`、`{{times}}` |
| `duplicate_message` | 重复签到提示，支持 `{{user}}`、`{{times}}` |

## 数据位置

签到数据保存在 `data/plugin_data/astrbot_plugin_lusignin/signin_data.json`。
