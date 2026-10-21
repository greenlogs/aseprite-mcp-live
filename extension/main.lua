-- Loaded by Aseprite's extension manager; automatic local connection is deferred.
local instance
function init(plugin)
  if _G.__aseprite_mcp_live then _G.__aseprite_mcp_live:shutdown() end
  instance = dofile(app.fs.joinPath(plugin.path, "bridge.lua")).new(plugin)
  _G.__aseprite_mcp_live = instance
  plugin:newCommand{id="MCPConnect", title="MCP: Connect / Settings", group="file_scripts",
    onclick=function() instance:settings() end}
  plugin:newCommand{id="MCPDisconnect", title="MCP: Disconnect", group="file_scripts",
    onclick=function() instance:disconnect() end}
  local ok,err=pcall(function() instance:start_auto() end)
  if not ok then instance:set_status(tostring(err)) end
end
function exit(plugin)
  if instance then instance:shutdown(); instance=nil end
  _G.__aseprite_mcp_live=nil
end
