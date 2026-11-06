"""Incremental C17/WASM project driver. Clang is explicitly the C17 backend.

The sibling wasm.py is EmberC's independent, smaller custom compiler.
This driver supports linked translation units, header dependency invalidation,
DWARF sections, and deterministic content-addressed object caching.
"""
import argparse, hashlib, json, os, shlex, subprocess, tempfile, time
from pathlib import Path

def build(sources, output, cache, compiler=None, linker=None):
    start = time.perf_counter()
    compiler = compiler or os.environ.get('CLANG', 'clang')
    linker = linker or os.environ.get('WASM_LD', 'wasm-ld')
    sources = [Path(p).resolve() for p in sources]
    output, cache = Path(output).resolve(), Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    version = subprocess.check_output([compiler, '--version'])
    flags = ['--target=wasm32', '-std=c17', '-O0', '-g', '-gdwarf-4', '-ffreestanding']
    objects, compiled, hits = [], 0, 0
    # Hash all project headers conservatively: avoids stale objects after edits.
    headers = sorted({h for p in sources for h in p.parent.rglob('*.h')})
    header_bytes = b''.join(str(h).encode()+h.read_bytes() for h in headers)
    for source in sources:
        key = hashlib.sha256(version+str(source).encode()+source.read_bytes()+header_bytes+repr(flags).encode()).hexdigest()
        # The C preprocessor can include files outside the source tree or with
        # arbitrary extensions. Retain the actual transitive dependency graph.
        record_file = cache / (key + '.deps.json')
        record = json.loads(record_file.read_text()) if record_file.exists() else {}
        obj = cache / record.get('object', 'missing')
        dependencies = record.get('files', {})
        valid = obj.is_file() and dependencies and all(
            Path(path).is_file() and hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
            for path, digest in dependencies.items()
        )
        if valid:
            hits += 1
        else:
            with tempfile.TemporaryDirectory(dir=cache) as stage:
                stage = Path(stage)
                temp = stage / 'unit.o'
                depfile = stage / 'unit.d'
                subprocess.run([compiler, *flags, '-MD', '-MF', str(depfile),
                                '-MT', 'unit', '-c', str(source), '-o', str(temp)], check=True)
                rule = depfile.read_text().replace(chr(92) + chr(10), ' ')
                paths = shlex.split(rule.partition(':')[2])
                files = {str(Path(path).resolve()): hashlib.sha256(Path(path).read_bytes()).hexdigest()
                         for path in paths}
                obj = cache / (hashlib.sha256(temp.read_bytes()).hexdigest() + '.o')
                temp.replace(obj)
                manifest_temp = stage / 'dependencies.json'
                manifest_temp.write_text(json.dumps({'object': obj.name, 'files': files}))
                manifest_temp.replace(record_file)
            compiled += 1
        objects.append(obj)
    # Relink only if the ordered object identities or linker change.
    link_key = hashlib.sha256(repr(objects).encode()+subprocess.check_output([linker,'--version'])).hexdigest()
    manifest = output.with_suffix('.build.json')
    relink = not output.exists() or not manifest.exists() or json.loads(manifest.read_text()).get('key') != link_key
    if relink:
        subprocess.run([linker, '--no-entry', '--export=main', *map(str,objects), '-o', str(output)], check=True)
        manifest.write_text(json.dumps({'key':link_key,'backend':'Clang C17 + wasm-ld','objects':len(objects)}))
    return {'compiled':compiled,'cached':hits,'linked':relink,'milliseconds':(time.perf_counter()-start)*1000,'backend':'Clang C17 + wasm-ld'}

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('sources',nargs='+');p.add_argument('-o',required=True);p.add_argument('--cache',default='.ember-cache')
    a=p.parse_args();print(json.dumps(build(a.sources,a.o,a.cache),indent=2))
