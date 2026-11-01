# JobPocket · 求职信息整理助手

把自己在 BOSS 直聘网页版推荐列表中可见的岗位，整理成能筛选、能保存、能接着处理的本地表格。

**当前版本：0.1.0，首个适配器为 BOSS 直聘。** Python + Playwright，可见浏览器、手动登录；同一工作目录累计最多 200 个去重职位。适合个人求职整理及学习浏览器自动化。

> 适配状态：已提供合成页面的离线浏览器测试；尚未通过真实登录后的 BOSS 推荐页验收。默认 CSS 是可调整的初始适配，并非对当前所有账号和页面版本都有效的承诺。第一次请先试 5 条。识别失败会停下，按[页面适配说明](docs/SELECTORS.md)调整。

## 项目定位

**个人求职信息整理助手（Personal Job Research Assistant）**。

第一阶段只做「推荐岗位 → 本地资料 → 表格筛选」。之后可以扩展本地收藏、去重、求职进度和其他来源的页面适配器。目前没有自动投递、群发招呼、账号托管或跨平台采集功能，也没有实现未来规划中的功能。

GitHub 仓库名建议：`job-pocket`（创建仓库时确认名称可用性）。

仓库简介可用：

> 基于 Python Playwright 的个人求职信息整理助手。手动登录 BOSS 直聘，整理可见推荐岗位与 JD，支持去重、断点续采和 CSV/XLSX 导出，遇到验证或访问限制即停止。

## 已有功能

- 只在你手动确认的推荐列表中读取卡片，不自动搜索、翻页或切换城市/频道。
- 收集岗位名称、薪资原文、城市区域、经验/学历、标签、公司、福利、卡片原文和链接；字段不存在就留空。
- 按卡片实际出现的职位链接，单独打开一个详情标签页，读取可见 JD 和地址。
- 按详情链接中的职位 ID 去重；跟踪参数不影响去重。不同 ID 的同名职位保留，避免误合并。
- SQLite 逐条提交；卡片先保存，随后才打开 JD。中断后保留未完成队列。
- 导出 UTF-8 BOM CSV 和带筛选、冻结表头的 XLSX；导出无需登录、无需联网。
- 默认每次主动访问/滚动间隔 8–15 秒，每处理 20 个 JD 休息 60 秒；列表每 20 轮另有休息。单线程，无自动重试。
- 最多 200 条、最多 80 轮列表扫描、连续 3 轮无新增停止；默认采集阶段最多 120 分钟。
- 验证码、风控提示、登录失效、相关 HTTP 401/403/429/5xx、页面异常或超时均停止，保留已有数据。

延时用于减少主动操作频率，**不保证平台接受自动化访问，也不保证一定能采满 200 条**。按你账号适用的平台规则使用；停止后不要反复重跑来冲击限制。

## 安装

需要 Python 3.10 或以上，Windows、macOS 或带桌面环境的 Linux。浏览器必须能显示窗口。以下命令均在项目文件夹中运行。

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m playwright install chromium
```

Windows PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m playwright install chromium
```

若 PowerShell 禁止激活虚拟环境，可直接用 `.\.venv\Scripts\python.exe` 替换后续命令中的 `python`，无需修改全局执行策略。Linux 缺少浏览器系统库时，可按 Playwright 官方说明执行 `python -m playwright install --with-deps chromium`。

`requirements-tested.txt` 记录交付时实际安装并测试的版本。需要按该版本集复现时，先运行 `python -m pip install -r requirements-tested.txt`，再安装项目和 Chromium。它是已测快照；日常安装默认使用 `pyproject.toml` 中允许的版本范围。

## 第一次采集：先试 5 条

```bash
python -m job_pocket collect --limit 5
```

1. 工具打开独立 Chromium 窗口，使用项目自己的浏览器资料目录。
2. 在**最初打开的同一个标签页**手动登录，进入你自己的首页推荐列表。默认入口是 `https://www.zhipin.com/web/geek/job-recommend`；若平台入口改变，可自行导航，或调整配置。
3. 确认当前内容确实是你的推荐列表，不是搜索结果、公开热门岗位或公司职位页。工具不能代替你辨别推荐标签的业务含义。
4. 回到终端输入 `START`，开始采集。其他输入会取消。无需向工具提供账号密码。
5. 开始后不要在工具窗口中切换列表、筛选或更换账号。详情页会由工具在第二个标签页依次打开。
6. 看见停止原因和导出路径后，检查表格的岗位名称、公司、薪资、JD 是否正确，再扩大到 200 条。

