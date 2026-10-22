# 动态项目结构

最近复核：2026-10-22，DOCS-M3 英文 README 同步。结构说明唯一来源；实际与规划分开。

## 实际结构

```text
aseprite-mcp/
├─ .git/                     用户授权建立的本地版本库，main 分支，origin 指向用户指定 GitHub 仓库
├─ Aseprite/                 本地软件与个人数据，忽略、不分发
├─ .work/                    隔离 Python/安装环境、验收日志/XML、P1/P2 图片、release 候选和清理记录，忽略
├─ .venv/                    uv 项目环境，忽略
├─ .github/workflows/check.yml Windows 契约/文档/打包 CI，测试前创建 .work，无 GUI 或自动发布步骤
├─ scripts/
│  ├─ build_release.py      uv 构建、确定性扩展 ZIP、生产依赖及分发清单校验
│  ├─ check_capabilities.py 逐工具兼容矩阵与实际注册核对
│  ├─ check_docs.py         Markdown 本地链接、服务入口及模块索引检查
│  └─ verify_install.py     独立 Windows 安装验收脚本，真实 MCP SDK/UI 与图片证据
├─ aseprite_mcp/
│  ├─ __init__.py            上游装饰器注册实例（116 项兼容基线）
│  ├─ __main__.py            stdio 入口、--host/--port 参数与配置优先级
│  ├─ server.py              core/cli/all、listener 生命周期与 MCP 文本/图片内容转换
│  ├─ core/
│  │  ├─ commands.py         上游进程/脚本执行；UTF-8、超时及错误
│  │  ├─ protocol.py         v1 请求、批次、目标、结果、PNG、握手与上限类型
│  │  ├─ config.py           回环/默认固定端口、CLI/环境优先级与上限；不使用发现文件
│  │  ├─ execution.py        Backend 接口、按资源队列、取消后确认、会话及去重
│  │  ├─ files.py            CLI/旧工具共享的有限期线程磁盘锁
│  │  ├─ legacy.py           旧 MCP CLI 工具的 worker 包装及失败映射
│  │  ├─ lua.py              上游可复用 Lua 片段
│  │  ├─ colors.py           颜色解析
│  │  ├─ fonts.py            字体发现及光栅化
│  │  ├─ native.py           本机滤镜命令辅助
│  │  └─ __init__.py         共享模块包
│  ├─ backends/
│  │  ├─ __init__.py         后端包
│  │  ├─ cli.py              受控线程、JSON 参数、nonce 回执、文件提交与清理
│  │  ├─ live.py             回环 WebSocket直连、原生Origin校验与在线请求关联
│  │  └─ cli.lua             固定磁盘读取及批量普通 RGB 图层编辑脚本
│  └─ tools/                 20 个上游 CLI 工具模块及 __init__.py，原名/参数保留
├─ extension/
│  ├─ package.json           注册 main.lua 的 0.4.1 发布扩展清单
│  ├─ NOTICE.md              扩展包上游固定提交与许可归属
│  ├─ main.lua               init/exit、延迟自动连接、菜单与重载清理
│  ├─ bridge.lua             地址/端口设置、直接连接/重连/停止、握手与编辑端去重；无选文件UI
│  ├─ editor.lua             文档/图层注册、事件修订、事务/历史与保存
│  ├─ animation.lua          可选基础动画、元数据指纹、预算及顺序预校验
│  └─ preview.lua            独立 Image 合成与内存 PNG/base64 编码
├─ tests/
│  ├─ conftest.py            平台临时目录和每模块画布夹具
│  ├─ test_environment.py    上游工具枚举、中文路径与真实像素核对
│  ├─ test_auto_connection.py 默认/CLI配置、无文件契约/Origin和真实UI/服务重启直连
│  ├─ test_reliability.py   取消/断线/迟到回执/磁盘修订及真实 UI 故障恢复
│  ├─ test_protocol.py       协议、错误映射、模拟 live、去重与样例
│  ├─ test_cli_backend.py    真实 CLI 纵向路径与进程/产物故障模拟
│  ├─ live_support.py        独立 UI 进程与仅测试使用的手工动作控制夹具
│  ├─ test_live_preview.py   真实 MCP 图片/阶段集成与真实上限拒绝
│  ├─ test_live_animation.py 可选能力契约与真实MCP/UI/CLI/关联Cel/历史回归
│  ├─ test_live_editor.py    真实文档、Cel、事务回滚、历史与保存
│  ├─ test_live_bridge.py    真实 socket 模拟编辑器及真实 UI 扩展生命周期
│  ├─ test_server.py         工具配置、真实 stdio 及 MCP→真实 CLI 读取
│  └─ test_*.py              121 个上游基线测试（20 个测试文件）
├─ pyproject.toml            Python 依赖、构建、脚本和测试入口
├─ uv.lock                   锁定依赖
├─ .python-version           目标解释器 3.13
├─ .env.example              ASEPRITE_PATH、工具配置及全部上限示例
├─ .gitignore                软件、个人配置、缓存与产物隔离
├─ LICENSE                   原始上游 MIT 声明
├─ README.md                 中文使用者入口，Windows uv、PyPI uvx/本地构建、Release 扩展与配置；不引用内部文档
├─ README.en.md              英文使用者入口，与中文版互链并纳入源码包
├─ assets/                   用户提供的 step1.png～step5.png 安装与连接截图，两版 README 共用
├─ CONTRIBUTING.md           贡献入口
├─ AGENTS.md                 协作规则
├─ EXECUTION_PLAN.md          执行与状态入口
└─ docs/
   ├─ PROJECT_STRUCTURE.md   本结构说明
   ├─ REFERENCES.md          本机环境与官方资料
   ├─ THIRD_PARTY.md         实际导入及许可记录
   ├─ upstream-manifest.json 原始导入文件、tree 和摘要
   ├─ INSTALL.md             wheel/锁定依赖/扩展安装、MCP 配置及使用规则
   ├─ TROUBLESHOOTING.md     故障码、环境/安装/重连诊断
   ├─ RELEASING.md           本地候选构建、清单及真实验收/远程边界
   ├─ TESTING.md             配置、真实命令、测试分层与集成步骤
   ├─ development/
   │  ├─ README.md           开发约定
   │  ├─ CAPABILITIES.md     P3兼容抽查与冻结批次
   │  ├─ tool-compatibility.json 全部116项工具/上游复核证据矩阵
   │  ├─ ARCHITECTURE.md     架构决策与实际/未来边界
   │  ├─ PROTOCOL.md         协议 v1 字段、默认值、错误、PNG 与兼容约定
   │  ├─ protocol-v1.examples.json
   │  │                      可由契约测试校验的握手/请求/结果样例
   │  ├─ MODULE_REPORT_TEMPLATE.md
   │  └─ prompts/            P0、P1、P2、P3 模块提示词
   └─ progress/              P0～P3 阶段总结及模块交接；DOCS.md 文档维护总结、DOCS-M1/M2/M3 中英 README 交接
```

