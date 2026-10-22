-- Aseprite 1.3.7 uses (message, data); do not require the newer error argument.
local M = {}
local EXTENSION_VERSION = "0.4.1"

local function environment(name)
  local value=os.getenv(name)
  return value and value~="" and value or nil
end
local function endpoint(plugin)
  local host=plugin.preferences.host or environment("ASEPRITE_MCP_HOST") or "127.0.0.1"
  if host=="localhost" then host="127.0.0.1" end
  local port=tonumber(plugin.preferences.port or environment("ASEPRITE_MCP_PORT") or 8765)
  assert(host=="127.0.0.1" or host=="::1","Host must be 127.0.0.1, localhost or ::1")
  assert(port and port%1==0 and port>=1 and port<=65535,"Port must be an integer from 1 to 65535")
  return host,port
end
local function endpoint_url(plugin)
  local host,port=endpoint(plugin)
  local address=host=="::1" and "[::1]" or host
  return "ws://"..address..":"..port
end
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
  function self:disconnect(stop_auto)
    if stop_auto~=false then
      self:stop_auto()
      plugin.preferences.auto_connect=false
    end
    self.generation=self.generation+1
    self.ready=false
    if self.ws then local ws=self.ws; self.ws=nil; ws:close() end
    if self.editor then self.editor:close(); self.editor=nil end
    self.cache={}; self.order={}; self.session=nil
    self.connection_url=nil
    self.opened=false; self.last_pong=nil
    self:set_status("Disconnected")
  end
  function self:shutdown()
    self:stop_auto()
    self:disconnect(false)
    if self.dialog then self.dialog:close(); self.dialog=nil end
  end
  function self:connect()
    local url=endpoint_url(plugin)
    self:disconnect(false)
    assert(WebSocket and json and json.encode and json.decode and app.apiVersion>=28,
           "Aseprite API 28, WebSocket and JSON required")
    self.connection_url=url
    self.connect_started=os.time()
    local generation=self.generation
    local function receive(kind, data)
      if generation~=self.generation then return end
      if kind==WebSocketMessageType.OPEN then
        self.opened=true; self.last_pong=os.time()
        -- Every reconnect gets a fresh namespace; no cached old-session writes.
        self.cache={}; self.order={}; self.ready=false
        if self.editor then self.editor:close(); self.editor=nil end
        local capabilities={"list_documents"}
        if Sprite and Image and app.events and app.transaction and app.undo and app.redo then
          capabilities={"list_documents","get_document_info","create_sprite","apply_operations","save_sprite","undo","redo"}
          if string.pack then capabilities[#capabilities+1]="get_preview" end
          local animation=dofile(app.fs.joinPath(plugin.path,"animation.lua"))
          if animation.available() then capabilities[#capabilities+1]="apply_animation" end
        end
        self.session=tostring(os.time()).."-"..tostring(math.random(1,2147483647)).."-"..tostring(generation)
        self.ws:sendText(json.encode{type="hello", protocol_version=1,
          session_id=self.session, aseprite_version=tostring(app.version), api_version=app.apiVersion,
          extension_version=EXTENSION_VERSION,
          capabilities=capabilities})
        self:set_status("Handshaking")
      elseif kind==WebSocketMessageType.TEXT then
        local ok, message=pcall(json.decode, data)
        if not ok or (type(message)~="table" and type(message)~="userdata") then
          self:set_status("Invalid server message"); return
        end
        if message.type=="pong" then self.last_pong=os.time(); return end
        if message.type=="welcome" then
          if message.protocol_version~=1 or message.session_id~=self.session then
            self:disconnect(false); self:set_status("Invalid welcome"); return
          end
          self.limits=message.limits
          local preview=string.pack and dofile(app.fs.joinPath(plugin.path,"preview.lua")) or nil
          local animation=dofile(app.fs.joinPath(plugin.path,"animation.lua"))
          local animation_enabled=false
          for _,name in ipairs(message.capabilities) do if name=="apply_animation" then animation_enabled=true end end
          self.editor=dofile(app.fs.joinPath(plugin.path,"editor.lua")).new(self.limits,preview,animation,animation_enabled)
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
        -- API 28's socket can remain stuck after its peer is force-killed.
        -- Retire it; the single auto timer creates a fresh connection.
        self:disconnect(false)
        self:set_status("Disconnected / reconnecting")
      elseif kind==WebSocketMessageType.ERROR then
        self:disconnect(false)
        self:set_status("Connection failed; check host and port")
      end
    end
    self.ws=WebSocket{url=url, onreceive=receive, deflate=false, minreconnectwait=1,maxreconnectwait=5}
    self:set_status("Connecting"); self.ws:connect()
  end
  function self:stop_auto()
    if self.auto_timer then self.auto_timer:stop(); self.auto_timer=nil end
  end
  function self:poll_connection()
    local url=endpoint_url(plugin)
    if self.ws and os.time()-(self.last_pong or self.connect_started or os.time())>=5 then
      self:disconnect(false)
    end
    if not self.ws or self.connection_url~=url then self:connect()
    elseif self.opened then self.ws:sendText('{"type":"ping"}') end
  end
  function self:start_auto()
    self:stop_auto()
    if plugin.preferences.auto_connect==false then return end
    assert(Timer,"Aseprite Timer API required for automatic connection")
    -- Defer socket permissions until extension registration has completed.
    self.auto_timer=Timer{interval=1.0,ontick=function()
      local ok,err=pcall(function() self:poll_connection() end)
      if not ok then self:set_status("Auto-connect: "..tostring(err)) end
    end}
    self.auto_timer:start()
    self:set_status("Waiting for MCP server...")
  end
  function self:settings()
    if self.dialog then self.dialog:close() end
    local dlg=Dialog{title="MCP Live"}; self.dialog=dlg
    local ok,host,port=pcall(endpoint,plugin)
    if not ok then host,port="127.0.0.1",8765 end
    dlg:combobox{id="host",label="Host",option=host,options={"127.0.0.1","::1"}}
      :number{id="port",label="Port",text=tostring(port),decimals=0}
      :check{id="auto",label="Connection",text="Connect automatically",selected=plugin.preferences.auto_connect~=false}
      :label{id="status",label="Status",text=self.status}
      :button{text="Apply / Connect",onclick=function()
        local ok,err=pcall(function()
          local port=tonumber(dlg.data.port)
          assert(port and port%1==0 and port>=1 and port<=65535,"Port must be 1 to 65535")
          plugin.preferences.host=dlg.data.host; plugin.preferences.port=port
          plugin.preferences.auto_connect=dlg.data.auto
          self:disconnect(false)
          self:start_auto(); self:poll_connection()
        end)
        if not ok then self:set_status(tostring(err)) end
      end}
      :button{text="Disconnect",onclick=function() self:disconnect() end}
      :show{wait=false}
  end
  return self
end
return M
