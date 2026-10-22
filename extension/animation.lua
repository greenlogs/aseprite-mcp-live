-- Optional basic timeline editing. No disk I/O or active-frame commands.
local M={}
local function fail(code,message) error({code=code,message=message},0) end
local function directions()
  return {forward=AniDir.FORWARD,reverse=AniDir.REVERSE,
    pingpong=AniDir.PING_PONG,pingpong_reverse=AniDir.PING_PONG_REVERSE}
end
function M.available()
  local ok,value=pcall(function()
    local d=directions()
    return app.apiVersion>=28 and d.forward~=nil and d.reverse~=nil and
      d.pingpong~=nil and d.pingpong_reverse~=nil
  end)
  return ok and value
end
function M.metadata(sprite)
  local durations,tags={},{}
  local names={}
  if M.available() then for name,value in pairs(directions()) do names[value]=name end end
  for _,frame in ipairs(sprite.frames) do durations[#durations+1]=math.floor(frame.duration*1000+0.5) end
  for _,tag in ipairs(sprite.tags) do
    tags[#tags+1]={name=tag.name,from_frame=tag.fromFrame.frameNumber,
      to_frame=tag.toFrame.frameNumber,direction=names[tag.aniDir] or tostring(tag.aniDir)}
  end
  return {frame_durations_ms=durations,tags=tags}
end
function M.signature(sprite)
  return json.encode(M.metadata(sprite))
end
local function frame_range(op,count)
  if op.from_frame>op.to_frame or op.to_frame>count then
    fail("INVALID_TARGET","Animation frame range is outside the current timeline")
  end
end
function M.validate(sprite,operations,limits)
  if not M.available() then fail("UNSUPPORTED_CAPABILITY","Animation API unavailable") end
  for _,name in ipairs{"newFrame","deleteFrame","newTag","deleteTag"} do
    local ok,value=pcall(function() return sprite[name] end)
    if not ok or type(value)~="function" then fail("UNSUPPORTED_CAPABILITY","Missing Sprite:"..name) end
  end
  if sprite.colorMode~=ColorMode.RGB then fail("UNSUPPORTED_CAPABILITY","Animation edits require RGB") end
  if #operations>limits.max_operations then fail("LIMIT_EXCEEDED","Too many animation operations") end
  local frame_count=#sprite.frames
  if frame_count>256 then fail("LIMIT_EXCEEDED","Animation timeline exceeds 256 frames") end
  -- Native frame cloning can copy any current frame after an earlier delete.
  -- Budget the largest Cel per layer for each appended frame, conservatively.
  local per_frame=0
  local function walk(layers)
    for _,layer in ipairs(layers) do
      if not layer.isEditable or layer.isReference or layer.isTilemap or layer.isBackground then
        fail("UNSUPPORTED_CAPABILITY","Animation requires editable ordinary layers/groups")
      end
      if layer.isGroup then walk(layer.layers)
      else
        local largest=0
        for _,cel in ipairs(layer.cels) do largest=math.max(largest,cel.image.width*cel.image.height) end
        per_frame=per_frame+largest
      end
    end
  end
  walk(sprite.layers)
  local tags={}
  for _,tag in ipairs(sprite.tags) do
    if tags[tag.name] then fail("INVALID_TARGET","Duplicate tag names must be resolved before editing") end
    tags[tag.name]=true
  end
  local copied=0
  for _,op in ipairs(operations) do
    if op.op=="add_frames" then
      frame_count=frame_count+op.count; copied=copied+per_frame*op.count
      if frame_count>256 or copied>limits.max_pixels then fail("LIMIT_EXCEEDED","Animation frame/copy budget exceeded") end
    elseif op.op=="delete_frame" then
      if op.frame>frame_count then fail("INVALID_TARGET","Unknown animation frame") end
      if frame_count<=1 then fail("INVALID_REQUEST","Cannot delete the only frame") end
      frame_count=frame_count-1
    elseif op.op=="set_frame_duration" then frame_range(op,frame_count)
    elseif op.op=="set_tag" then
      frame_range(op,frame_count); tags[op.tag]=true
    elseif op.op=="delete_tag" then
      if not tags[op.tag] then fail("INVALID_TARGET","Unknown animation tag") end
      tags[op.tag]=nil
    else fail("INVALID_REQUEST","Unknown animation operation") end
  end
end
local function find_tag(sprite,name)
  for _,tag in ipairs(sprite.tags) do if tag.name==name then return tag end end
end
function M.apply_one(sprite,op,check_time)
  if op.op=="add_frames" then
    for _=1,op.count do
      local frame=sprite:newFrame()
      frame.duration=op.duration_ms/1000
      check_time()
    end
  elseif op.op=="delete_frame" then sprite:deleteFrame(sprite.frames[op.frame])
  elseif op.op=="set_frame_duration" then
    for index=op.from_frame,op.to_frame do
      sprite.frames[index].duration=op.duration_ms/1000; check_time()
    end
  elseif op.op=="set_tag" then
    local tag=find_tag(sprite,op.tag)
    if not tag then tag=sprite:newTag(op.from_frame,op.to_frame);tag.name=op.tag end
    -- Move the upper endpoint first when expanding right, to avoid transient
    -- inverted ranges on implementations that enforce tag endpoint order.
    if op.from_frame>tag.toFrame.frameNumber then
      tag.toFrame=sprite.frames[op.to_frame];tag.fromFrame=sprite.frames[op.from_frame]
    else tag.fromFrame=sprite.frames[op.from_frame];tag.toFrame=sprite.frames[op.to_frame] end
    tag.aniDir=directions()[op.direction]
  elseif op.op=="delete_tag" then
    local tag=find_tag(sprite,op.tag)
    if not tag then fail("INVALID_TARGET","Tag was removed by a preceding frame deletion") end
    sprite:deleteTag(tag)
  end
  check_time()
end
return M
