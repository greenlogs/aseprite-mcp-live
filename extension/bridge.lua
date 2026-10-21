-- Aseprite 1.3.7 uses (message, data); do not require the newer error argument.
local M = {}
-- API 28 JSON objects are userdata; json.encode does not serialize nested
-- JSON userdata inside Lua tables. Normalize incoming messages recursively.
local function plain(value)
  if type(value)~="userdata" and type(value)~="table" then return value end
  local result={}
  -- API 28 JSON arrays expose ipairs but pairs yields no entries.
  for index,item in ipairs(value) do result[index]=plain(item) end
  if next(result) then return result end
  for key,item in pairs(value) do result[key]=plain(item) end
  return result
end
function M.new(plugin)
  local self = {plugin=plugin, status="Disconnected", generation=0}
  function self:set_status(text)
    self.status=text
    if self.dialog then self.dialog:modify{id="status", text=text} end
  end
  function self:disconnect()
    self.generation=self.generation+1
    self.ready=false
    if self.ws then local ws=self.ws; self.ws=nil; ws:close() end
    if self.editor then self.editor:close(); self.editor=nil end
    self.cache={}; self.order={}; self.session=nil
    self:set_status("Disconnected")
  end
  function self:connect(config)
    self:disconnect()
    if (type(config) ~= "table" and type(config) ~= "userdata") or type(config.url) ~= "string" or
        not (config.url:match("^ws://127%.0%.0%.1:%d+$") or config.url:match("^ws://%[::1%]:%d+$")) or
        type(config.token) ~= "string" or #config.token==0 then
      error("Invalid loopback connection configuration")
    end
    assert(WebSocket and json and json.encode and json.decode and app.apiVersion>=28,
           "Aseprite API 28, WebSocket and JSON required")
    local generation=self.generation
    local function receive(kind, data)
      if generation~=self.generation then return end
      if kind==WebSocketMessageType.OPEN then
        -- Every reconnect gets a fresh namespace; no cached old-session writes.
        self.cache={}; self.order={}; self.ready=false
        if self.editor then self.editor:close(); self.editor=nil end
        local capabilities={"list_documents"}
        if Sprite and Image and app.events and app.transaction and app.undo and app.redo then
          capabilities={"list_documents","get_document_info","create_sprite","apply_operations","save_sprite","undo","redo"}
        end
        self.session=tostring(os.time()).."-"..tostring(math.random(1,2147483647)).."-"..tostring(generation)
        self.ws:sendText(json.encode{type="hello", protocol_version=1, token=config.token,
          session_id=self.session, aseprite_version=tostring(app.version), api_version=app.apiVersion,
          capabilities=capabilities})
        self:set_status("Handshaking")
      elseif kind==WebSocketMessageType.TEXT then
        local ok, message=pcall(json.decode, data)
        if not ok or (type(message)~="table" and type(message)~="userdata") then
          self:set_status("Invalid server message"); return
        end
        if message.type=="welcome" then
          if message.protocol_version~=1 or message.session_id~=self.session then
            self:disconnect(); self:set_status("Invalid welcome"); return
          end
          self.limits=message.limits
          self.editor=dofile(app.fs.joinPath(plugin.path,"editor.lua")).new(self.limits)
          self.ready=true; self:set_status("Connected")
          return
        end
        if not message.request_id then
          self:set_status(message.error and message.error.message or "Unknown server message"); return
        end
        local request=plain(message)
        local result={protocol_version=1, request_id=request.request_id, target=request.target, ok=false}
        local function reject(code, text) result.error={code=code,message=text} end
        if not self.ready or not request.target or request.target.session_id~=self.session then
          reject("SESSION_MISMATCH", "Stale editor session")
        elseif request.protocol_version~=1 then reject("VERSION_MISMATCH", "Protocol version must be 1")
        else
          local previous=self.cache[request.request_id]
          if previous and os.time()-previous.time<self.limits.dedup_ttl_seconds then
            if previous.raw==data then self.ws:sendText(previous.result); return end
            reject("REQUEST_CONFLICT", "Request ID reused with different payload")
          elseif request.action then
            local ok,value,record=pcall(function() return self.editor:execute(request) end)
            if ok then
              result.ok=true; result.data=value; result.revision=record and record.revision
              result.context_revision=self.editor.context
            elseif type(value)=="table" then reject(value.code,value.message)
            else reject("EXECUTION_FAILED",tostring(value)) end
          else reject("INVALID_REQUEST", "Missing editor action") end
        end
        local encoded=json.encode(result)
        if not self.cache[request.request_id] then self.order[#self.order+1]=request.request_id end
        -- Keep the original ID receipt on conflict.
        if not result.error or result.error.code~="REQUEST_CONFLICT" then
          self.cache[request.request_id]={raw=data,result=encoded,time=os.time()}
        end
        while #self.order>self.limits.dedup_entries do self.cache[table.remove(self.order,1)]=nil end
        self.ws:sendText(encoded)
      elseif kind==WebSocketMessageType.CLOSE then
        if self.editor then self.editor:close(); self.editor=nil end
        self.ready=false; self:set_status("Disconnected / reconnecting")
      elseif kind==WebSocketMessageType.ERROR then
        self.ready=false; self:set_status("Connection failed; check server and configuration")
      end
    end
    self.ws=WebSocket{url=config.url, onreceive=receive, deflate=false, minreconnectwait=1,maxreconnectwait=5}
    self:set_status("Connecting"); self.ws:connect()
  end
  function self:settings()
    if self.dialog then self.dialog:close() end
    local dlg=Dialog{title="MCP Live"}; self.dialog=dlg
    dlg:file{id="config",label="Connection JSON",filename=plugin.preferences.connection_file or "",open=true}
      :label{id="status",label="Status",text=self.status}
      :button{text="Connect",onclick=function()
        local ok,err=pcall(function()
          local path=dlg.data.config
          local f=assert(io.open(path,"rb"),"Cannot open connection file")
          local raw=f:read("*a"); f:close()
          self:connect(json.decode(raw)); plugin.preferences.connection_file=path
        end)
        if not ok then self:set_status(tostring(err)) end
      end}
      :button{text="Disconnect",onclick=function() self:disconnect() end}
      :show{wait=false}
  end
  return self
end
return M
