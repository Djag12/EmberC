import json,os,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'emberc'))
from project import build
from debug import breakpoint
with tempfile.TemporaryDirectory() as d:
 d=Path(d);source=root/'emberc/examples/debug.c'
 build([source],d/'debug.wasm',d/'cache')
 result=breakpoint(d/'debug.wasm',source,6)
 assert result['result']==50 and result['breakpoint_hit']
 try:breakpoint(d/'debug.wasm',source,999)
 except ValueError:pass
 else:raise AssertionError('Invalid source line accepted')
 print(json.dumps(result,indent=2))
