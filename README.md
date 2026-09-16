# 每日早报：微信定时推送

每天早上 07:00（北京时间）自动给你发一条微信，内容包括今天的天气、黄历宜忌、星座运势和节假日状态。

```
🌤 9月16日 周三 · 合肥
天气　烟霾 19~27℃ ｜ 东风9km/h ｜ 紫外线强
农历　八月初六 · 白露后第9天
黄历　宜 开市、交易、立券、纳财 · 忌 嫁娶、破土、进人口 · 冲猪（丁亥）煞东
星座　白羊座 ★★★★☆ 适合处理旧事，别急着表态。（幸运色酒红 · 幸运数字9）
假期　工作日 · 距中秋节还有 9 天
```

上面这段是真实的本地试跑输出（`--dry-run`，没有发到微信）；星座那行是示意，实际取不到时会整行省略。

定时跑在 GitHub Actions 上，电脑关机也能收到。任何单个数据源挂掉都不会导致当天收不到消息，只会在末尾多一行提示。

## 数据来源与降级顺序

| 内容 | 主来源 | 备用 |
| --- | --- | --- |
| 天气 | 和风天气官方 API | wttr.in → Open-Meteo → 显示"数据暂不可用" |
| 节假日 | holiday-cn 公开数据集（联网后自动缓存到 `data/holidays/`） | 本地缓存 → 只按周末判断 |
| 黄历、农历、节气 | `lunar_python` 本地计算 | 无网络依赖，不会失效 |
| 星座运势 | 天行数据（填了 key 时） | 免 key 公共接口 → 取不到就整段省略 |
| 推送 | PushPlus | 无（发送失败会让任务变红并给你发邮件） |

## 一、先准备好两个 key（各约两分钟）

1. **PushPlus**（负责把消息送进微信，必做）
   打开 https://www.pushplus.plus ，用微信扫码登录，在"一对一推送"页面复制你的 `token`。

2. **和风天气**（负责天气数据，建议做）
   打开 https://dev.qweather.com ，注册后在控制台创建项目，拿到 `KEY`，同时记下控制台给你的 **API Host**（形如 `abcdefg.re.qweatherapi.com`，和风现在的免费订阅要求用自己的专属域名）。

   不注册也能用，程序会自动走 wttr.in 或 Open-Meteo，内容和温度照样准，只是少了穿衣、紫外线这类生活指数。

3. **天行数据**（负责星座运势，可选）
   打开 https://www.tianapi.com ，注册后申请"星座运势"接口，拿到 key 填进 `TIANAPI_KEY`。没有 key 时程序会尝试免 key 的公共接口，取不到就跳过星座那一段，不影响其他内容。

## 二、本地试跑（可选，但建议先做）

```bash
cd daily-brief
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 只看内容，不推送到微信
python3 main.py --dry-run --city 合肥 --sign 白羊座

# 完全不联网，用来确认渲染逻辑
python3 main.py --dry-run --offline --date 2026-10-01
```

想看真实效果就直接把 key 填进环境变量再跑：

```bash
export PUSHPLUS_TOKEN=你的token
export QWEATHER_KEY=你的key
export QWEATHER_HOST=你的专属host
export CITY=合肥
export ZODIAC=白羊座
python3 main.py
```

## 三、部署到 GitHub（每天自动跑）

你已经有 GitHub 账号，本机还没有 `gh` 命令和 Git 身份，按下面的顺序做一次就好。

1. **装 gh 并登录**（也可以跳过这步，全部在网页上点）

   ```bash
   brew install gh
   gh auth login
   ```

2. **配置 Git 身份并初始化仓库**

   ```bash
   cd daily-brief
   git config --global user.name "你的名字"
   git config --global user.email "你的邮箱"
   git init -b main
   git add .
   git commit -m "feat: 每日早报初始版本"
   ```

3. **创建远程仓库并推送**

   ```bash
   gh repo create daily-brief --private --source=. --remote=origin --push
   ```

   私库一样能用定时任务，免费额度每月 2000 分钟，这个任务每天跑不到 1 分钟，完全用不完。

4. **填 Secrets**（在仓库网页 Settings → Secrets and variables → Actions → New repository secret）

   | 名称 | 必填 | 说明 |
   | --- | --- | --- |
   | `PUSHPLUS_TOKEN` | 是 | 推送用的 token |
   | `QWEATHER_KEY` | 建议 | 和风天气 KEY，不填则直接用备用天气源 |
   | `QWEATHER_HOST` | 建议 | 你的专属 API Host，例如 `abcdefg.re.qweatherapi.com`，不要带 `https://` |
   | `CITY` | 是 | 城市名，例如 `合肥` |
   | `ZODIAC` | 是 | 你的星座，例如 `白羊座`（也接受 `aries`） |
   | `TIANAPI_KEY` | 否 | 天行数据 key，没有就自动跳过星座段 |
   | `PUSHPLUS_TOPIC` | 否 | 只有群组推送才需要 |

