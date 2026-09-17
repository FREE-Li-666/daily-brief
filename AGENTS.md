# 项目规则：每日早报（daily-brief）

## 这是什么

每天北京时间 07:00，把合肥当天的天气、农历黄历、星座运势、节假日状态拼成一条消息，通过 PushPlus 推送到微信。定时跑在 GitHub Actions 上，不依赖本机开机。

## 技术约定

- 用 Python 3，标准库优先。唯一的第三方依赖是 `lunar_python`（本地计算农历、节气、宜忌），不要随手引入新依赖。
- 文案全部用中文，消息追求一屏读完，不要写成大段文字。
- 城市默认合肥、星座默认白羊座。这两个值通过 `CITY`、`ZODIAC` 环境变量或 `--city`、`--sign` 参数覆盖，不要把具体值硬编码进逻辑。

## 代码结构

- `main.py` 命令行入口与流程编排，`weather.py`、`calendar_cn.py`、`zodiac.py` 负责取数，`render.py` 拼消息，`pushplus.py` 负责发送，`net.py` 是标准库 HTTP 封装。
- `tests/` 全部是离线单元测试，不允许依赖网络，也不允许真实发送。

## 必须守住的边界

- 任何单个数据源失败都不能导致当天收不到消息。天气按 和风天气 → wttr.in → Open-Meteo 依次降级，星座取不到就整段省略，节假日退到本地缓存。
- 任何密钥都不许写进代码、测试或提交记录，密钥只走环境变量和 GitHub Secrets。
- PushPlus 发送失败必须抛错让 GitHub Actions 任务变红，不要静默吞掉。
- 不要为了让测试通过而删掉降级分支。

## 常用命令

- 跑测试：`python3 -m unittest discover -s tests -t .`
- 只看内容不发送：`python3 main.py --dry-run`
- 完全离线测试：`python3 main.py --dry-run --offline --date 2026-10-01`
- 真实发送：`PUSHPLUS_TOKEN=你的token python3 main.py`

## 改动完成的标准

- 改完必须跑一遍完整测试。
- 改了配置项、命令行参数或数据源行为，同步更新 `README.md` 里对应的表格。
- 改成涉及单个数据源的改动，要顺手确认降级链还成立。

## 已知的坑

- macOS 上 python.org 版 Python 默认没有 CA 证书，`net.py` 里已经做了自动查找，别把这层删掉。
- wttr.in 必须用 `lang=zh-cn`，用 `lang=zh` 会返回英文描述。
- 墨迹天气没有可用的公开接口，不要尝试接入。
- 定时任务用 UTC 计时：`0 23 * * *` 等于北京时间 07:00，改时间要换算。
