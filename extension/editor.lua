-- Session-local object registry and undoable edits. Objects are compared by
-- equality: API 28 may return different userdata wrappers on each enumeration.
local M={}
local function fail(code,message) error({code=code,message=message},0) end
local function find(items,object)
  for _,entry in ipairs(items) do if entry.object==object then return entry end end
end
local function ordinary(layer)
  return not layer.isGroup and not layer.isTilemap and not layer.isReference and not layer.isBackground
end
local function editable(layer)
  local current=layer
  while current and current.isGroup~=nil do
    if not current.isEditable then return false end
    current=current.parent
    if current and current==layer.sprite then break end
  end
  return ordinary(layer)
end
function M.new(limits)
  local self={documents={},next_document=0,next_layer=0,context=0,suppress_context=false,limits=limits}
  self.site_listener=app.events:on("sitechange",function()
    if not self.suppress_context then self.context=self.context+1 end
  end)
  function self:close()
    app.events:off(self.site_listener)
    for _,record in ipairs(self.documents) do
      for _,listener in ipairs(record.listeners) do pcall(function() record.events:off(listener) end) end
    end
    self.documents={}
  end
  function self:sync()
    local current={}
    for _,sprite in ipairs(app.sprites) do
      local record=find(self.documents,sprite)
      if not record then
        self.next_document=self.next_document+1
        record={object=sprite,id="d"..self.next_document,revision=0,layers={},listeners={},events=sprite.events}
        for _,event in ipairs{"change","filenamechange","layername","layeropacity","layervisibility","layerblendmode"} do
          local ok,listener=pcall(function()
            return record.events:on(event,function() record.revision=record.revision+1 end)
          end)
          if ok then record.listeners[#record.listeners+1]=listener
          elseif event=="change" then fail("UNSUPPORTED_CAPABILITY","Sprite change events required") end
        end
      end
      current[#current+1]=record
      local layers={}
      local function walk(items,parent_id)
        for _,layer in ipairs(items) do
          local entry=find(record.layers,layer)
          if not entry then
            self.next_layer=self.next_layer+1
            entry={object=layer,id="l"..self.next_layer}
          end
          entry.parent_id=parent_id; layers[#layers+1]=entry
          if layer.isGroup then walk(layer.layers,entry.id) end
        end
      end
      walk(sprite.layers,nil); record.layers=layers
    end
    for _,old in ipairs(self.documents) do
      if not find(current,old.object) then
        for _,listener in ipairs(old.listeners) do pcall(function() old.events:off(listener) end) end
      end
    end
    self.documents=current
  end
  function self:info(record)
    local sprite=record.object
    local mode=sprite.colorMode==ColorMode.RGB and "rgb" or
      sprite.colorMode==ColorMode.GRAY and "gray" or "indexed"
    local data={document_id=record.id,width=sprite.width,height=sprite.height,color_mode=mode,
      frames=#sprite.frames,frame_durations={},layers={},active=app.activeSprite==sprite,
      saved=app.fs.isFile(sprite.filename),path=sprite.filename,modified=sprite.isModified,
      revision=record.revision,context_revision=self.context,
      aseprite_version=tostring(app.version),api_version=app.apiVersion}
    for _,frame in ipairs(sprite.frames) do data.frame_durations[#data.frame_durations+1]=frame.duration end
    for _,entry in ipairs(record.layers) do
      local layer=entry.object
      data.layers[#data.layers+1]={id=entry.id,name=layer.name,parent_id=entry.parent_id,
        is_group=layer.isGroup,opacity=layer.opacity,visible=layer.isVisible,editable=layer.isEditable,
        is_reference=layer.isReference,is_tilemap=layer.isTilemap}
      if data.active and app.activeLayer==layer then data.active_layer_id=entry.id end
    end
    if data.active and app.activeFrame then data.active_frame=app.activeFrame.frameNumber end
    local bounds=sprite.selection.bounds
    data.selection={empty=sprite.selection.isEmpty,x=bounds.x,y=bounds.y,width=bounds.width,height=bounds.height}
    return data
  end
  function self:with_target(sprite,callback)
    local old_sprite,old_layer,old_frame=app.activeSprite,app.activeLayer,app.activeFrame
    local previous=self.suppress_context; self.suppress_context=true
    local ok,value=pcall(function() app.activeSprite=sprite; return callback() end)
    local restored,restore_error=pcall(function()
      app.activeSprite=old_sprite
      if old_sprite then
        if old_layer then app.activeLayer=old_layer end
        if old_frame then app.activeFrame=old_frame end
      end
    end)
    self.suppress_context=previous
    if not ok then error(value,0) end
    if not restored then fail("EXECUTION_FAILED","Could not restore active context: "..tostring(restore_error)) end
    return value
  end
  function self:resolve(record,op,refs)
    if op.layer.kind=="ref" then
      if refs[op.layer.value] then return refs[op.layer.value] end
    else
      for _,entry in ipairs(record.layers) do if entry.id==op.layer.value then return entry.object end end
    end
    fail("INVALID_TARGET","Unknown or deleted layer")
  end
  function self:validate(record,operations)
    local sprite=record.object
    if sprite.colorMode~=ColorMode.RGB then fail("UNSUPPORTED_CAPABILITY","Editing requires RGB") end
    if #operations>limits.max_operations then fail("LIMIT_EXCEEDED","Too many operations") end
    local refs,pixels={},0
    for _,op in ipairs(operations) do
      if op.op=="create_layer" then
        if refs[op.ref] then fail("INVALID_REQUEST","Duplicate layer reference") end
        refs[op.ref]={pending=true}
      else
        local layer=self:resolve(record,op,refs)
        if type(layer)~="table" and not editable(layer) then
          fail("UNSUPPORTED_CAPABILITY","Target and its parents must be editable ordinary layers")
        end
        if op.op=="pixel" or op.op=="rectangle" then
          if not sprite.frames[op.frame] then fail("INVALID_TARGET","Unknown frame") end
          local w,h=op.width or 1,op.height or 1
          if op.x<0 or op.y<0 or op.x+w>sprite.width or op.y+h>sprite.height then
            fail("INVALID_REQUEST","Coordinates exceed canvas")
          end
          pixels=pixels+w*h
          if type(layer)~="table" then
            local cel=layer:cel(op.frame)
            if cel then
              local left,top=math.min(cel.position.x,op.x),math.min(cel.position.y,op.y)
              local right=math.max(cel.position.x+cel.image.width,op.x+w)
              local bottom=math.max(cel.position.y+cel.image.height,op.y+h)
              if (right-left)*(bottom-top)>limits.max_pixels then
                fail("LIMIT_EXCEEDED","Expanded Cel exceeds pixel budget")
              end
            end
          end
        elseif op.op~="set_opacity" then fail("INVALID_REQUEST","Unknown operation") end
      end
    end
    if pixels>limits.max_pixels then fail("LIMIT_EXCEEDED","Batch exceeds pixel budget") end
  end
  function self:apply_one(record,op,refs)
    local sprite=record.object
    if op.op=="create_layer" then
      local layer=sprite:newLayer(); layer.name=op.name; refs[op.ref]=layer
    elseif op.op=="set_opacity" then self:resolve(record,op,refs).opacity=op.opacity
    else
      local layer=self:resolve(record,op,refs)
      local cel=layer:cel(op.frame)
      local w,h=op.width or 1,op.height or 1
      local left,top,right,bottom=op.x,op.y,op.x+w,op.y+h
      if cel then
        left=math.min(left,cel.position.x); top=math.min(top,cel.position.y)
        right=math.max(right,cel.position.x+cel.image.width); bottom=math.max(bottom,cel.position.y+cel.image.height)
      end
      if (right-left)*(bottom-top)>limits.max_pixels then fail("LIMIT_EXCEEDED","Expanded Cel exceeds pixel budget") end
      local image=Image(right-left,bottom-top,ColorMode.RGB)
      if cel then
        -- Copy raw pixels, including alpha-zero RGB, into an independent image.
        for it in cel.image:pixels() do
          image:putPixel(it.x+cel.position.x-left,it.y+cel.position.y-top,it())
        end
      end
      local color=app.pixelColor.rgba(table.unpack(op.rgba))
      for y=0,h-1 do for x=0,w-1 do
        if op.op=="pixel" or op.filled or x==0 or y==0 or x==w-1 or y==h-1 then
          image:putPixel(op.x+x-left,op.y+y-top,color)
        end
      end end
      if cel then cel.image=image; cel.position=Point(left,top)
      else sprite:newCel(layer,op.frame,image,Point(left,top)) end
    end
  end
  function self:execute(request)
    self:sync()
    local action=request.action
    if request.expected_context and request.expected_context~=self.context then
      fail("CONTEXT_CONFLICT","Active context changed; refresh document information")
    end
    if action.name=="list_documents" then
      local documents={}; local active
      for _,record in ipairs(self.documents) do
        documents[#documents+1]=self:info(record)
        if app.activeSprite==record.object then active=record.id end
      end
      return {documents=documents,active_document_id=active},nil
    elseif action.name=="create_sprite" then
      if action.width*action.height>limits.max_pixels then fail("LIMIT_EXCEEDED","Canvas exceeds pixel budget") end
      local sprite=Sprite(action.width,action.height,ColorMode.RGB)
      self:sync(); local record=find(self.documents,sprite)
      return self:info(record),record
    end
    local record
    for _,entry in ipairs(self.documents) do if entry.id==request.target.document_id then record=entry; break end end
    if not record then fail("INVALID_TARGET","Document closed or unknown") end
    if request.expected_revision and request.expected_revision~=record.revision then
      fail("REVISION_CONFLICT","Document changed; refresh before editing")
    end
    local sprite=record.object
    if action.name=="get_document_info" then return self:info(record),record
    elseif action.name=="apply_operations" then
      self:validate(record,action.operations)
      local refs={}
      self:with_target(sprite,function()
        app.transaction("MCP batch",function()
          for _,op in ipairs(action.operations) do self:apply_one(record,op,refs) end
        end)
      end)
      self:sync()
      local layer_refs={}
      for ref,layer in pairs(refs) do layer_refs[ref]=assert(find(record.layers,layer)).id end
      return {layer_refs=next(layer_refs) and layer_refs or nil,operations=#action.operations},record
    elseif action.name=="save_sprite" then
      local path=action.path
      if not path or path=="" then
        if not app.fs.isFile(sprite.filename) then fail("INVALID_REQUEST","Unsaved document requires an absolute path") end
        path=sprite.filename
      end
      if not (path:match("^%a:[/\\]") or path:match("^[/\\][/\\]") or path:match("^/")) then
        fail("INVALID_REQUEST","Save path must be absolute")
      end
      if not (path:lower():match("%.aseprite$") or path:lower():match("%.ase$")) then
        fail("UNSUPPORTED_CAPABILITY","Save requires .aseprite or .ase to preserve the document")
      end
      if app.fs.isFile(path) and not action.overwrite then fail("INVALID_REQUEST","Destination exists; explicitly allow overwrite") end
      self:with_target(sprite,function() sprite:saveAs(path) end)
      if not app.fs.isFile(path) or sprite.isModified then fail("EXECUTION_FAILED","Save did not complete") end
      return {path=sprite.filename},record
    elseif action.name=="undo" or action.name=="redo" then
      local before=record.revision
      self:with_target(sprite,function()
        if action.name=="undo" then app.undo() else app.redo() end
      end)
      self:sync()
      return {applied=record.revision~=before,
        message="History acts on the document's latest action, including manual edits"},record
    end
    fail("UNSUPPORTED_CAPABILITY","Unknown editor action")
  end
  return self
end
return M
