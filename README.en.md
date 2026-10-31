<div align="center">

# Aseprite MCP

**Make AI your pixel art creative partner**

Draw, edit, and preview pixel art in Aseprite through the Model Context Protocol.

[中文](README.md) · **English**

[![PyPI](https://img.shields.io/pypi/v/aseprite-mcp.svg)](https://pypi.org/project/aseprite-mcp/)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python)](https://pypi.org/project/aseprite-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

Aseprite MCP connects MCP-compatible clients and agents, such as `Codex`, `Claude Code`, and `DeepseekHarness`, to Aseprite. It supports reading and editing unsaved canvases in real time, image previews, undo and redo, and optional basic animation, so you can keep creating in the same document. CLI tools for processing files on disk are also retained.

<table>
  <tr>
    <td align="center"><img src="./assets/preview1.gif" width="30%" style="border-radius:4px;"/><br/>Real-time animation drawing</td>
    <td align="center"><img src="./assets/display3.png" width="50%" style="border-radius:4px;"/><br/>Real-time scene drawing preview</td>
    <td align="center"><img src="./assets/display2.png" width="50%" style="border-radius:4px;"/><br/>Item drawing</td>
  </tr>
  <tr>
    <td align="center"><img src="./assets/display1.png" width="50%" style="border-radius:4px;"/><br/>Real-time marquee selection and region editing</td>
  </tr>
</table>

[Install from PyPI](https://pypi.org/project/aseprite-mcp/) · [Download the Extension from Releases](https://github.com/greenlogs/aseprite-mcp-live/releases) · [Report an Issue](https://github.com/greenlogs/aseprite-mcp-live/issues)

Tested with **Aseprite 1.3+ on Windows**. Aseprite must be installed separately and is not distributed with this project.

## Quick Start

Make sure you have installed the [Aseprite extension](#install-the-aseprite-extension).
Then enter the following prompt in your preferred AI agent tool:

```text
Please help me install the Aseprite MCP integration from https://github.com/greenlogs/aseprite-mcp-live. Aseprite is already installed at [enter the installation path to your aseprite.exe], and I have already installed and enabled the extension.
```

## Install uv (Windows)

Run either of the following commands in PowerShell.

**Option 1: Official installation script**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Option 2: WinGet**

```powershell
winget install --id=astral-sh.uv -e
```

After installation, reopen your terminal and verify that `uv` and the bundled `uvx` are available:

```powershell
uv --version
uvx --version
```

You can also download the archive for your Windows architecture from the [official uv releases](https://github.com/astral-sh/uv/releases), extract it, and add the directory containing the executables to `PATH`. For more options, see the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

This project requires **Python 3.13+**. You can let uv manage the required interpreter:

```powershell
uv python install 3.13
```

## Install the Aseprite Extension

Both server startup methods require the companion extension:

1. Go to [GitHub Releases](https://github.com/greenlogs/aseprite-mcp-live/releases) and download the `.aseprite-extension` file that matches your server version. The current server version is **0.5.1**.
2. In Aseprite, open **Edit → Preferences → Extensions → Add Extension**, select the downloaded extension package, then install and enable it.

    <img src="./assets/step2.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />

   Check the script status:

    <img src="./assets/step3.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />
    <img src="./assets/step4.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />
    <img src="./assets/step6.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />

   When `status` shows Connected, the extension has successfully connected to the server.

    <img src="./assets/step5.png" style="width: 50%; max-width: 100%; border-radius: 4px;" />

3. Restart Aseprite. On the first connection, follow the permission prompt to allow the extension to use a local WebSocket connection.

**Notes:**

- Avoid drawing on the canvas while the agent is working, as this may interfere with real-time collaboration.
- Make sure the extension and server versions match. Otherwise, connections may fail or features may behave unexpectedly.

By default, the extension automatically connects to `127.0.0.1:8765`. Open **File → Scripts → MCP: Connect / Settings** to check the status, change the port, or disconnect. No connection file needs to be selected.

## Option 1: Run with uvx (Recommended)

Download and run directly from PyPI without cloning the repository:

```powershell
uvx --python 3.13 aseprite-mcp
```

This command starts a **stdio MCP server** and waits for input from an MCP client. It is normal for the terminal to remain waiting. In practice, the MCP client usually starts the server automatically using the configuration below, so you do not need to launch a second instance in a separate terminal.

### MCP Client Configuration

The following configuration applies to clients that use the `mcpServers` JSON format. For other clients, use their corresponding stdio configuration format.

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "uvx",
      // Sharing is enabled by default in 0.5.1; --shared is a compatibility flag and can be omitted.
      "args": ["--python", "3.13", "aseprite-mcp", "--shared"],
      "env": {
        // The core tool profile is enabled by default. Other options are all and cli.
        "ASEPRITE_MCP_TOOL_PROFILE": "core",
        // Enable animation capabilities for the core profile.
        "ASEPRITE_MCP_CAPABILITY_SETS": "animation"
      }
    }
  }
}
```

Save the configuration and restart the client, then open Aseprite. You can start the extension and server in either order; they will connect automatically once the server is ready.

## Option 2: Build and Run Locally

Git is required. Alternatively, download the source archive from the repository page, extract it, and open the project root directory.

```powershell
git clone https://github.com/greenlogs/aseprite-mcp-live.git
cd aseprite-mcp-live
uv sync --locked --python 3.13
uv run --locked python scripts/build_release.py --out-dir dist
```

This generates a Python wheel, a source distribution, and an `.aseprite-extension` package in `dist/`.

Start the server from the project root:

```powershell
uv run --locked aseprite-mcp
```

To have your MCP client start the local source version, replace the configuration with:

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "uv",
      "args": ["--directory", "{source-path}", "run", "--locked", "aseprite-mcp"],
      "env": {
        "ASEPRITE_MCP_TOOL_PROFILE": "core",
        "ASEPRITE_MCP_CAPABILITY_SETS": "animation"
      }
    }
  }
}
```

Replace `source-path` with the absolute path to your source directory, such as `C:/path/to/aseprite-mcp-live`. Choose one server configuration; run only one server instance per port.

## Features

| Feature                        | Description                                                                                        |
| ------------------------------ | -------------------------------------------------------------------------------------------------- |
| **Real-time collaboration**    | Read and edit open documents, including unsaved canvases                                           |
| **Pixels and layers**          | Create RGB canvases, add regular layers, adjust opacity, and draw pixels and rectangles in batches |
| **Image feedback**             | Return previews directly as PNG images to MCP clients that support image content                   |
| **Undo and redo**              | Each successful editing batch corresponds to one undo step in Aseprite's native history            |
| **Basic animation (optional)** | Append or delete frames, set frame durations, and create and manage animation tags                 |
| **CLI file tools**             | Enable disk file processing separately and use the retained upstream tools for batch processing    |
| **Automatic connection**       | Wait for the server to become ready and reconnect automatically after a server restart             |

The Python MCP server communicates with the client over stdio. The Lua extension connects to the server over a local WebSocket and edits documents in Aseprite's memory. Real-time edits are bound to a specific document and revision, so switching the active window does not change the operation target.

## Optional Configuration

### Additional Tools

For a detailed tool list, see the [tool reference](assets/tools.md).

Enable only the capabilities your project needs to reduce unnecessary context. Add the following entry to `env` in your client configuration, then restart the server:

```json
{
  // Enable animation editing.
  "ASEPRITE_MCP_CAPABILITY_SETS": "animation"
}
```

This adds the `apply_animation` tool. It supports appending copies of the last frame, deleting frames, setting frame durations, and creating, updating, and deleting tags. Frame numbers start at 1, and durations are specified in integer milliseconds. Each batch of animation operations supports a single undo/redo step and does not save automatically.

### Tool Profiles and Aseprite Path

Use `ASEPRITE_MCP_TOOL_PROFILE` to select the available tools:

| Value            | Available Tools                                     |
| ---------------- | --------------------------------------------------- |
| `all`            | Enables both core and CLI tools                     |
| `core` (default) | Currently provides 9 core real-time tools           |
| `cli`            | 116 disk file tools, without a real-time connection |

```json
{
  "ASEPRITE_PATH": "{absolute path to your Aseprite executable}",
  "ASEPRITE_MCP_TOOL_PROFILE": "all"
}
```

### Custom Port

Use a startup argument to change the server port. For example:

```powershell
uvx --python 3.13 aseprite-mcp==0.5.1 --port 8766
```

Append `--port` and `8766` to `args` in the client configuration, and change Port to `8766` in the extension settings. When running from local source, you can also use `uv run --locked aseprite-mcp --port 8766`.

### Arguments

| Argument   | Purpose                                                                                                               |
| ---------- | --------------------------------------------------------------------------------------------------------------------- |
| `--shared` | Compatibility flag for shared mode; real-time connections are shared by default in 0.5.1, so this flag can be omitted |

## Scope and Limitations

- Real-time drawing supports regular, editable RGB layers. Unsupported edits, including those involving non-RGB documents, locked layers, background layers, reference layers, or tilemaps, are explicitly rejected. Palettes, effects, tweening, and tilemaps have not yet been ported to real-time capabilities.
- Edits are not saved automatically. Saving as `.aseprite` or `.ase` requires an explicit path, and overwriting an existing file requires an explicit overwrite parameter.
- Undo and redo operate on the document's latest history and may also affect manual edits. Large operations may exceed pixel, copy, or execution-time budgets; reduce the batch size if this happens.
- The real-time backend operates on documents in memory, while the CLI backend operates on files on disk. A disconnection does not trigger an automatic switch to CLI. Avoid writing to the same disk file through both backends at the same time.
- The server listens only on the local loopback address. After reconnecting, read the document list again; old session and document IDs cannot be reused.

## Troubleshooting

| Problem                                 | Solution                                                                                                                                                  |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv` or `uvx` not found                 | Reopen the terminal and client after installation, or use the executable's absolute path in the client configuration                                      |
| Extension not connected                 | Confirm that the MCP client has started the server, the extension is enabled, WebSocket permission has been granted, and both sides use the same port     |
| Port already in use                     | The current source version shares connections by default. If an older, non-shared server or another program is using the port, stop it or change the port |
| `Transport closed`                      | The previous MCP channel has ended. Re-establish the client connection using shared mode, and restart the client if necessary                             |
| Version mismatch                        | Install matching server and extension versions. Use `aseprite-mcp==0.5.1` to pin the server version                                                       |
| Document not found or revision conflict | Read the document list and information again, then use the current session and revision                                                                   |
| Preview image not displayed             | Confirm that the client supports MCP image content, and reduce the preview region or scale factor                                                         |

If the problem persists, open a [GitHub issue](https://github.com/greenlogs/aseprite-mcp-live/issues) with your software versions, startup method, and error details.

## Acknowledgments and License

This project builds on the tools and testing foundation of [diivi/aseprite-mcp](https://github.com/diivi/aseprite-mcp). The upstream MIT license and copyright notices are retained, and new code is also released under the [MIT License](LICENSE).

This project is a third-party integration and is not affiliated with the official Aseprite project. You must obtain Aseprite separately; it is not distributed with this project.
