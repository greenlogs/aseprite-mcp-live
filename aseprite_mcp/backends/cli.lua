-- Protocol v1 disk adapter. All parameters arrive as JSON, never Lua code.
local function read_json(path)
  local f = assert(io.open(path, "rb"))
  local text = f:read("*a")
  f:close()
  return json.decode(text)
end
local p = read_json(app.params.payload)
local function fail(code, message) error({code=code, message=message}) end
local function execute()
  if not json or not json.encode or not json.decode then
    fail("UNSUPPORTED_CAPABILITY", "JSON API unavailable")
  end
  local spr = app.activeSprite
  if not spr then fail("INVALID_TARGET", "No disk sprite loaded") end
  local ids, layers, refs = {}, {}, {}
  local function walk(items, prefix)
    for i, layer in ipairs(items) do
      local id = prefix .. tostring(i)
      ids[layer] = id; layers[id] = layer
      if layer.isGroup then walk(layer.layers, id .. "/") end
    end
  end
  walk(spr.layers, "")
  local function info()
    local mode = "unknown"
    if spr.colorMode == ColorMode.RGB then mode="rgb"
    elseif spr.colorMode == ColorMode.GRAY then mode="gray"
    elseif spr.colorMode == ColorMode.INDEXED then mode="indexed" end
    local result = {width=spr.width, height=spr.height, color_mode=mode,
      frames=#spr.frames, layers={}, aseprite_version=tostring(app.version),
      api_version=app.apiVersion}
    local function describe(items, prefix)
      for i, layer in ipairs(items) do
        local id = prefix .. tostring(i)
        result.layers[#result.layers+1] = {id=id, name=layer.name,
          is_group=layer.isGroup, opacity=layer.opacity, visible=layer.isVisible}
        if layer.isGroup then describe(layer.layers, id .. "/") end
      end
    end
    describe(spr.layers, "")
    return result
  end
  if p.action.name == "get_document_info" then return info() end
  if p.action.name ~= "apply_operations" then
    fail("UNSUPPORTED_CAPABILITY", "Operation not implemented by CLI adapter")
  end
  if spr.colorMode ~= ColorMode.RGB then
    fail("UNSUPPORTED_CAPABILITY", "Editing requires RGB")
  end
  local function resolve(op)
    local layer = op.layer.kind == "ref" and refs[op.layer.value] or layers[op.layer.value]
    if not layer then fail("INVALID_TARGET", "Unknown layer identifier") end
    return layer
  end
  -- Validate the whole batch before edits, including references to future real layers.
  for _, op in ipairs(p.action.operations) do
    if op.op == "create_layer" then
      refs[op.ref] = {pending=true}
    else
      local layer = resolve(op)
      if type(layer) ~= "table" and (layer.isGroup or layer.isTilemap or layer.isReference
          or layer.isBackground or not layer.isEditable) then
        fail("UNSUPPORTED_CAPABILITY", "Editing requires an editable ordinary layer")
      end
      if op.op == "pixel" or op.op == "rectangle" then
        if op.frame > #spr.frames then fail("INVALID_TARGET", "Unknown frame") end
        local w, h = op.width or 1, op.height or 1
        if op.x+w > spr.width or op.y+h > spr.height then
          fail("INVALID_REQUEST", "Coordinates exceed canvas bounds")
        end
      end
    end
  end
  refs = {}
  app.transaction(function()
    for _, op in ipairs(p.action.operations) do
      if op.op == "create_layer" then
        local layer = spr:newLayer(); layer.name=op.name; refs[op.ref]=layer
      elseif op.op == "set_opacity" then
        resolve(op).opacity=op.opacity
      else
        local layer = resolve(op)
        local frame = spr.frames[op.frame]
        local cel = layer:cel(frame)
        local image = Image(spr.width, spr.height, ColorMode.RGB)
        if cel then image:drawImage(cel.image, cel.position) end
        local color = app.pixelColor.rgba(table.unpack(op.rgba))
        local w, h = op.width or 1, op.height or 1
        for y=0,h-1 do
          for x=0,w-1 do
            if op.op == "pixel" or op.filled or x==0 or y==0 or x==w-1 or y==h-1 then
              image:putPixel(op.x+x, op.y+y, color)
            end
          end
        end
        if cel then cel.image=image; cel.position=Point(0,0)
        else spr:newCel(layer, frame, image, Point(0,0)) end
      end
    end
  end)
  -- Stage to a unique artifact. Python commits only after a matching receipt.
  spr:saveAs(p.artifact)
  ids, layers = {}, {}; walk(spr.layers, "")
  local result = info(); result.layer_refs={}
  for ref, layer in pairs(refs) do
    for id, candidate in pairs(layers) do
      if candidate == layer then result.layer_refs[ref]=id end
    end
  end
  return result
end
local success, data = pcall(execute)
local receipt = {nonce=p.nonce, ok=success}
if success then receipt.data=data
elseif type(data) == "table" then receipt.error=data
else receipt.error={code="EXECUTION_FAILED", message=tostring(data)} end
local f = assert(io.open(app.params.result, "wb"))
f:write(json.encode(receipt)); f:close()
