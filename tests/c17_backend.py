"""Broader C17 integration through the explicitly attributed Clang backend.
This does not test or claim standards completeness of the custom frontend.
"""
import json,os,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'emberc'))
from project import build
source=r'''
#define COUNT 8
_Static_assert(sizeof(int)==4,"32-bit int required");
typedef struct {int x; double scale;} Item;
static int data[COUNT]={1,2,3,4,5,6,7,8};
static int total;
int sum(const int *p,int n){int s=0;for(int i=0;i<n;i++)s+=p[i];return s;}
int apply(int (*fn)(const int*,int)){return fn(data,COUNT);}
int main(void){
 Item a={.scale=1.5,.x=4};
 union {unsigned int u;int i;} v={.u=9u};
 enum Mode {A=2,B=3};
 unsigned int bits=0x80000000u;
 long long wide=10000000000LL;
 total=apply(sum);
 int result=total+(int)(a.x*a.scale)+(int)(wide/1000000000LL)+(int)(bits>>31)+v.i;
 switch(B){case A:result=0;break;case B:result+=3;break;default:result=-1;}
 return result+_Generic(a.x,int:7,default:0);
}
'''
with tempfile.TemporaryDirectory() as temp:
 d=Path(temp);p=d/'features.c';p.write_text(source);out=d/'features.wasm'
 result=build([p],out,d/'cache')
 wasm=int(subprocess.check_output(['node',str(root/'emberc/run.js'),str(out)],text=True))
 subprocess.run([os.environ.get('CC','gcc'),'-std=c17','-pedantic-errors',str(p),'-o',str(d/'native')],check=True)
 native=subprocess.run([str(d/'native')]).returncode
 assert wasm==native==72,(wasm,native)
 verify=subprocess.check_output([os.environ.get('LLVM_DWARFDUMP','llvm-dwarfdump'),'--verify',str(out)],text=True)
 assert 'No errors.' in verify
 print(json.dumps({'backend':'Clang C17 + wasm-ld, not custom frontend','native_reference':'GCC','result':wasm,'dwarf_verified':True,'features':['pointers','arrays','structs','unions','enum','typedef','unsigned arithmetic','64-bit integers','floating point','globals','function pointers','preprocessor','switch','_Static_assert','_Generic'],'build':result},indent=2))
