"""Validate linked C17, cache invalidation, debug sections and edit timing."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'emberc'))
from project import build
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as d:
 d=Path(d);sources=[]
 # 100 linked translation units, exactly 100 source lines each.
 for i in range(100):
  p=d/f'u{i}.c'
  if i==0:
   lines=['int f1(void);','int main(void) {','int x=f1();']+['x=x+1;']*95+['return x;','}']
  else:
   lines=[f'int f{i}(void) {{','int x=0;']+['x=x+1;']*96+['return x;','}']
  assert len(lines)==100;p.write_text('\n'.join(lines)+'\n');sources.append(p)
 out=d/'app.wasm';cache=d/'cache'
 cold=build(sources,out,cache);warm=build(sources,out,cache)
 sources[1].write_text(sources[1].read_text().replace('x=x+1;','x=x+2;',1))
 edited=build(sources,out,cache)
 assert edited['compiled']==1 and edited['cached']==99 and edited['linked']
 result=subprocess.check_output(['node',str(root/'emberc/run.js'),str(out)],text=True).strip()
 assert result=='192',result
 js="const fs=require('fs');let m=new WebAssembly.Module(fs.readFileSync(process.argv[1]));for(let n of ['.debug_info','.debug_abbrev','.debug_line','.debug_str'])if(!WebAssembly.Module.customSections(m,n).length)throw Error(n);"
 subprocess.run(['node','-e',js,str(out)],check=True)
 # Header changes must invalidate cached object code and change behavior.
 hdr=d/'config.h';hdr.write_text('#define VALUE 40\n');h=d/'header.c';h.write_text('#include "config.h"\nint main(void){return VALUE;}\n')
 build([h],d/'h.wasm',cache);hdr.write_text('#define VALUE 41\n');changed=build([h],d/'h.wasm',cache)
 assert changed['compiled']==1
 assert subprocess.check_output(['node',str(root/'emberc/run.js'),str(d/'h.wasm')],text=True).strip()=='41'
 # A nested include with a non-.h extension outside the source tree must invalidate.
 outside=d/'external includes';outside.mkdir()
 unit=d/'units';unit.mkdir()
 outer=outside/'outer.inc';outer.write_text('#include "value.inc"\n')
 value=outside/'value.inc';value.write_text('#define AMOUNT 13\n')
 consumer=unit/'consumer.c';consumer.write_text('#include "../external includes/outer.inc"\nint main(void){return AMOUNT;}\n')
 build([consumer],d/'external.wasm',cache)
 value.write_text('#define AMOUNT 19\n')
 refreshed=build([consumer],d/'external.wasm',cache)
 assert refreshed['compiled']==1 and refreshed['linked']
 assert subprocess.check_output(['node',str(root/'emberc/run.js'),str(d/'external.wasm')],text=True).strip()=='19'
 print(json.dumps({'source_lines':10000,'linked_units':100,'cold':cold,'warm':warm,'local_edit':edited,'header_invalidation':True,'external_transitive_include_invalidation':True,'dwarf_sections':True,'linked_result':int(result),'backend':'Clang C17 + wasm-ld; EmberC orchestrates caching/linking'},indent=2))
