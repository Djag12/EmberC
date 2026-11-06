"""Project-owned DWARF v4 encoder for a single WASM compilation unit."""
import struct
from pathlib import Path

def uleb(n):
 out=bytearray()
 while True:
  b=n&127;n>>=7;out.append(b|(128 if n else 0))
  if not n:return bytes(out)
def sleb(n):
 out=bytearray()
 while True:
  b=n&127;n>>=7;done=(n==0 and not b&64) or (n==-1 and b&64);out.append(b|(0 if done else 128))
  if done:return bytes(out)
def u32(n):return struct.pack('<I',n)
def z(s):return str(s).encode()+b'\0'
def unit(body):return u32(len(body))+body

def sections(filename,rows,start,end,function="main",statement_offset=0):
 # Compile unit and child subprogram abbreviations; all offsets address the
 # WASM code section payload, as required by WASM DWARF conventions.
 attributes=[(3,8),(0x1b,8),(0x13,5),(0x10,0x17),(0x11,1),(0x12,6)]
 abbrev=uleb(1)+uleb(0x11)+b'\1'+b''.join(uleb(a)+uleb(f) for a,f in attributes)+b'\0\0'
 abbrev+=uleb(2)+uleb(0x2e)+b'\0'+b''.join(uleb(a)+uleb(f) for a,f in [(3,8),(0x11,1),(0x12,6)])+b'\0\0\0'
 file=Path(filename)
 info=struct.pack('<HI',4,0)+b'\4'+uleb(1)+z(file.name)+z(file.parent)+struct.pack('<H',2)+u32(statement_offset)+u32(start)+u32(end-start)
 info+=uleb(2)+z(function)+u32(start)+u32(end-start)+b'\0'
 # One file, current directory, standard opcode lengths from DWARF4.
 header=bytes([1,1,1,251,14,13])+bytes([0,1,1,1,1,0,0,0,1,0,0,1])+b'\0'+z(file.name)+b'\0\0\0\0'
 program=b'\0'+uleb(5)+b'\2'+u32(start);address=start;line=1
 for offset,newline in sorted(set(rows)):
  if offset<address:raise ValueError('Nonmonotonic DWARF addresses')
  if offset!=address:program+=b'\2'+uleb(offset-address);address=offset
  if newline!=line:program+=b'\3'+sleb(newline-line);line=newline
  program+=b'\1'
 if end>address:program+=b'\2'+uleb(end-address)
 program+=b'\0\1\1'
 line_data=struct.pack('<H',4)+u32(len(header))+header+program
 return {'.debug_abbrev':abbrev,'.debug_info':unit(info),'.debug_line':unit(line_data)}
