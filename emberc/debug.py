"""Resolve a source line via LLVM's DWARF reader, then actually pause in Node.
Usage: LLVM_DWARFDUMP=llvm-dwarfdump python3 debug.py app.wasm source.c 6
"""
import json,os,re,subprocess,sys
from pathlib import Path

def breakpoint(wasm,source,line):
 dump=subprocess.check_output([os.environ.get('LLVM_DWARFDUMP','llvm-dwarfdump'),'--debug-line',str(wasm)],text=True)
 matches=[]
 for table in dump.split('debug_line[')[1:]:
  files=dict(re.findall(r'file_names\[\s*(\d+)\]:\s*name: "([^"]+)"',table))
  for row in table.splitlines():
   m=re.match(r'0x([0-9a-f]+)\s+(\d+)\s+(\d+)\s+(\d+)\s',row)
   if m and int(m[2])==line and Path(files.get(m[4], '')).name==Path(source).name and 'is_stmt' in row and 'end_sequence' not in row:
    matches.append(int(m[1],16))
 if not matches:raise ValueError('No executable DWARF statement at requested file/line')
 if len(matches)>1:raise ValueError('Ambiguous file/line: use a unique source filename and line')
 result=json.loads(subprocess.check_output(['node',str(Path(__file__).with_name('breakpoint.js')),str(wasm),str(matches[0])],text=True))
 return dict(result,source=Path(source).name,line=line,dwarf_address=matches[0])
if __name__=='__main__':print(json.dumps(breakpoint(sys.argv[1],sys.argv[2],int(sys.argv[3])),indent=2))
