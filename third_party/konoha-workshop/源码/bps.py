"""Small BPS v1 writer/reader, SourceRead and TargetRead; verifies all three CRCs."""
import zlib,struct

def integer(n):
 out=bytearray()
 while True:
  b=n&127;n>>=7
  if not n:out.append(b|128);return out
  out.append(b);n-=1

def encode(source,target):
 patch=bytearray(b'BPS1')+integer(len(source))+integer(len(target))+integer(0);at=0
 while at<len(target):
  same=at<len(source)and source[at]==target[at];end=at+1
  while end<len(target)and(end<len(source)and source[end]==target[end])==same:end+=1
  patch+=integer(((end-at-1)<<2)|(0 if same else 1))
  if not same:patch+=target[at:end]
  at=end
 patch+=struct.pack('<II',zlib.crc32(source),zlib.crc32(target));patch+=struct.pack('<I',zlib.crc32(patch));return bytes(patch)

def apply(source,patch):
 assert patch[:4]==b'BPS1';assert zlib.crc32(patch[:-4])==struct.unpack('<I',patch[-4:])[0]
 at=4
 def number():
  nonlocal at
  val=0;shift=1
  while True:
   b=patch[at];at+=1;val+=(b&127)*shift
   if b&128:return val
   shift<<=7;val+=shift
 source_size=number();target_size=number();meta=number();at+=meta
 assert len(source)==source_size and zlib.crc32(source)==struct.unpack('<I',patch[-12:-8])[0]
 out=bytearray()
 while len(out)<target_size:
  action=number();length=(action>>2)+1;kind=action&3
  if kind==0:out+=source[len(out):len(out)+length]
  elif kind==1:out+=patch[at:at+length];at+=length
  else:raise AssertionError('Unsupported action')
 assert at==len(patch)-12 and zlib.crc32(out)==struct.unpack('<I',patch[-8:-4])[0]
 return bytes(out)
