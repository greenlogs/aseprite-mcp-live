-- Deterministic RGB raster operations. No active-site, file or history changes.
local M={}
local function fail(code,message) error({code=code,message=message},0) end
function M.key(op) return op.layer.kind..":"..op.layer.value..":"..op.frame end
function M.bounds(op)
  if op.op=="line" then
    local before=math.floor((op.thickness-1)/2); local after=op.thickness-before
    return math.min(op.x1,op.x2)-before,math.min(op.y1,op.y2)-before,
      math.max(op.x1,op.x2)+after,math.max(op.y1,op.y2)+after
  elseif op.op=="pixels" then
    local left,top,right,bottom=math.huge,math.huge,0,0
    for _,p in ipairs(op.points) do
      left=math.min(left,p.x);top=math.min(top,p.y)
      right=math.max(right,p.x+1);bottom=math.max(bottom,p.y+1)
    end
    return left,top,right,bottom
  elseif op.op=="pixel" or op.op=="rectangle" or op.op=="write_region" or
      op.op=="clear_region" or op.op=="ellipse" then
    return op.x,op.y,op.x+(op.width or 1),op.y+(op.height or 1)
  end
end
function M.cost(op)
  if op.op=="pixels" then return #op.points end
  if op.op=="line" then
    return (math.max(math.abs(op.x2-op.x1),math.abs(op.y2-op.y1))+1)*op.thickness^2
  end
  local l,t,r,b=M.bounds(op)
  return l and (r-l)*(b-t) or 0
end
function M.clock(limits)
  local started=os.clock();local count=0
  return function(force)
    count=count+1
    if force or count%1024==0 then
      if os.clock()-started>limits.max_batch_seconds then
        fail("LIMIT_EXCEEDED","Atomic operation exceeded CPU budget; reduce batch size or region")
      end
    end
  end
end
function M.prepare(entry,layer,tick)
  if entry.image then return end
  local image=Image(entry.right-entry.left,entry.bottom-entry.top,ColorMode.RGB)
  local cel=layer:cel(entry.frame)
  if cel then
    -- Raw copy retains alpha-zero RGB and all off-canvas source pixels.
    for it in cel.image:pixels() do
      image:putPixel(it.x+cel.position.x-entry.left,it.y+cel.position.y-entry.top,it())
      tick()
    end
  end
  entry.image,entry.layer,entry.cel=image,layer,cel
  tick(true)
end
local function packed(rgba) return app.pixelColor.rgba(table.unpack(rgba)) end
local function source_over(source,dest)
  local pc=app.pixelColor
  local sa,da=pc.rgbaA(source),pc.rgbaA(dest)
  if sa==0 then return dest end
  if sa==255 or da==0 then return source end
  local denominator=sa*255+da*(255-sa)
  local function channel(s,d)
    return math.floor((s*sa*255+d*da*(255-sa)+denominator/2)/denominator)
  end
  return pc.rgba(channel(pc.rgbaR(source),pc.rgbaR(dest)),
    channel(pc.rgbaG(source),pc.rgbaG(dest)),channel(pc.rgbaB(source),pc.rgbaB(dest)),
    math.floor((denominator+127)/255))
end
function M.paint(entry,op,tick)
  local image=entry.image
  local function put(x,y,color,over)
    x=x-entry.left;y=y-entry.top
    if over then color=source_over(color,image:getPixel(x,y)) end
    image:putPixel(x,y,color);tick()
  end
  if op.op=="pixels" then
    for _,p in ipairs(op.points) do put(p.x,p.y,packed(p.rgba)) end
  elseif op.op=="write_region" then
    local index=0
    local function emit(color,count)
      color=packed(color)
      for _=1,count do
        put(op.x+index%op.width,op.y+math.floor(index/op.width),color,op.mode=="source_over")
        index=index+1
      end
    end
    if op.encoding=="rle" then
      for _,run in ipairs(op.runs) do emit(run.rgba,run.count) end
    else
      for _,rgba in ipairs(op.pixels) do emit(rgba,1) end
    end
  elseif op.op=="line" then
    local x,y=op.x1,op.y1
    local dx,dy=math.abs(op.x2-x),-math.abs(op.y2-y)
    local sx,sy=x<op.x2 and 1 or -1,y<op.y2 and 1 or -1
    local err=dx+dy;local before=math.floor((op.thickness-1)/2)
    local color=packed(op.rgba)
    while true do
      for by=0,op.thickness-1 do for bx=0,op.thickness-1 do
        put(x-before+bx,y-before+by,color)
      end end
      if x==op.x2 and y==op.y2 then break end
      local twice=2*err
      if twice>=dy then err=err+dy;x=x+sx end
      if twice<=dx then err=err+dx;y=y+sy end
    end
  else
    local color=op.op=="clear_region" and 0 or packed(op.rgba)
    local w,h=op.width or 1,op.height or 1
    -- Use floats to avoid 64-bit integer overflow on long, thin ellipses.
    local function inside(x,y)
      if x<0 or y<0 or x>=w or y>=h then return false end
      local dx,dy=(2*x+1-w)/w,(2*y+1-h)/h
      return dx*dx+dy*dy<=1
    end
    for y=0,h-1 do for x=0,w-1 do
      local draw=true
      if op.op=="ellipse" then
        draw=inside(x,y) and (op.filled or not (inside(x-1,y) and inside(x+1,y) and
          inside(x,y-1) and inside(x,y+1)))
      elseif op.op=="rectangle" then
        draw=op.filled or x==0 or y==0 or x==w-1 or y==h-1
      end
      if draw then put(op.x+x,op.y+y,color) else tick() end
    end end
  end
  tick(true)
