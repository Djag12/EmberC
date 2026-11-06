"""Project-owned incremental integer-C compiler and WASM linker.
Supports zero-argument int functions, calls, separate source units, and DWARF.
No Clang, LLVM, linker, or compiler subprocess is used to build the program.
"""
import argparse,hashlib,json,time
from pathlib import Path
from frontend import CompileError, KEYWORDS
from wasm import Backend,LocatedParser,leb,vec,string,section
from dwarf import sections as dwarf_sections

class ProgramParser(LocatedParser):
 def __init__(self,source):super().__init__(source);self.allow_calls=True;self.pending_params=None
 def block(self):
  if self.pending_params is None:return super().block()
  self.take('{');self.scopes.append(self.pending_params);self.pending_params=None;out=[]
  while self.peek()!='}':
   if self.peek()=='<eof>':self.fail('Unterminated function')
   out.append(self.statement())
  self.take('}');self.scopes.pop();return ['block',out]
 def parse_program(self):
  functions=[]
  while self.peek()!='<eof>':
   self.take('int');name=self.take()
   if not name.isidentifier() or (name in KEYWORDS and name!='main'):self.fail('Invalid function name')
   self.take('(');params=[]
   if self.peek()=='void':self.take()
   elif self.peek()!=')':
    while True:
     self.take('int');param=self.name()
     if param in params:self.fail('Duplicate parameter')
     params.append(param)
     if self.peek()!=',':break
     self.take(',')
   self.take(')')
   if self.peek()==';':
    self.take(';');functions.append({'name':name,'parameters':len(params),'prototype':True});continue
   self.slots=len(params);self.pending_params={name:i+1 for i,name in enumerate(params)};self.lines={};tree=self.block()
   # Persist node source locations by tree paths rather than Python identity.
   locations=[]
   def visit(node,path):
    if isinstance(node,list):
     if id(node) in self.lines:locations.append((path,self.lines[id(node)]))
     for i,child in enumerate(node):visit(child,path+[i])
   visit(tree,[])
   functions.append({'name':name,'tree':tree,'slots':self.slots,'parameters':len(params),'locations':locations})
  return functions

def build(sources,output,cache):
 start=time.perf_counter();cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
 compiler=b''.join(Path(__file__).with_name(f).read_bytes() for f in ['custom_project.py','frontend.py','wasm.py','dwarf.py'])
 units=[];names=[];signatures={}
 for source in map(Path,sources):
  key=hashlib.sha256(compiler+str(source.resolve()).encode()+source.read_bytes()).hexdigest()
  astpath=cache/(key+'.json')
  if astpath.exists():functions=json.loads(astpath.read_text())
  else:
   functions=ProgramParser(source.read_text()).parse_program();astpath.write_text(json.dumps(functions))
  for f in functions:
   if f['name'] in signatures and signatures[f['name']]!=f['parameters']:
    raise CompileError('Conflicting function declarations for '+f['name'])
   signatures[f['name']]=f['parameters']
  definitions=[f for f in functions if not f.get('prototype',False)]
  units.append((source,key,definitions));names.extend(f['name'] for f in definitions)
 if len(set(names))!=len(names):raise CompileError('Duplicate global function')
 if 'main' not in names:raise CompileError('Missing main')
 names=sorted(names);indices={n:i for i,n in enumerate(names)}
 if signatures['main']!=0:raise CompileError('main must take no arguments')
 symbols=hashlib.sha256(json.dumps(signatures,sort_keys=True).encode()).hexdigest()
 compiled=cached=0;objects={}
 for source,key,functions in units:
  objpath=cache/(key+symbols+'.obj.json')
  if objpath.exists():unit=json.loads(objpath.read_text());cached+=1
  else:
   compiled+=1;unit=[]
   for f in functions:
    backend=Backend();backend.function_indices=indices;backend.function_signatures=signatures;backend.code=bytearray();backend.rows=[];backend.source_lines={}
    for path,line in f['locations']:
     node=f['tree']
     for i in path:node=node[i]
     backend.source_lines[id(node)]=line
    backend.emit_stmt(f['tree']);backend.code+=b'\x41\0\x0b'
    count=f['slots']-f['parameters'];locals=vec([leb(count)+b'\x7f'] if count else [])
    unit.append({'name':f['name'],'body':(locals+backend.code).hex(),'local_bytes':len(locals),'rows':backend.rows,'source':str(source.resolve())})
   objpath.write_text(json.dumps(unit))
  for f in unit:objects[f['name']]=f
 bodyparts=[];line_tables=b'';info=b'';abbrev=b'';cursor=len(leb(len(names)))
 for name in names:
  f=objects[name];body=bytes.fromhex(f['body']);part=leb(len(body))+body
  begin=cursor+len(leb(len(body)))+f['local_bytes'];end=cursor+len(part)
  d=dwarf_sections(f['source'],[(begin+offset,line) for offset,line in f['rows']],begin,end,name,len(line_tables))
  line_tables+=d['.debug_line'];info+=d['.debug_info'];abbrev=d['.debug_abbrev'];bodyparts.append(part);cursor=end
 arities=sorted(set(signatures.values()));types=[b'\x60'+vec([b'\x7f']*arity)+b'\x01\x7f' for arity in arities]
 module=b'\0asm\x01\0\0\0'+section(1,vec(types))+section(3,vec([leb(arities.index(signatures[name])) for name in names]))+section(7,vec([string('main')+b'\0'+leb(indices['main'])]))+section(10,vec(bodyparts))
 for name,data in {'.debug_abbrev':abbrev,'.debug_info':info,'.debug_line':line_tables}.items():module+=section(0,string(name)+data)
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(module)
 return {'compiled':compiled,'cached':cached,'linked_functions':len(names),'milliseconds':(time.perf_counter()-start)*1000,'backend':'EmberC custom lexer/parser/WASM linker/DWARF encoder'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('sources',nargs='+');p.add_argument('-o',required=True);p.add_argument('--cache',default='.ember-custom-cache');a=p.parse_args();print(json.dumps(build(a.sources,a.o,a.cache),indent=2))