5. **手动触发一次验证**

   ```bash
   gh workflow run "每日早报"
   gh run watch
   ```

   或者在仓库的 Actions 页面点 `每日早报` → `Run workflow`。勾上 `dry_run` 就只打印内容、不推到微信，适合先看排版。

6. 收到微信就算通了。之后每天 07:00 自动送达。

## 四、配置项速查

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PUSHPLUS_TOKEN` | 无 | 必填，正式发送时缺了会直接报错退出 |
| `CITY` | 合肥 | 也支持 `--city` 临时覆盖 |
| `ZODIAC` | 白羊座 | 也支持 `--sign`；写 `--no-zodiac` 可整段去掉 |
| `QWEATHER_KEY` / `QWEATHER_HOST` | 空 / `devapi.qweather.com` | 都填上才走和风天气 |
| `TIANAPI_KEY` | 空 | 天行数据 key，填了优先用它取星座运势 |
| `HOROSCOPE_URL` | 空 | 自定义星座接口地址模板，占位符 `{key}`、`{sign}`、`{api_key}` |
| `PUSHPLUS_TOPIC` | 空 | 群组推送话题编码 |
| `HTTP_TIMEOUT` | 8 | 单个请求的超时秒数 |

命令行参数：

| 参数 | 作用 |
| --- | --- |
| `--dry-run` | 只打印消息，不推送到微信（数据照常实时抓取） |
| `--offline` | 完全不联网：不抓天气和星座，节假日只用本地缓存 |
| `--date 2026-10-01` | 指定日期，用来检查节日和调休的渲染效果 |
| `--city` / `--sign` | 临时覆盖城市和星座 |
| `--no-zodiac` | 不发送星座那一段 |
| `--verbose` | 把各数据源的失败原因打到日志里 |

## 五、跑测试

```bash
python3 -m unittest discover -s tests -t . -v
```

覆盖：节假日四种状态（工作日、周末、法定节日、调休上班）、下个假期倒数、缓存回退、天气三级降级、星座接口异常降级、消息渲染与 HTML 转义、PushPlus 失败语义、命令行退出码。

## 六、常见问题

**到点了但没收到。**
先去仓库 Actions 页面看这次运行是红的还是绿的。绿色代表已经成功发给 PushPlus，检查微信是否屏蔽了 PushPlus 服务号；红色看日志里的报错，多半是 token 或 key 填错。

**时间不准，晚了十几分钟。**
正常现象。GitHub 的定时任务在整点高峰期会排队，通常延迟几分钟到半小时。想更准就换一台常开的机器跑 `python3 main.py`。

**用了几个月突然不发了。**
GitHub 会在仓库连续 60 天没有任何活动后暂停定时任务，并给你发一封邮件。去 Actions 页面手动 `Run workflow` 一次即可恢复。想避免，每月手动跑一次，或加一个每月提交。

**天气显示来自备用源。**
说明和风天气这次没取到（KEY 过期、额度用尽或网络抖动），程序自动降级到了 wttr.in 或 Open-Meteo。内容仍然可用，只是生活指数可能少一两项。

**星座那一段没出现。**
星座运势是全网最不稳定的一类接口，免 key 的公共接口经常超时，也容易被海外节点拦。想稳定拿到就配一个天行数据的免费 key（`TIANAPI_KEY`），或者用 `HOROSCOPE_URL` 接自己熟悉的服务；都不配也不影响天气、黄历、节假日。

**本地跑报 `CERTIFICATE_VERIFY_FAILED`。**
macOS 上 python.org 安装包的解释器默认不带 CA 证书。程序已经会自动去找 `certifi` 包或系统证书（`/etc/ssl/cert.pem`），通常不用管；如果还是报错，装一下证书即可：`pip install certifi`，或运行 `/Applications/Python 3.13/Install Certificates.command`。

**为什么备用源里没有墨迹天气。**
墨迹天气没有面向个人的公开接口，网页端接口属于非官方，海外节点还经常被拦；而 GitHub Actions 的服务器在海外。所以兜底换成了同样免 key 的 wttr.in 和 Open-Meteo，能真正把消息发出来。

**想换星座运势的数据源。**
设环境变量 `HOROSCOPE_URL` 即可，占位符 `{key}` 是星座英文键、`{sign}` 是中文星座名、`{api_key}` 是 `TIANAPI_KEY`。解析器对 `short`、`fortune`、`content`、`all` 等字段名和 `result.list[0]` 这类嵌套结构都能兼容。

## 代码结构

| 文件 | 职责 |
| --- | --- |
| `main.py` | 命令行入口，编排取数与发送，决定退出码 |
| `weather.py` | 和风天气、wttr.in、Open-Meteo 三级降级 |
| `calendar_cn.py` | 节假日数据集与缓存、农历黄历本地计算 |
| `zodiac.py` | 星座运势取用与容错解析 |
| `render.py` | 纯文本与 HTML 两版消息渲染 |
| `pushplus.py` | PushPlus 发送与失败语义 |
| `net.py` | 标准库 HTTP 封装，含重试与超时 |
| `tests/` | 离线单元测试，全部不依赖网络 |