依赖方向：`__main__` → `server` → Request / Executor → CliBackend → commands / 固定 Lua → Aseprite CLI。旧兼容工具 → 共享算法/commands，尚未全部迁移到 Executor。live Backend 已实现同一 Backend 协议，通过 WebSocket 接入扩展；默认协商八种文档/事务/图片动作，可显式增加apply_animation。协议层不导入工具或后端。

## 当前入口

| 入口 | 实际位置或状态 |
|---|---|
| 启动 | PyPI：`uvx --python 3.13 aseprite-mcp==0.4.1`；源码：`uv run --locked python -m aseprite_mcp` 或 `uv run --locked aseprite-mcp [--host 127.0.0.1] [--port 8765]`，均为 stdio |
| 工具配置 | `ASEPRITE_MCP_TOOL_PROFILE=core`（默认 9）/cli（116）/all（125）；原始 Lua 额外显式开启 |
| 依赖同步 | `uv sync --locked --python 3.13` |
| 测试 | `uv run --locked pytest -q --basetemp=.work/pytest`；详见 [TESTING](TESTING.md) |
| 公共 CLI 路径 | Python Executor.execute(JSON) 或 CLI 配置的 MCP cli_execute |
| 构建 | `uv run --locked python scripts/build_release.py --out-dir dist`；wheel/sdist/扩展/锁定依赖/摘要 |
| 扩展加载 | `.aseprite-extension` 安装或解压至配置 extensions/aseprite-mcp-live；main.lua init/exit；默认直接连接 127.0.0.1:8765，设置可改端口 |
| 维护入口 | [兼容清单](development/CAPABILITIES.md)，P3基础动画完成后评估下一独立批次 |

## 规划结构：尚未实现

基础动画已建立；其余高级能力为P3清单明确的后续范围。正式 PyPI 0.4.1 已公开；用户已发布扩展 Release，README 使用 origin 对应 Release 列表入口，匿名访问 404、具体附件未复核。scripts 与 Windows CI 配置已建立；下载日志确认远程 CI 已运行并因缺少 .work 失败，PACK-M3 本地修复验证通过，远程重跑待执行。

## 复核记录与更新规则

P0-M1 导入上游源码、测试和环境入口；P0-M2 增加协议/配置/执行层、CLI 适配器、服务暴露及契约测试，入口已实际验收。每次模块交付检查实际文件、入口、职责、依赖后同步本文件，记录日期和模块号；模块报告、根计划与阶段总结同步状态，不承诺后台自动更新。

2026-10-21 Git 复核：用户单独授权初始化并创建一次本地提交；已建立 `.git/`，补充早期根目录测试产物忽略规则，产品职责和启动/测试/打包入口无变化。

