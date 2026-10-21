# 动态项目结构

最近复核：2026-10-21，P1-M2 文档及事务验收。结构说明唯一来源；实际与规划分开。

## 实际结构

```text
aseprite-mcp/
├─ .git/                     用户授权建立的本地版本库，main 分支，无远程
├─ Aseprite/                 本地软件与个人数据，忽略、不分发
├─ .work/                    下载、隔离 Python/uv 缓存、测试与包检查输出，忽略
├─ .venv/                    uv 项目环境，忽略
├─ 根目录早期测试画布/图像    以 .gitignore 精确规则忽略，保留本地文件
├─ aseprite_mcp/
│  ├─ __init__.py            上游装饰器注册实例（116 项兼容基线）
│  ├─ __main__.py            stdio 服务命令入口
│  ├─ server.py              默认 core / 可选 cli / all 暴露与 MCP 结果转换
│  ├─ core/
│  │  ├─ commands.py         上游进程/脚本执行；UTF-8、超时及错误
│  │  ├─ protocol.py         v1 请求、批次、目标、结果、PNG、握手与上限类型
│  │  ├─ config.py           回环端点配置、随机启动 token 和环境上限
│  │  ├─ execution.py        Backend 接口、显式路由、单会话、串行与去重
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
├─ extension/                package.json/main.lua 生命周期；bridge.lua 会话去重；editor.lua 文档注册/事务/历史
├─ tests/
│  ├─ conftest.py            平台临时目录和每模块画布夹具
│  ├─ test_environment.py    上游工具枚举、中文路径与真实像素核对
│  ├─ test_protocol.py       协议、错误映射、模拟 live、去重与样例
│  ├─ test_cli_backend.py    真实 CLI 纵向路径与进程/产物故障模拟
│  ├─ live_support.py        独立 UI 进程与仅测试使用的手工动作控制夹具
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
   ├─ TESTING.md             配置、真实命令、测试分层与集成步骤
   ├─ development/
   │  ├─ README.md           开发约定
   │  ├─ ARCHITECTURE.md     架构决策与实际/未来边界
   │  ├─ PROTOCOL.md         协议 v1 字段、默认值、错误、PNG 与兼容约定
   │  ├─ protocol-v1.examples.json
   │  │                      可由契约测试校验的握手/请求/结果样例
   │  ├─ MODULE_REPORT_TEMPLATE.md
   │  └─ prompts/            P0、P1、P2、P3 模块提示词
   └─ progress/              P0～P3 阶段总结、P0-M1 / P0-M2 / P1-M1 / P1-M2 交接报告
```

依赖方向：`__main__` → `server` → Request / Executor → CliBackend → commands / 固定 Lua → Aseprite CLI。旧兼容工具 → 共享算法/commands，尚未全部迁移到 Executor。live Backend 已实现同一 Backend 协议，通过 WebSocket 接入扩展；当前协商七种文档/事务动作。协议层不导入工具或后端。

## 当前入口

| 入口 | 实际位置或状态 |
|---|---|
| 启动 | `uv run --locked python -m aseprite_mcp`；或 `uv run --locked aseprite-mcp`，stdio |
| 工具配置 | `ASEPRITE_MCP_TOOL_PROFILE=core`（默认 9）/cli（116）/all（125）；原始 Lua 额外显式开启 |
| 依赖同步 | `uv sync --locked --python 3.13` |
| 测试 | `uv run --locked pytest -q --basetemp=.work/pytest`；详见 [TESTING](TESTING.md) |
| 公共 CLI 路径 | Python Executor.execute(JSON) 或 CLI 配置的 MCP cli_execute |
| 构建 | `uv build --out-dir .work/build`；hatchling；包资源已检查，P2 发布/干净安装验收未执行 |
| 扩展加载 | extension/package.json → main.lua init/exit；设置对话框选择服务发现 JSON；core/all lifespan 监听 |
| 下一模块 | [P1-M3](development/prompts/P1-实时核心闭环.md#p1-m3) |

## 规划结构：尚未实现

P1-M3 将扩充现有扩展的 PNG 预览模块。`scripts/` 扩展打包、`.github/workflows/` 自动检查及正式发布入口在 P2。高级能力按 P3 清单迁移；尚未存在的目录不是可运行入口。

## 复核记录与更新规则

P0-M1 导入上游源码、测试和环境入口；P0-M2 增加协议/配置/执行层、CLI 适配器、服务暴露及契约测试，入口已实际验收。每次模块交付检查实际文件、入口、职责、依赖后同步本文件，记录日期和模块号；模块报告、根计划与阶段总结同步状态，不承诺后台自动更新。

2026-10-21 Git 复核：用户单独授权初始化并创建一次本地提交；已建立 `.git/`，补充早期根目录测试产物忽略规则，产品职责和启动/测试/打包入口无变化。


2026-10-21 P1-M1：新增 live.py、extension/ 与 test_live_bridge.py；FastMCP lifespan 实际监听回环端口，websockets 15.0.1；真实 UI 扩展生命周期通过。

2026-10-21 P1-M2：新增 editor.lua、live_support.py 和 test_live_editor.py；实时文档注册、事件修订、事务/历史/原生保存已真实验证。
