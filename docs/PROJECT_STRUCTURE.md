# 动态项目结构

最近复核：2026-10-21，P2-M2 安装打包及阶段集成验收。结构说明唯一来源；实际与规划分开。

## 实际结构

```text
aseprite-mcp/
├─ .git/                     用户授权建立的本地版本库，main 分支，无远程
├─ Aseprite/                 本地软件与个人数据，忽略、不分发
├─ .work/                    隔离 Python/安装环境、验收日志/XML、P1/P2 图片、release 候选和清理记录，忽略
├─ .venv/                    uv 项目环境，忽略
├─ 根目录早期测试画布/图像    以 .gitignore 精确规则忽略，保留本地文件
├─ .github/workflows/check.yml Windows 契约/文档/打包 CI，无 GUI 或自动发布步骤
├─ scripts/
│  ├─ build_release.py      uv 构建、确定性扩展 ZIP、生产依赖及分发清单校验
│  ├─ check_docs.py         Markdown 本地链接、服务入口及模块索引检查
│  └─ verify_install.py     独立 Windows 安装验收脚本，真实 MCP SDK/UI 与图片证据
├─ aseprite_mcp/
│  ├─ __init__.py            上游装饰器注册实例（116 项兼容基线）
│  ├─ __main__.py            stdio 服务命令入口
│  ├─ server.py              core/cli/all、listener 生命周期与 MCP 文本/图片内容转换
│  ├─ core/
│  │  ├─ commands.py         上游进程/脚本执行；UTF-8、超时及错误
│  │  ├─ protocol.py         v1 请求、批次、目标、结果、PNG、握手与上限类型
│  │  ├─ config.py           回环端点配置、随机启动 token 和环境上限
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
│  │  ├─ live.py             回环 WebSocket、发现文件与在线请求关联
│  │  └─ cli.lua             固定磁盘读取及批量普通 RGB 图层编辑脚本
│  └─ tools/                 20 个上游 CLI 工具模块及 __init__.py，原名/参数保留
├─ extension/
│  ├─ package.json           注册 main.lua 的 0.1.0 发布扩展清单
│  ├─ NOTICE.md              扩展包上游固定提交与许可归属
│  ├─ main.lua               init/exit、连接/断开菜单与重载清理
│  ├─ bridge.lua             设置、主动 WebSocket 握手/会话与编辑端去重
│  ├─ editor.lua             文档/图层注册、事件修订、事务/历史与保存
│  └─ preview.lua            独立 Image 合成与内存 PNG/base64 编码
├─ tests/
│  ├─ conftest.py            平台临时目录和每模块画布夹具
│  ├─ test_environment.py    上游工具枚举、中文路径与真实像素核对
│  ├─ test_reliability.py   取消/断线/迟到回执/磁盘修订及真实 UI 故障恢复
│  ├─ test_protocol.py       协议、错误映射、模拟 live、去重与样例
│  ├─ test_cli_backend.py    真实 CLI 纵向路径与进程/产物故障模拟
│  ├─ live_support.py        独立 UI 进程与仅测试使用的手工动作控制夹具
│  ├─ test_live_preview.py   真实 MCP 图片/阶段集成与真实上限拒绝
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
├─ README.md                 使用者入口
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
   │  ├─ ARCHITECTURE.md     架构决策与实际/未来边界
   │  ├─ PROTOCOL.md         协议 v1 字段、默认值、错误、PNG 与兼容约定
   │  ├─ protocol-v1.examples.json
   │  │                      可由契约测试校验的握手/请求/结果样例
   │  ├─ MODULE_REPORT_TEMPLATE.md
   │  └─ prompts/            P0、P1、P2、P3 模块提示词
   └─ progress/              P0～P3 阶段总结、P0/P1/P2 各模块交接报告
```

依赖方向：`__main__` → `server` → Request / Executor → CliBackend → commands / 固定 Lua → Aseprite CLI。旧兼容工具 → 共享算法/commands，尚未全部迁移到 Executor。live Backend 已实现同一 Backend 协议，通过 WebSocket 接入扩展；当前协商八种文档/事务/图片动作。协议层不导入工具或后端。

## 当前入口

| 入口 | 实际位置或状态 |
|---|---|
| 启动 | `uv run --locked python -m aseprite_mcp`；或 `uv run --locked aseprite-mcp`，stdio |
| 工具配置 | `ASEPRITE_MCP_TOOL_PROFILE=core`（默认 9）/cli（116）/all（125）；原始 Lua 额外显式开启 |
| 依赖同步 | `uv sync --locked --python 3.13` |
| 测试 | `uv run --locked pytest -q --basetemp=.work/pytest`；详见 [TESTING](TESTING.md) |
| 公共 CLI 路径 | Python Executor.execute(JSON) 或 CLI 配置的 MCP cli_execute |
| 构建 | `uv run --locked python scripts/build_release.py --out-dir dist`；wheel/sdist/扩展/锁定依赖/摘要 |
| 扩展加载 | `.aseprite-extension` 安装或解压至配置 extensions/aseprite-mcp-live；main.lua init/exit；设置选择发现 JSON |
| 下一模块 | [P3-M1](development/prompts/P3-高级能力迁移.md#p3-m1)，尚未开始 |

## 规划结构：尚未实现

高级能力按 P3 清单迁移；远程发布入口未建立且不自动执行。scripts 与 Windows CI 配置已建立，远程 CI 未执行。

## 复核记录与更新规则

P0-M1 导入上游源码、测试和环境入口；P0-M2 增加协议/配置/执行层、CLI 适配器、服务暴露及契约测试，入口已实际验收。每次模块交付检查实际文件、入口、职责、依赖后同步本文件，记录日期和模块号；模块报告、根计划与阶段总结同步状态，不承诺后台自动更新。

2026-10-21 Git 复核：用户单独授权初始化并创建一次本地提交；已建立 `.git/`，补充早期根目录测试产物忽略规则，产品职责和启动/测试/打包入口无变化。


2026-10-21 P1-M1：新增 live.py、extension/ 与 test_live_bridge.py；FastMCP lifespan 实际监听回环端口，websockets 15.0.1；真实 UI 扩展生命周期通过。

2026-10-21 P1-M2：新增 editor.lua、live_support.py 和 test_live_editor.py；实时文档注册、事件修订、事务/历史/原生保存已真实验证。

2026-10-21 P1-M3：新增 preview.lua 与 test_live_preview.py；独立图像内存编码 PNG，MCP 返回图片内容，实际客户端图片渲染及 179 项全量回归通过。清理重复测试目录，保留 .work/p1-evidence 四图/截图/测量及验收日志。

2026-10-21 P2-M1：新增 core/files.py、core/legacy.py 与 test_reliability.py；执行器按资源排队并保留取消后回执，CLI 摘要契约/输出解码、事务 CPU/复制预算与随机发现路径已实现并真实验证。

2026-10-21 P2-M2：新增 scripts 三个构建/文档/安装验收入口、Windows CI 配置、扩展 NOTICE 及安装/故障/发布文档；hatch 白名单限定服务与源码分发，扩展包含根部清单和四个 Lua；服务/扩展版本进入状态与兼容校验。

P2 阶段复核：191 项完整 Windows 回归，独立 site-packages/扩展 ZIP/MCP SDK 双启动入口及图片显示通过；0.1.0 候选已验收未发布，其他平台未验证。
