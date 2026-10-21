-- Loaded by Aseprite's extension manager. No connection without a user command.
local instance
function init(plugin)
  if _G.__aseprite_mcp_live then _G.__aseprite_mcp_live:disconnect() end
  instance = dofile(app.fs.joinPath(plugin.path, "bridge.lua")).new(plugin)
  _G.__aseprite_mcp_live = instance
  plugin:newCommand{id="MCPConnect", title="MCP: Connect / Settings", group="file_scripts",
    onclick=function() instance:settings() end}
  plugin:newCommand{id="MCPDisconnect", title="MCP: Disconnect", group="file_scripts",
    onclick=function() instance:disconnect() end}
end
function exit(plugin)
  if instance then instance:disconnect(); instance=nil end
  _G.__aseprite_mcp_live=nil
end
