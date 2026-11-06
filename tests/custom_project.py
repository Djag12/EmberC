import json,os,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'emberc'))
from custom_project import build
from debug import breakpoint
with tempfile.TemporaryDirectory() as temp:
 d=Path(temp);sources=[]
 for i in range(100):
  lines=(['int f1(void);','int main(void) {','int x=f1();']+['x=x+1;']*95+['return x;','}']) if i==0 else ([f'int f{i}(void) {{','int x=0;']+['x=x+1;']*96+['return x;','}'])
  assert len(lines)==100;p=d/f'u{i}.c';p.write_text('\n'.join(lines)+'\n');sources.append(p)
 out=d/'app.wasm';cache=d/'cache';cold=build(sources,out,cache);warm=build(sources,out,cache)
 sources[1].write_text(sources[1].read_text().replace('x=x+1;','x=x+2;',1));edit=build(sources,out,cache)
 assert edit['compiled']==1 and edit['cached']==99
 assert subprocess.check_output(['node',str(root/'emberc/run.js'),str(out)],text=True).strip()=='192'
 # LLVM is a reader/validator only; this WASM was generated entirely by EmberC.
 verified=subprocess.check_output([os.environ.get('LLVM_DWARFDUMP','llvm-dwarfdump'),'--verify',str(out)],text=True)
 assert 'No errors.' in verified
 hit=breakpoint(out,sources[0],99);assert hit['result']==192
 # Compare custom linked result to native Clang with all 100 source files.
 subprocess.run([os.environ.get('CLANG','clang'),'-std=c17',*map(str,sources),'-o',str(d/'native')],check=True)
 assert subprocess.run([str(d/'native')]).returncode==192
 example=root/'emberc/examples/functions.c';build([example],d/'functions.wasm',d/'functions-cache')
 assert subprocess.check_output(['node',str(root/'emberc/run.js'),str(d/'functions.wasm')],text=True).strip()=='127'
 for source in ['int f(int x){return x;} int main(void){return f();}', 'int main(void){return missing();}', 'int main(void){return 1;} int main(void){return 2;}', 'int f(int x){int x=1;return x;} int main(void){return f(2);}']:
  bad=d/'bad.c';bad.write_text(source)
  try:build([bad],d/'bad.wasm',d/'bad-cache')
  except ValueError:pass
  else:raise AssertionError('Invalid program accepted')
 print(json.dumps({'lines':10000,'linked_units':100,'cold':cold,'warm':warm,'local_edit':edit,'custom_dwarf_verified':True,'source_breakpoint':hit,'native_clang_match':True},indent=2))
