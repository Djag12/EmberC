"""Exercise the shipped C17 driver end to end on 2,000 freestanding programs.

Compile and run each independent program as a WASM module. Compile a native
translation unit of the same functions with Clang to obtain full signed results.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "emberc"))
from project import build


def program(index, rng):
    values = [rng.randrange(-25, 26) for _ in range(4)]
    numbers = ",".join(map(str, values))
    # All inputs stay well within signed integer range on both tested targets.
    bodies = [
        f"int a[4]={{{numbers}}}; int *p=a; return p[0]*p[2]-p[1]*p[3];",
        f"struct Pair {{int x,y;}} p={{{values[0]},{values[1]}}}; return p.x*p.y;",
        f"int a[4]={{{numbers}}}; int t=0; for(int i=0;i<4;i++) t+=a[i]*i; return t;",
        f"unsigned x={index}u; return (int)((x*2654435761u)>>21);",
        f"double x={values[0]}.0/4.0; return (int)(8.0*x)+{values[1]};",
        f"long long x=3000000000LL+{index}; return (int)(x%997LL);",
        f"int x={values[0]}; switch(x&3){{case 0:return x+4;case 1:return x-8;default:return x;}}",
        f"int a[4]={{{numbers}}}; return _Generic(a[0],int:a[2],default:0);",
    ]
    return "int main(void){" + bodies[index % len(bodies)] + "}\n"


def main():
    rng = random.Random(6841)
    sources = [program(i, rng) for i in range(2000)]
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        native = directory / "oracle.c"
        definitions = [text.replace("main(void)", f"case_{i}(void)") for i, text in enumerate(sources)]
        prints = [f'printf("%d\\n",case_{i}());' for i in range(len(sources))]
        native.write_text("#include <stdio.h>\n" + "".join(definitions) +
                          "int main(void){" + "".join(prints) + "return 0;}\n")
        compiler = os.environ.get("CLANG", "clang")
        exe = directory / "oracle"
        subprocess.run([compiler,"-std=c17",str(native),"-o",str(exe)],check=True)
        expected = subprocess.check_output([str(exe)],text=True).splitlines()

        def compile_one(index):
            work = directory / str(index)
            work.mkdir()
            source = work / "entry.c"
            source.write_text(sources[index])
            module = work / "entry.wasm"
            build([source],module,work/"cache")
            return str(module)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            modules = list(executor.map(compile_one,range(len(sources))))
        actual = []
        for start in range(0,len(modules),100):
            batch = modules[start:start+100]
            output = subprocess.check_output(["node",str(ROOT/"emberc/run.js"),*batch],text=True)
            actual.extend(output.splitlines())
        if actual != expected:
            raise RuntimeError("WASM results differ from native Clang")
        print(json.dumps({"independent_wasm_modules":len(modules),"matched_native_clang":len(actual),
                          "generated_families":8,"seed":6841,"compiler_path":"Clang-backed EmberC project driver",
                          "oracle":"native Clang","comparison":"full signed return values"},indent=2))

if __name__ == "__main__":
    main()