end
function M.save_range()
  if not app.activeSprite then return nil end
  local range=app.range
  return {type=range.type,layers=range.layers,frames=range.frames,
    colors=range.colors,tiles=range.tiles,slices=range.slices}
end
function M.restore_range(saved)
  if not saved or not app.activeSprite then return end
  local frames={}
  for _,frame in ipairs(saved.frames) do
    local ok,number=pcall(function() return frame.frameNumber end)
    if ok and app.activeSprite.frames[number]==frame then frames[#frames+1]=frame end
  end
  app.range:clear()
  if saved.type==RangeType.LAYERS then app.range.layers=saved.layers
  elseif saved.type==RangeType.FRAMES and #frames>0 then app.range.frames=frames
  end
  app.range.colors=saved.colors;app.range.tiles=saved.tiles;app.range.slices=saved.slices
end
local function unlink(cel)
  local linked=false
  for _,other in ipairs(cel.layer.cels) do
    if other~=cel and other.image.id==cel.image.id then linked=true;break end
  end
  if not linked then return end
  if not app.command.UnlinkCel or not app.range then
    fail("UNSUPPORTED_CAPABILITY","UnlinkCel and Range API required for linked Cel edits")
  end
  -- The native command preserves ALL Cel user/extension properties. Replacing
  -- a Cel with newCel would discard unknown extension property namespaces.
  local saved=M.save_range()
  local old_layer,old_frame=app.activeLayer,app.activeFrame
  local ok,err=pcall(function()
    app.range:clear()
    app.activeLayer=cel.layer;app.activeFrame=cel.frame
    app.range.layers={cel.layer};app.range.frames={cel.frame}
    app.command.UnlinkCel()
  end)
  local restored,restore_error=pcall(function()
    app.activeLayer=old_layer;app.activeFrame=old_frame
    M.restore_range(saved)
  end)
  if not ok then error(err,0) end
  if not restored then error(restore_error,0) end
  for _,other in ipairs(cel.layer.cels) do
    if other~=cel and other.image.id==cel.image.id then
      fail("EXECUTION_FAILED","Could not isolate linked Cel")
    end
  end
end
function M.commit(batch,tick)
  for _,entry in ipairs(batch.entries) do
    if entry.image then
      if entry.cel then
        unlink(entry.cel)
        entry.cel.image=entry.image;entry.cel.position=Point(entry.left,entry.top)
      else entry.layer.sprite:newCel(entry.layer,entry.frame,entry.image,Point(entry.left,entry.top)) end
      tick(true)
    end
  end
end
function M.read(sprite,layer,action,limits)
  local region=action.region
  if not sprite.frames[action.frame] then fail("INVALID_TARGET","Unknown frame") end
  if region.x+region.width>sprite.width or region.y+region.height>sprite.height then
    fail("INVALID_REQUEST","Read region exceeds canvas")
  end
  local area=region.width*region.height
  if area>limits.max_pixels then fail("LIMIT_EXCEEDED","Pixel read exceeds pixel budget") end
  if action.encoding=="rgba" and area*20+2048>limits.max_message_bytes then
    fail("LIMIT_EXCEEDED","Pixel response too large; reduce region or use RLE")
  end
  local tick=M.clock(limits)
  local data={layer=action.layer,frame=action.frame,region=region,width=region.width,height=region.height,
    encoding=action.encoding}
  local values={};local cel=layer:cel(action.frame);local pc=app.pixelColor
  local previous
  for y=region.y,region.y+region.height-1 do for x=region.x,region.x+region.width-1 do
    local color=0
    if cel then
      local cx,cy=x-cel.position.x,y-cel.position.y
      if cx>=0 and cy>=0 and cx<cel.image.width and cy<cel.image.height then color=cel.image:getPixel(cx,cy) end
    end
    if action.encoding=="rle" and previous==color then values[#values].count=values[#values].count+1
    else
      local rgba={pc.rgbaR(color),pc.rgbaG(color),pc.rgbaB(color),pc.rgbaA(color)}
      if action.encoding=="rle" then
        values[#values+1]={count=1,rgba=rgba};previous=color
        if #values*64+2048>limits.max_message_bytes then
          fail("LIMIT_EXCEEDED","RLE response too large; reduce region")
        end
      else values[#values+1]=rgba end
    end
    tick()
  end end
  if action.encoding=="rle" then data.runs=values else data.pixels=values end
  tick(true)
  return data
end
return M
