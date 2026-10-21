-- Render into an independent RGB Image. PNG uses bounded in-memory stored
-- deflate blocks: no temporary files, Sprite copies, save flags or history.
local M={}
local function fail(code,message) error({code=code,message=message},0) end
local crc_table={}
for n=0,255 do
  local c=n
  for _=1,8 do c=(c&1)==1 and (0xedb88320~(c>>1)) or (c>>1) end
  crc_table[n]=c
end
local function chunk(kind,data)
  local body=kind..data; local crc=0xffffffff
  for i=1,#body do crc=crc_table[(crc~body:byte(i))&255]~(crc>>8) end
  return string.pack(">I4",#data)..body..string.pack(">I4",crc~0xffffffff)
end
local function deflate(raw)
  local blocks={"\120\1"}; local a,b=1,0
  for i=1,#raw do a=(a+raw:byte(i))%65521; b=(b+a)%65521 end
  for start=1,#raw,65535 do
    local part=raw:sub(start,start+65534)
    blocks[#blocks+1]=string.char(start+#part>#raw and 1 or 0)..string.pack("<I2I2",#part,0xffff~#part)..part
  end
  blocks[#blocks+1]=string.pack(">I4",(b<<16)|a)
  return table.concat(blocks)
end
local alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
local function base64(raw)
  local parts={}
  for i=1,#raw,3 do
    local a,b,c=raw:byte(i,i+2); b=b or 0; c=c or 0
    local bits=(a<<16)|(b<<8)|c
    local first=(bits>>18)&63; local second=(bits>>12)&63
    local third=(bits>>6)&63; local fourth=bits&63
    parts[#parts+1]=alphabet:sub(first+1,first+1)..alphabet:sub(second+1,second+1)..
      (i+1<=#raw and alphabet:sub(third+1,third+1) or "=")..
      (i+2<=#raw and alphabet:sub(fourth+1,fourth+1) or "=")
  end
  return table.concat(parts)
end
function M.render(sprite,action,limits)
  if not sprite.frames[action.frame] then fail("INVALID_TARGET","Unknown preview frame") end
  local region=action.region or {x=0,y=0,width=sprite.width,height=sprite.height}
  if region.x<0 or region.y<0 or region.width<1 or region.height<1 or
      region.x+region.width>sprite.width or region.y+region.height>sprite.height then
    fail("INVALID_REQUEST","Preview region must be inside the canvas")
  end
  local scale=action.scale
  local width,height=region.width*scale,region.height*scale
  if width*height>limits.max_pixels then fail("LIMIT_EXCEEDED","Preview too large; reduce region or scale") end
  -- Filter byte per row + RGBA + small PNG/deflate framing, checked before allocation.
  local raw_size=(width*4+1)*height
  if raw_size+math.ceil(raw_size/65535)*5+100>limits.max_png_bytes then
    fail("LIMIT_EXCEEDED","PNG budget exceeded; reduce region or scale")
  end
  local image=Image(region.width,region.height,ColorMode.RGB)
  image:drawSprite(sprite,action.frame,Point(-region.x,-region.y))
  local rows={}
  for y=0,region.height-1 do
    local row={"\0"}
    for x=0,region.width-1 do
      row[#row+1]=string.rep(string.pack("<I4",image:getPixel(x,y)),scale)
    end
    row=table.concat(row)
    for _=1,scale do rows[#rows+1]=row end
  end
  local raw=table.concat(rows)
  local png="\137PNG\r\n\26\n"..chunk("IHDR",string.pack(">I4I4BBBBB",width,height,8,6,0,0,0))..
    chunk("IDAT",deflate(raw))..chunk("IEND","")
  if #png>limits.max_png_bytes then fail("LIMIT_EXCEEDED","PNG too large; reduce region or scale") end
  local encoded=base64(png)
  if #encoded+2048>limits.max_message_bytes then fail("LIMIT_EXCEEDED","Message too large; reduce region or scale") end
  return {png={mime_type="image/png",encoding="base64",data=encoded,width=width,height=height,
    frame=action.frame,scale=scale,region=region}}
end
return M
