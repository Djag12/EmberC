"""Differential tests for custom loop lowering, side effects and C precedence."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'emberc'))
from custom_project import build
cases=[
'int main(void){int s=0;for(int i=0;i<20;i++){if(i%3==0)continue;if(i==17)break;s+=i;}return s;}',
'int main(void){int i=0;int s=0;do{i++;if(i<5)continue;s+=i;}while(i<10);return s;}',
'int main(void){int s=0;for(int i=0;i<6;++i){for(int j=0;j<8;++j){if(j==2)continue;if(j==5)break;s+=i*j;}}return s;}',
'int main(void){int i=0;for(;;){if(++i==8)break;}return i;}',
'int main(void){int i=3;int a=i++;int b=++i;return a*10+b;}',
'int main(void){int i=0;int a=0&&i++;int b=1||++i;return i+a+b;}',
'int main(void){int x=7;x<<=3;x|=2;x^=3;x&=63;x>>=1;x%=11;x*=3;x/=2;x-=1;return x;}',
'int main(void){return 3|4^6&7==7;}',
'int main(void){int i=1;for(int i=0;i<4;i++){}return i;}',
'int add(int x){return x+2;} int main(void){add(4);return add(10);}',
'int main(void){int i=1;int a=--i;int b=i--;return a+b+i;}',
'int main(void){return ~7 & 255;}',
]
# Parameterized, defined-behavior loop families; no overflow or unsequenced updates.
for n in range(1,101):
 cases.append(f'int main(void){{int s=0;for(int i=0;i<{n};i++){{if(i%4==0)continue;s+=(i&7);}}return s;}}')
 cases.append(f'int main(void){{int i={n};int s=0;do{{s+=i%9;--i;}}while(i>0);return s;}}')
with tempfile.TemporaryDirectory() as temp:
 d=Path(temp);outputs=[]
 for i,source in enumerate(cases):
  p=d/f'p{i}.c';p.write_text(source);out=d/f'p{i}.wasm';build([p],out,d/'cache')
  outputs.append(int(subprocess.check_output(['node',str(root/'emberc/run.js'),str(out)],text=True)))
 # One native executable returns full signed values, avoiding exit-status truncation.
 native='#include <stdio.h>\n'+'\n'.join(s.replace('main(',f'case{i}(').replace('int add(',f'int add{i}(').replace('return add(',f'return add{i}(').replace('{add(',f'{{add{i}(') for i,s in enumerate(cases))
 native+='\nint main(void){'+''.join(f'printf("%d\\n",case{i}());' for i in range(len(cases)))+'return 0;}'
 (d/'oracle.c').write_text(native)
 subprocess.run([os.environ.get('CLANG','clang'),'-std=c17','-O0',str(d/'oracle.c'),'-o',str(d/'oracle')],check=True)
 expected=list(map(int,subprocess.check_output([str(d/'oracle')],text=True).splitlines()))
 assert outputs==expected,[(i,a,b) for i,(a,b) in enumerate(zip(outputs,expected)) if a!=b]
 bad=['int f(int x); int f(void){return 1;} int main(void){return f();}', 'int main(void){for(int i=0;i<2;i++){}return i;}', 'int main(void){continue;return 0;}', 'int while(void){return 0;} int main(void){return 1;}', 'int main(void){int x=1;(x+1)++;return x;}']
 for source in bad:
  p=d/'bad.c';p.write_text(source)
  try:build([p],d/'bad.wasm',d/'cache')
  except ValueError:pass
  else:raise AssertionError(source)
 print(json.dumps({'differential_programs':len(cases),'invalid_programs_rejected':len(bad),'reference':os.environ.get('CLANG','clang'),'features':['for','do while','nested break/continue','prefix/postfix increment','compound assignment','bitwise','shift','side-effect short circuit'],'full_C17':False},indent=2))
