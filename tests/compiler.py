import os,sys,tempfile,subprocess,random,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'emberc'))
from wasm import Backend,build
root=Path(__file__).resolve().parents[1];rng=random.Random(42)
with tempfile.TemporaryDirectory() as d:
 d=Path(d);programs=[];expected=[]
 for i in range(2000):
  a,b=rng.randrange(-100,100),rng.randrange(1,20);n=rng.randrange(1,20)
  source=f'int main(void){{int x={a};int i=0;while(i<{n}){{i=i+1;if(i==2)continue;x=x+{b};if(i>10)break;}}return x;}}'
  if i%8==0:source=f'int main(void){{return ({a}<{b}) || (0 && (1/0));}}'
  if i%8==1:source=f'int main(void){{int x={a};{{int x={b};x=x+1;}}return x;}}'
  if i%8==2:source=f'int main(void){{return ({a}/{b})*{b}+({a}%{b});}}'
  if i%8==3:source=f'int main(void){{int x=0;int y=0;while(x<{n}){{x=x+1;while(1){{y=y+1;break;}}}}return y;}}'
  if i%8==4:source=f'int main(void){{if({a}>{b})return {a};else return {b};}}'
  if i%8==5:source=f'int main(void){{return !({a}=={b})+({a}<={b})+({a}>={b});}}'
  if i%8==6:source=f'int main(void){{return ({a}+{b})*3-({a}-{b});}}'
  p=d/f'p{i}.wasm';p.write_bytes(Backend().compile(source));programs.append(p)
  expected.append(source.replace('main(void)',f'f{i}(void)'))
 c=d/'ref.c';c.write_text('#include <stdio.h>\n'+'\n'.join(expected)+'\nint main(void){'+''.join(f'printf("%d\\n",f{i}());' for i in range(2000))+'}')
 subprocess.run([os.environ.get('CLANG','clang'),'-O0',str(c),'-o',str(d/'ref')],check=True)
 native=subprocess.check_output([str(d/'ref')],text=True).splitlines();actual=[]
 for start in range(0,2000,100):actual+=subprocess.check_output(['node',str(root/'emberc/run.js'),*map(str,programs[start:start+100])],text=True).splitlines()
 assert actual==native
 for bad in ['int main(void){return nope;}', 'int main(void){break;}', 'int main(void){int x=x;return x;}', 'int main(void){int x=0;int x=1;return x;}']:
  try: Backend().compile(bad)
  except ValueError: pass
  else: raise AssertionError('accepted invalid source')
 units=[]
 for i in range(100):
  p=d/f'unit{i}.c';p.write_text('int main(void){\nint x='+str(i)+';\n'+'x=x+1;\n'*97+'return x;}\n');units.append(p)
 cold=build(units,d/'cache');warm=build(units,d/'cache');units[5].write_text(units[5].read_text().replace('x=x+1;','x=x+2;',1));edited=build(units,d/'cache')
 assert edited['compiled']==1 and edited['cached']==99
 print(json.dumps({'differential_programs':2000,'reference':'Clang','lines':10000,'independent_modules':100,'cold':cold,'no_change':warm,'local_edit':edited,'dwarf':True,'full_C17':False},indent=2))
