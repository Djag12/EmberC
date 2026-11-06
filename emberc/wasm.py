"""Direct WebAssembly binary backend for EmberC's documented integer C subset."""
from frontend import Parser
from dwarf import sections as dwarf_sections
class LocatedParser(Parser):
 def __init__(self,source):super().__init__(source);self.lines={}
 def statement(self):
  line=self.tokens[self.i][1];node=super().statement();self.lines[id(node)]=line;return node

import hashlib,json,sys,time
from pathlib import Path

def leb(n,signed=False):
 out=bytearray()
 while True:
  b=n&127;n >>=7
  done=(n==0 and (not signed or not b&64)) or (signed and n==-1 and b&64)
  out.append(b if done else b|128)
  if done:return bytes(out)
def vec(xs):return leb(len(xs))+b''.join(xs)
def string(s):b=s.encode();return leb(len(b))+b
def section(i,b):return bytes([i])+leb(len(b))+b
class Backend:
 def __init__(self):self.labels=[]
 def expr(self,n):
  k=n[0]
  if k=='call':
   if n[1] not in self.function_indices:raise ValueError('Undefined function '+n[1])
   args=n[2] if len(n)>2 else []
   if len(args)!=self.function_signatures[n[1]]:raise ValueError('Argument count mismatch for '+n[1])
   return b''.join(self.expr(arg) for arg in args)+b'\x10'+leb(self.function_indices[n[1]])
  if k=='update':
   get=b'\x20'+leb(n[1]-1);value=get+b'\x41'+leb(n[2],True)+b'\x6a'
   return get+value+b'\x21'+leb(n[1]-1) if n[3] else value+b'\x22'+leb(n[1]-1)
  if k=='number':return b'\x41'+leb(n[1],True)
  if k=='var':return b'\x20'+leb(n[1]-1)
  if k=='unary':
   e=self.expr(n[2]);return {'+':e,'-':b'\x41\0'+e+b'\x6b','!':e+b'\x45','~':e+b'\x41\x7f\x73'}[n[1]]
  op=n[1];a=self.expr(n[2]);b=self.expr(n[3])
  if op in ('&&','||'):
   return a+b'\x04\x7f'+(b+b'\x45\x45\x05\x41\0' if op=='&&' else b'\x41\x01\x05'+b+b'\x45\x45')+b'\x0b'
  return a+b+bytes([{'+':0x6a,'-':0x6b,'*':0x6c,'/':0x6d,'%':0x6f,'&':0x71,'|':0x72,'^':0x73,'<<':0x74,'>>':0x75,'==':0x46,'!=':0x47,'<':0x48,'>':0x4a,'<=':0x4c,'>=':0x4e}[op]])
 def emit_stmt(self,n):
  k=n[0]
  if id(n) in self.source_lines and k not in ('block','empty'):
   self.rows.append((len(self.code),self.source_lines[id(n)]))
  if k=='empty':return
  if k=='block':
   for node in n[1]:self.emit_stmt(node)
  elif k=='expr':self.code+=self.expr(n[1])+b'\x1a'
  elif k=='set':self.code+=self.expr(n[2])+b'\x21'+leb(n[1]-1)
  elif k=='return':self.code+=self.expr(n[1])+b'\x0f'
  elif k=='if':
   self.code+=self.expr(n[1])+b'\x04\x40';self.labels.append('if')
   self.emit_stmt(n[2]);self.code+=b'\x05';self.emit_stmt(n[3]);self.code+=b'\x0b';self.labels.pop()
  elif k=='while':
   self.code+=b'\x02\x40\x03\x40'+self.expr(n[1])+b'\x45\x0d\x01';self.labels+=['break','continue']
   self.emit_stmt(n[2]);self.code+=b'\x0c\0\x0b\x0b';self.labels=self.labels[:-2]
  elif k=='for':
   self.emit_stmt(n[1]);self.code+=b'\x02\x40\x03\x40'+self.expr(n[2])+b'\x45\x0d\x01'
   self.labels+=['break','loop'];self.code+=b'\x02\x40';self.labels.append('continue')
   self.emit_stmt(n[4]);self.code+=b'\x0b';self.labels.pop();self.emit_stmt(n[3])
   self.code+=b'\x0c\0\x0b\x0b';self.labels=self.labels[:-2]
  elif k=='do':
   self.code+=b'\x02\x40\x03\x40\x02\x40';self.labels+=['break','loop','continue']
   self.emit_stmt(n[1]);self.code+=b'\x0b';self.labels.pop()
   self.code+=self.expr(n[2])+b'\x0d\0\x0b\x0b';self.labels=self.labels[:-2]
  elif k in ('break','continue'):self.code+=b'\x0c'+leb(list(reversed(self.labels)).index(k))
  else:raise ValueError(k)
 def compile(self,source,filename='source.c'):
  parser=LocatedParser(source);tree,slots=parser.parse();self.source_lines=parser.lines;self.code=bytearray();self.rows=[];self.labels=[]
  self.emit_stmt(tree);self.code+=b'\x41\0\x0b'
  locals=vec([leb(slots)+b'\x7f'] if slots else [])
  body=locals+bytes(self.code);start=1+len(leb(len(body)))+len(locals);end=start+len(self.code)
  module=b'\0asm\x01\0\0\0'+section(1,vec([b'\x60\0\x01\x7f']))+section(3,vec([b'\0']))+section(7,vec([string('main')+b'\0\0']))+section(10,vec([leb(len(body))+body]))
  debug=dwarf_sections(filename,[(start+offset,line) for offset,line in self.rows],start,end)
  for name,data in debug.items():module+=section(0,string(name)+data)
  return module

def build(paths,out):
 """Content-addressed, independent translation-unit cache; no cross-file linking."""
 out=Path(out);out.mkdir(parents=True,exist_ok=True);compiled=0;cached=0;start=time.perf_counter()
 for p in paths:
  p=Path(p);source=p.read_text();key=hashlib.sha256((Path(__file__).read_text()+Path(__file__).with_name('frontend.py').read_text()+Path(__file__).with_name('dwarf.py').read_text()+str(p)+source).encode()).hexdigest();dest=out/(key+'.wasm')
  if dest.exists():cached+=1
  else:dest.write_bytes(Backend().compile(source,str(p)));compiled+=1
  (out/(p.stem+'.wasm')).write_bytes(dest.read_bytes())
 return {'compiled':compiled,'cached':cached,'elapsed_ms':(time.perf_counter()-start)*1000}
if __name__=='__main__':print(json.dumps(build(sys.argv[2:],sys.argv[1])))