```bash
python -m job_pocket collect --limit 200
```

第一次的 5 条会留在同一数据库里，继续运行会补到**累计** 200 条，不会额外新增 200 条。不要求推荐顺序稳定；重新从当前推荐列表扫描，已收录的职位 ID 跳过。职位未再出现仍保留在本地。

如果推荐页不自动加载下一批，工具会因无新增而停止；不会猜测并点击其他频道、搜索或加载按钮。该情形可以调整滚动容器，不能保证采满。

## 日常使用

开始 / 继续采集：

```bash
python -m job_pocket collect --limit 200
```

只整理卡片，暂不访问 JD：

```bash
python -m job_pocket collect --limit 200 --cards-only
```

卡片的 `JD状态` 保持 `pending`。随后去掉 `--cards-only` 再运行同样命令，优先补采这些 JD；即使已达到 200 条，也会处理尚未完成的 JD。

随时按 **Ctrl+C** 停止。正常中断会关闭浏览器、保存停止原因并尝试导出。若进程被强制结束或电脑掉电，以逐条提交的 SQLite 为准，重新运行 `export` 恢复表格。

查看进度 / 本地重新导出：

```bash
python -m job_pocket status
python -m job_pocket export
```

指定一组独立的数据和登录状态：

```bash
python -m job_pocket --workspace ./my-job-search collect --limit 200
python -m job_pocket --workspace ./my-job-search export
```

`--workspace` 放在子命令之前；默认为**当前工作目录**。换运行目录就会用另一份数据。保持同一 `--workspace` 才是续采。不要让多个工作目录共用同一浏览器资料目录；不要在同一目录混用不同账号。新求职批次或不同账号应使用独立工作目录，并避免提交其中的私人文件。

一次更短的采集：

```bash
python -m job_pocket collect --limit 200 --max-minutes 30
```

时长上限从输入 START 后开始计算，单次页面加载/关闭可能让实际结束略晚。达到任意上限都会保留已有数据，200 是上限，不是成功条数承诺。

## 文件在哪里

```text
job-pocket/
├── src/job_pocket/          程序与内置 CSS 配置
├── tests/                  核心测试与本地合成页面浏览器测试
├── docs/                   字段、适配、发布说明
├── config.example.json     完整配置示例，可公开
├── .private/               本地自动生成，不提交
│   ├── browser-profile/    登录会话/浏览器资料
│   └── run.lock            单实例运行锁
├── data/jobs.sqlite3       本地断点与岗位全文，不提交
└── exports/                本地输出，不提交
    ├── jobs.csv
    └── jobs.xlsx
```

CSV/XLSX 每次使用同名文件替换；**SQLite 是进度和数据的准本**。CSV 与 XLSX 分别原子替换，但不保证二者在同一次系统故障时同时更新；再次 `export` 即可同步。Excel 打开 XLSX 时可能锁文件，关闭后重新导出。

CSV 保留完整长文本；XLSX 受每格 32,767 字符上限约束，截断时在 JD 备注中注明。两个表格都对公式前缀做转义，避免岗位原文被当作表格公式执行；数据库保留原文。默认不采集招聘者姓名、头像、电话、聊天记录或简历内容；卡片/JD 原文中若自带联系方式则可能随原文保存，不应公开。

## 断点与停止行为

- `job_id` 是去重键，每条卡片和每次详情更新各自提交事务。
- `pending` 表示 JD 未完成，包括只采卡片、运行中断、风控和超时。下次显式运行时重新处理。
- `ok` 表示提取到可见 JD。
- `unavailable` 表示详情返回 404/410，不自动重试。
- `no_visible_jd` 表示页面正常打开、渲染等待后未识别到可见 JD，可能是页面改版、内容不开放或加载较慢，不自动重试。可增加等待或修复 CSS 后，在新的工作目录重新采集。
- 续采以本地首次收录的卡片为准；不会刷新已经完成的岗位，也不保证薪资/状态是最新值。需要新快照时换工作目录。
- 遇到风控/验证码不点击、不求解、不刷新、不自动重试；关闭浏览器并返回停止原因。仅在限制已自然解除、确认允许继续时由你决定是否再次运行。
- 不抓取内部接口、不解密签名、不读取隐藏 JSON、不伪装浏览器指纹、不接管日常 Chrome、不切换代理或账号绕过限制。

