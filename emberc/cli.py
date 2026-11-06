"""Explicit backend selection: own integer compiler or Clang-backed C17 builds."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('sources',nargs='+',type=Path)
p.add_argument('-o','--output',type=Path,required=True)
p.add_argument('--backend',choices=['custom','clang-c17'],default='custom')
p.add_argument('--cache',type=Path,default=Path('.ember-cache'))
a=p.parse_args()
if a.backend=='custom':from custom_project import build
else:from project import build
print(json.dumps(build(a.sources,a.output,a.cache/a.backend),indent=2))
