-- Session-local object registry and undoable edits. Objects are compared by
-- equality: API 28 may return different userdata wrappers on each enumeration.
local M={}
local drawing=dofile(app.fs.joinPath(app.fs.filePath(debug.getinfo(1,"S").source:sub(2)),"drawing.lua"))
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
function M.new(limits,preview,animation,animation_enabled)
  local self={documents={},next_document=0,next_layer=0,context=0,suppress_context=false,limits=limits,
    animation=animation,animation_enabled=animation_enabled}
  self.site_listener=app.events:on("sitechange",function()
    if not self.suppress_context then self.context=self.context+1 end
  end)
  -- Commands include selection-shape changes whose bounds may stay identical.
  self.command_listener=app.events:on("aftercommand",function()
    if not self.suppress_context then self.context=self.context+1 end
  end)
  function self:close()
    app.events:off(self.site_listener)
    app.events:off(self.command_listener)
    for _,record in ipairs(self.documents) do
      for _,listener in ipairs(record.listeners) do pcall(function() record.events:off(listener) end) end
    end
    self.documents={}
  end
  function self:sync()
    local active,layer,frame=app.activeSprite,app.activeLayer,app.activeFrame
    local selection=""
    if active then
      local bounds=active.selection.bounds
      selection=table.concat({tostring(active.selection.isEmpty),bounds.x,bounds.y,bounds.width,bounds.height},":")
    end
    if self.active~=active or self.active_layer~=layer or self.active_frame~=frame or self.selection~=selection then
      self.context=self.context+1
      self.active,self.active_layer,self.active_frame,self.selection=active,layer,frame,selection
    end
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
      if animation then
        local signature=animation.signature(sprite)
        if record.animation_signature and record.animation_signature~=signature then record.revision=record.revision+1 end
        record.animation_signature=signature
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
    if animation then
      local timeline=animation.metadata(sprite)
      data.frame_durations_ms=timeline.frame_durations_ms;data.tags=timeline.tags
    end
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
  function self:with_target(sprite,callback,refresh)
    local old_sprite,old_layer,old_frame=app.activeSprite,app.activeLayer,app.activeFrame
    local old_range=drawing.save_range()
    -- API28 exposes Range.type read-only; layers/frames setters cannot rebuild
    -- a CELS range. Refuse before any mutation rather than lose this selection.
    if old_range and old_range.type==RangeType.CELS then
      fail("UNSUPPORTED_CAPABILITY","Clear the timeline Cel selection before editing; API28 cannot restore its range type")
    end
    local old_frame_number=old_frame and old_frame.frameNumber
    local previous=self.suppress_context; self.suppress_context=true
    local ok,value=pcall(function()
      if app.activeSprite~=sprite then app.activeSprite=sprite end
      return callback()
    end)
    local restored,restore_error=pcall(function()
      if app.activeSprite~=old_sprite then app.activeSprite=old_sprite end
      if old_sprite then
        if old_layer then app.activeLayer=old_layer end
        if old_frame then
          local surviving
          for _,frame in ipairs(old_sprite.frames) do if frame==old_frame then surviving=frame;break end end
          app.activeFrame=surviving or old_sprite.frames[math.min(old_frame_number,#old_sprite.frames)]
        end
        drawing.restore_range(old_range)
      end
    end)
    self.suppress_context=previous
    -- Socket callbacks do not automatically invalidate the editor canvas.
    -- Refresh once after commit/rollback and context restoration, never per pixel.
    local refreshed,refresh_error=true,nil
    if refresh then refreshed,refresh_error=pcall(app.refresh) end
    if not ok then error(value,0) end
    if not restored then fail("EXECUTION_FAILED","Could not restore active context: "..tostring(restore_error)) end
    if not refreshed then fail("EXECUTION_FAILED","Could not refresh editor: "..tostring(refresh_error)) end
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
    local batch={entries={},by_key={}}
    for _,op in ipairs(operations) do
      if op.op=="create_layer" then
        if refs[op.ref] then fail("INVALID_REQUEST","Duplicate layer reference") end
        refs[op.ref]={pending=true}
      else
        local layer=self:resolve(record,op,refs)
        if type(layer)~="table" and not editable(layer) then
          fail("UNSUPPORTED_CAPABILITY","Target and its parents must be editable ordinary layers")
        end
        local left,top,right,bottom=drawing.bounds(op)
        if left then
          if not sprite.frames[op.frame] then fail("INVALID_TARGET","Unknown frame") end
          if left<0 or top<0 or right>sprite.width or bottom>sprite.height then
            fail("INVALID_REQUEST","Coordinates exceed canvas")
          end
          pixels=pixels+drawing.cost(op)
          local key=drawing.key(op)
          local entry=batch.by_key[key]
          if not entry then
            entry={left=left,top=top,right=right,bottom=bottom,frame=op.frame}
            batch.by_key[key]=entry;batch.entries[#batch.entries+1]=entry
            if type(layer)~="table" then
              local cel=layer:cel(op.frame)
              if cel then
                entry.left=math.min(entry.left,cel.position.x);entry.top=math.min(entry.top,cel.position.y)
                entry.right=math.max(entry.right,cel.position.x+cel.image.width)
                entry.bottom=math.max(entry.bottom,cel.position.y+cel.image.height)
              end
            end
          else
            entry.left=math.min(left,entry.left);entry.top=math.min(top,entry.top)
            entry.right=math.max(right,entry.right);entry.bottom=math.max(bottom,entry.bottom)
          end
        elseif op.op~="set_opacity" then fail("INVALID_REQUEST","Unknown operation") end
      end
    end
    if pixels>limits.max_pixels then fail("LIMIT_EXCEEDED","Batch exceeds pixel budget") end
    local allocated=0
    for _,entry in ipairs(batch.entries) do allocated=allocated+(entry.right-entry.left)*(entry.bottom-entry.top) end
    if allocated>limits.max_pixels then fail("LIMIT_EXCEEDED","Batch Cel buffers exceed pixel budget") end
    return batch
  end
  function self:apply_one(record,op,refs,batch,tick)
    local sprite=record.object
    if op.op=="create_layer" then
      local layer=sprite:newLayer(); layer.name=op.name; refs[op.ref]=layer
    elseif op.op=="set_opacity" then self:resolve(record,op,refs).opacity=op.opacity
    else
      local entry=batch.by_key[drawing.key(op)]
      drawing.prepare(entry,self:resolve(record,op,refs),tick)
      drawing.paint(entry,op,tick)
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
    elseif action.name=="get_preview" and preview then
      local value=preview.render(sprite,action,limits)
      self.preview_timing=preview.last_timing
      return value,record
    elseif action.name=="read_pixels" then
      if sprite.colorMode~=ColorMode.RGB then fail("UNSUPPORTED_CAPABILITY","Pixel reads require RGB") end
      local layer=self:resolve(record,{layer={kind="id",value=action.layer}},{})
      if not ordinary(layer) then fail("UNSUPPORTED_CAPABILITY","Pixel reads require an ordinary layer") end
      return drawing.read(sprite,layer,action,limits),record
    elseif action.name=="apply_operations" then
      local batch=self:validate(record,action.operations)
      local refs={}
      self:with_target(sprite,function()
        app.transaction("MCP batch",function()
          local tick=drawing.clock(limits)
          for _,op in ipairs(action.operations) do
            self:apply_one(record,op,refs,batch,tick)
            tick(true)
          end
          drawing.commit(batch,tick)
        end)
      end,true)
      self:sync()
      local layer_refs={}
      for ref,layer in pairs(refs) do layer_refs[ref]=assert(find(record.layers,layer)).id end
      return {layer_refs=next(layer_refs) and layer_refs or nil,operations=#action.operations},record
    elseif action.name=="apply_animation" and animation and self.animation_enabled then
      animation.validate(sprite,action.operations,limits)
      self:with_target(sprite,function()
        app.transaction("MCP animation",function()
          local started=os.clock()
          local function check_time()
            if os.clock()-started>(limits.max_batch_seconds or 0.25) then
              fail("LIMIT_EXCEEDED","Atomic animation exceeded CPU budget; reduce batch size")
            end
          end
          for _,op in ipairs(action.operations) do self.animation.apply_one(sprite,op,check_time) end
        end)
      end,true)
      self:sync()
      local data=animation.metadata(sprite);data.operations=#action.operations;data.frames=#sprite.frames
      return data,record
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
      end,true)
      self:sync()
      return {applied=record.revision~=before,
        message="History acts on the document's latest action, including manual edits"},record
    end
    fail("UNSUPPORTED_CAPABILITY","Unknown editor action")
  end
  return self
end
return M