2026-10-21 清理复核：按用户授权删除根目录 12 个早期测试画布/图像、历次 pytest 临时目录、项目/测试 Python 字节码与 pytest 缓存、构建包、上游下载副本、uv 下载缓存及已确认无提交/对象的空 Git 初始化备份。保留 `.venv/` 及其依赖的 `.work/python/`、本地 Aseprite、验收日志/XML、已入库来源清单和全部源码/测试。`.work/` 后续可再生成临时缓存和测试输出，使用后按需清理；产品模块、职责和入口无变化。

2026-10-21 P1-M1：新增 live.py、extension/ 与 test_live_bridge.py；FastMCP lifespan 实际监听回环端口，websockets 15.0.1；真实 UI 扩展生命周期通过。

2026-10-21 P1-M2：新增 editor.lua、live_support.py 和 test_live_editor.py；实时文档注册、事件修订、事务/历史/原生保存已真实验证。

2026-10-21 P1-M3：新增 preview.lua 与 test_live_preview.py；独立图像内存编码 PNG，MCP 返回图片内容，实际客户端图片渲染及 179 项全量回归通过。清理重复测试目录，保留 .work/p1-evidence 四图/截图/测量及验收日志。

2026-10-21 P2-M1：新增 core/files.py、core/legacy.py 与 test_reliability.py；执行器按资源排队并保留取消后回执，CLI 摘要契约/输出解码、事务 CPU/复制预算与随机发现路径已实现并真实验证。

2026-10-21 P2-M2：新增 scripts 三个构建/文档/安装验收入口、Windows CI 配置、扩展 NOTICE 及安装/故障/发布文档；hatch 白名单限定服务与源码分发，扩展包含根部清单和四个 Lua；服务/扩展版本进入状态与兼容校验。

P2 阶段复核：191 项完整 Windows 回归，独立 site-packages/扩展 ZIP/MCP SDK 双启动入口及图片显示通过；0.1.0 候选已验收未发布，其他平台未验证。

2026-10-21 P2-M3：固定默认端口 8765，命令行优先配置；运行凭据按 host/port 原子发布，扩展 Timer 自动读取/重连，停止和退出清理。服务/扩展版本 0.2.0，新增自动连接专项，独立安装验收改用产品启动逻辑。

P2-M3 验收复核：197项全量、61项无软件检查、真实强杀重启自动恢复和0.2.0独立安装/图片显示通过。候选 .work/release-auto，证据 .work/auto-evidence，未推送或发布。

2026-10-22 P2-M4：移除发现目录/连接文件/token及Legacy JSON UI；原生WebSocket直接连接配置端点，连接关闭/错误由Timer重建；全部实时夹具与独立安装验收移除读文件/传凭据路径。旧历史结构记录仅描述当时版本，不代表当前能力。

P2-M4验收复核：197项全量、61项无软件检查、真实无文件读取/强杀重启/独立安装和客户端图片显示通过。当前候选.work/release-direct，证据.work/direct-evidence；0.3.0未发布。

2026-10-22 P3-M1：新增兼容说明、逐工具 JSON 矩阵和 check_capabilities.py；116 项与实际 CLI 注册逐项一致，冻结基础动画批次，无产品能力变化。

2026-10-22 P3-M2：新增animation.lua与test_live_animation.py；config/protocol/server/live新增可选animation能力集，editor补时间轴指纹与删除帧上下文恢复。打包纳入第五个Lua，verify_install支持--port/--animation；实时测试夹具支持独立测试端口，CI纳入动画契约与矩阵校验。

2026-10-22 DOCS-M1：README.md 重写为中文公开使用入口，新增 README.en.md 英文入口并互链；新增文档维护总结及交接。pyproject.toml 的 sdist 清单纳入英文 README，保留源码包中的语言切换目标；产品模块、依赖、版本及启动/测试入口无变化。

2026-10-22 PACK-M1：源码分发改为运行源码、Lua扩展、build_release.py、构建/锁文件、环境样例、README及MIT许可白名单。wheel/sdist/扩展统一拒绝docs、提示词、AGENTS/SKILL、执行计划和CONTRIBUTING；测试、CI及其他开发脚本不进入源码分发，完整开发测试从Git仓库运行。新增PACK.md/PACK-M1.md分发维护交接；origin为git@github.com:greenlogs/aseprite-mcp-live.git。仓库中的维护文档仍保留。

2026-10-22 PACK-M2：服务/扩展/握手/样例统一0.4.1，新增PACK-M2发布交接；当前产物在dist，wheel和sdist已发布TestPyPI并核对公开SHA256，扩展包仍在本地。无产品目录/职责或启动入口变化，保持PACK-M1分发排除规则。

2026-10-22 PACK-M3：check.yml 在 pytest 前创建被忽略的 .work 父目录；TESTING 同步手工复现步骤。新增 PACK-M3 交接并同步分发维护总结和根计划；无产品目录、公共接口或依赖变化。本地干净副本71项检查及文档/能力/打包通过，远程修复重跑未执行。