HTTP 监控只看 `www.zhipin.com` 的 document/xhr/fetch 状态码，不读取响应体；相关请求一旦返回 401/403/429/5xx 就锁定停止。人工登录准备阶段允许正常登录；初始入口的 403/429/5xx 仍会停止。检测是尽力而为：平台未识别的新验证页面可能触发通用页面异常/缺少 JD，而不会被准确命名为风控；也可能因岗位原文含验证提示词而保守停止。

程序的正常停止（包含风险、无新增、用户取消、页面不匹配）返回退出码 0；参数、配置、文件错误返回非零。**退出码 0 不代表采满或实站适配成功**，应查看停止原因、条数和 JD 状态。状态可用 `status` 查询，停止原因也保存在本地数据库。

## 配置与页面变化

```bash
# macOS / Linux
cp config.example.json config.local.json
python -m job_pocket collect --limit 5 --config config.local.json
```

Windows 可用 `Copy-Item config.example.json config.local.json`。也可以只写需要覆盖的项：

```json
{
  "min_delay": 12,
  "max_delay": 20,
  "render_wait_seconds": 4,
  "selectors": {
    "feed_roots": [".your-recommendation-container"]
  }
}
```

此处 CSS 是占位示例，不能直接用于真实页面。完整字段见 `config.example.json`。CSS 使用标准浏览器选择器，不使用 Playwright 特有的 `:visible`。

延时最小值不能低于 5 秒；休息不能低于 30 秒，休息间隔不能超过 20；列表扫描不能超过 100 轮、空轮不能超过 5 轮。`render_wait_seconds` 是导航后的固定渲染等待（1–30 秒），慢页面可适当增加。配置文件不会自动加载，必须显式传入 `--config`。不要为通过限制而缩短延时或删除验证提示。

## 常见问题

**打开的不是推荐页 / 默认入口无效**：在同一个标签页手动导航至推荐列表，看到卡片后再输入 START。配置入口不是对平台固定路由的保证。

**未找到列表或没有卡片**：先确认已登录、推荐标签正确、页面已加载。再按照[适配说明](docs/SELECTORS.md)校准 CSS；工具不会自动退回全站搜索或抓取所有链接。

**几条就停了 / 少于 200 条**：查看停止原因。推荐数量、重复卡片、虚拟列表、页面变化、平台限制都会影响数量，不会为了凑满切换信息来源。

**有卡片没有 JD**：查看 `JD状态`、`JD备注`。`pending` 可续采；下线/不开放/结构不匹配不保证能补齐。JD固定等待结束后才提取，可适当延长渲染等待。

**浏览器提示 executable 不存在**：在运行项目的同一个虚拟环境内执行 `python -m playwright install chromium`。

**显示运行锁**：先确认上次进程已退出、工具浏览器已关闭，再删除 `.private/run.lock`。不要在程序仍运行时删除锁；强制退出后可能留锁，这是为了避免同时使用同一登录资料。

**需要重置或删除本地数据**：程序退出后，删除 `.private/browser-profile/` 会移除工具的本地登录会话；删除 `data/` 会丢弃断点和岗位；删除 `exports/` 会移除导出表格。按需手动操作，不影响日常 Chrome 的资料。

## 开发与验证

```bash
python -m pip install -e '.[dev]'
python -m pytest -q                      # 核心测试；浏览器测试默认跳过
python -m playwright install chromium
python -m pytest --run-browser -q        # 全量离线测试
```

浏览器测试把所有请求路由到本地合成 HTML，不访问 BOSS，不需要账号或密钥。GitHub Actions 在 Python 3.10 / 3.12 / 3.13 上运行这些离线测试；工作流已配置，云端结果以你实际 push 后为准。交付时的本地结果见[验证记录](docs/VALIDATION.md)。

模块分工：`collector.py` 管浏览器、限速和停止；`dom.js` 读取可见页面；`model.py` 规范链接及字段；`store.py` 管断点；`exporter.py` 导出；`config.py` 校验边界。

## 开源发布

已经准备 `.gitignore`、MIT 许可证、离线测试和 CI。首次公开前按[发布指南](docs/PUBLISHING.md)检查实际待提交文件。程序在本地运行；发布仓库时只上传代码、文档与合成测试夹具，不上传登录资料和个人岗位数据。

程序代码的 MIT 许可证不授予平台内容或第三方商标的权利。JobPocket 是独立个人项目，与 BOSS 直聘无隶属关系。

参考实现文档：[Playwright 安装](https://playwright.dev/python/docs/library)、[持久浏览器上下文](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)、[登录状态保存注意事项](https://playwright.dev/python/docs/auth)、[openpyxl](https://openpyxl.readthedocs.io/en/stable/tutorial.html)。
