<div align="center">

# Aseprite MCP

**让 AI 成为你的像素画创作搭档**

通过 Model Context Protocol，在 Aseprite 中绘制、修改和预览像素画。

**中文** · [English](README.en.md)

[![PyPI](https://img.shields.io/pypi/v/aseprite-mcp.svg)](https://pypi.org/project/aseprite-mcp/)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python)](https://pypi.org/project/aseprite-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

Aseprite MCP 将支持 MCP 的客户端如`Codex`，`CluadeCode`，`DeepseekHarness`等Agent与 Aseprite 连接起来，支持读取和编辑未保存画布、图片预览、撤销重做及可选基础动画，让你在同一文档中继续创作。同时保留 CLI 磁盘文件处理能力。

<div align="center">
  <img src="./assets/preview1.gif" style="width: 50%; max-width: 100%; border-radius: 4px;" />
</div>
<div align="center">
  <img src="./assets/preview2.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />
</div>

[PyPI 安装包](https://pypi.org/project/aseprite-mcp/) · [Release 扩展下载](https://github.com/greenlogs/aseprite-mcp-live/releases) · [问题反馈](https://github.com/greenlogs/aseprite-mcp-live/issues)

**Windows Aseprite 1.3+** 验证；Aseprite 需自行安装，不随项目分发。

## 快速开始

确保你已经安装了[aseprite-扩展](#安装-aseprite-扩展)
然后可以使用你常用的ai agent工具输入以下内容：

```text
请帮我安装这个项目https://github.com/greenlogs/aseprite-mcp-live的Aseprite MCP扩展，我的Aseprite已经安装好在[输入你的aseprite.exe 安装路径]，且已经安装了扩展并启用。
```

## 安装 uv（Windows）

在 PowerShell 中运行以下任意一种方式。

**方式一：官方安装脚本**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**方式二：WinGet**

```powershell
winget install --id=astral-sh.uv -e
```

安装后重新打开终端，确认 `uv` 和附带的 `uvx` 可用：

```powershell
uv --version
uvx --version
```

也可以从 [uv 官方 Releases](https://github.com/astral-sh/uv/releases) 下载对应 Windows 架构的压缩包，解压后将可执行文件所在目录加入 `PATH`。更多安装选项见 [uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)。

本项目需要 **Python 3.13+**。可以让 uv 管理所需解释器：

```powershell
uv python install 3.13
```

## 安装 Aseprite 扩展

两种服务启动方式都需要配套扩展：

1. 前往 [GitHub Releases](https://github.com/greenlogs/aseprite-mcp-live/releases)，下载与服务版本一致的 `.aseprite-extension` 文件。当前服务版本为 **0.4.1**。
2. 在 Aseprite 中打开 **Edit → Preferences → Extensions → Add Extension**，选择下载的扩展包，安装并启用。

    <img src="./assets/step1.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />
    <img src="./assets/step2.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />

   查看脚本状态：

    <img src="./assets/step3.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />
    <img src="./assets/step4.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />
    <img src="./assets/step6.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />

   `status` 出现 Connected 状态表示扩展已成功连接服务

    <img src="./assets/step5.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />

3. 重启 Aseprite，首次连接时按权限提示允许扩展使用本机 WebSocket。

`注意事项`：

- 1.若MCP连接正常但获取不到工具状态，尝试重启Agent客户端，尽量先让Aseprite先启动。
- 2.Agent工作时，尽量不要在画布上绘制，以免干扰实时协作。

扩展默认自动连接 `127.0.0.1:8765`。在 **File → Scripts → MCP: Connect / Settings** 中可查看状态、调整端口或断开连接，无需选择连接文件。

## 方式一：通过 uvx 运行（推荐）

直接从 PyPI 获取并运行，无需克隆仓库：

```powershell
uvx --python 3.13 aseprite-mcp
```

以上命令启动 **stdio MCP server**，等待 MCP 客户端输入；终端保持等待属于正常行为。实际使用时，通常由 MCP 客户端按下列配置自动启动服务，无需另外开终端启动第二份。

### MCP 客户端配置

以下适用于采用 `mcpServers` JSON 格式的客户端；其他客户端使用对应的 stdio 配置格式。

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "uvx",
      "args": ["--python", "3.13", "aseprite-mcp"],
      "env": {
        "ASEPRITE_MCP_TOOL_PROFILE": "all",
        "ASEPRITE_MCP_CAPABILITY_SETS": "animation"
      }
    }
  }
}
```

保存配置并重启客户端，然后打开 Aseprite。扩展与服务启动顺序不限，服务就绪后会自动连接。

## 方式二：本地构建与运行

需要 Git；也可以从仓库页面下载源码压缩包，解压后进入项目根目录。

```powershell
git clone https://github.com/greenlogs/aseprite-mcp-live.git
cd aseprite-mcp-live
uv sync --locked --python 3.13
uv run --locked python scripts/build_release.py --out-dir dist
```

`dist/` 中会生成 Python wheel、源码包、`.aseprite-extension`、锁定生产依赖清单和摘要文件。你可以安装对应版本的 Release 扩展，或使用本地生成的扩展包。

在项目根目录启动服务：

```powershell
uv run --locked aseprite-mcp
```

由 MCP 客户端启动本地源码版本时，将配置替换为：

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "uv",
      "args": ["--directory", "{source-path}", "run", "--locked", "aseprite-mcp"],
      "env": {
        "ASEPRITE_MCP_TOOL_PROFILE": "all",
        "ASEPRITE_MCP_CAPABILITY_SETS": "animation"
      }
    }
  }
}
```

将 `source-path` 替换为源码目录的绝对路径如`C:/path/to/aseprite-mcp-live`。选择一种服务配置即可，同一端口只运行一份服务。

## 功能

| 功能                 | 说明                                                          |
| -------------------- | ------------------------------------------------------------- |
| **实时协作**         | 读取和编辑已经打开的文档，包括未保存画布                      |
| **像素与图层**       | 新建 RGB 画布、添加普通图层、调整不透明度、批量绘制像素和矩形 |
| **图片反馈**         | 将预览作为 PNG 图片直接返回给支持图片内容的 MCP 客户端        |
| **撤销与重做**       | 一个成功编辑批次对应一次撤销，沿用 Aseprite 原生历史          |
| **基础动画（可选）** | 追加或删除帧、设置帧时长、创建和管理动画标签                  |
| **CLI 文件工具**     | 单独启用磁盘文件处理，使用保留的上游工具进行批处理            |
| **自动连接**         | 等待服务就绪，并在服务重启后自动重新连接                      |

Python MCP 服务通过 stdio 与客户端通信；Lua 扩展通过本机 WebSocket 连接服务，编辑 Aseprite 中的内存文档。实时编辑绑定明确的文档与修订，切换活动窗口不会改变操作目标。

## 可选配置

### 基础动画

在客户端配置的 `env` 中增加以下项，并重启服务：

```json
{
  "ASEPRITE_MCP_CAPABILITY_SETS": "animation"
}
```

这会额外提供 `apply_animation`。支持追加末帧副本、删除帧、设置帧时长，以及创建、更新和删除标签。帧号从 1 开始，时长使用整数毫秒；每批动画操作支持一次撤销和重做，不自动保存。

### 工具范围与 Aseprite 路径

通过 `ASEPRITE_MCP_TOOL_PROFILE` 选择工具范围：

| 值             | 工具范围                                    |
| -------------- | ------------------------------------------- |
| `all` （默认） | 实时与 CLI 合计 125 个；启用动画后为 126 个 |
| `core`         | 9 个实时核心入口；启用动画后为 10 个        |
| `cli`          | 116 个磁盘文件工具，不建立实时连接          |

```json
{
  "ASEPRITE_PATH": "{你的aseprite应用的绝对路径}",
  "ASEPRITE_MCP_TOOL_PROFILE": "all"
}
```

### 自定义端口

通过启动参数修改服务端口，例如：

```powershell
uvx --python 3.13 aseprite-mcp==0.4.1 --port 8766
```

客户端配置中将 `--port`、`8766` 追加到 `args`，并在扩展设置中把 Port 改为 `8766`。本地源码运行同样支持 `uv run --locked aseprite-mcp --port 8766`。

## 使用范围

- 实时绘制以普通可编辑 RGB 图层为范围；非 RGB、锁定层、背景层、参考层和 Tilemap 等不支持的编辑会明确拒绝。调色板、特效、补间和 Tilemap 尚未迁移为实时能力。
- 编辑不会自动保存；保存为 `.aseprite` 或 `.ase` 时需明确指定路径，覆盖已有文件需显式设置覆盖参数。
- 撤销与重做针对文档最新历史，也可能涉及手动编辑。较大操作可能触发像素、复制或执行时间预算，需要缩小批次。
- 实时后端操作内存文档，CLI 后端操作磁盘文件。断线不会自动切换到 CLI；避免同时通过两种方式写入同一个磁盘文件。
- 服务仅监听本机回环地址。重连后需重新读取文档列表，不能复用旧会话和文档 ID。

## 故障排查

| 问题                 | 处理方式                                                                    |
| -------------------- | --------------------------------------------------------------------------- |
| 找不到 `uv` 或 `uvx` | 安装后重开终端与客户端，或在客户端配置中使用可执行文件的绝对路径            |
| 扩展未连接           | 确认服务已由 MCP 客户端启动、扩展已启用、WebSocket 权限已允许，双方端口一致 |
| 端口被占用           | 关闭重复服务，或同时修改服务与扩展端口                                      |
| 版本不匹配           | 安装同版本的服务和扩展；可使用 `aseprite-mcp==0.4.1` 固定版本               |
| 找不到文档或修订冲突 | 重新读取文档列表与信息，使用当前会话和修订                                  |
| 预览图片未显示       | 确认客户端支持 MCP 图片内容，并缩小预览区域或缩放倍数                       |

如仍有问题，请通过 [GitHub Issues](https://github.com/greenlogs/aseprite-mcp-live/issues) 提交软件版本、启动方式与错误信息。

## 致谢与许可

基于 [diivi/aseprite-mcp](https://github.com/diivi/aseprite-mcp) 的工具与测试基础改造，保留上游 MIT 许可和版权，新增代码同样采用 [MIT 许可](LICENSE)。

本项目为第三方集成，与 Aseprite 官方无隶属关系。Aseprite 需自行准备，不随项目分发。
