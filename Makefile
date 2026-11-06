.PHONY: all demo test benchmark hardware os os-benchmark
demo:
	python3 emberc/cli.py --backend custom emberc/examples/functions.c -o functions.wasm
	node emberc/run.js functions.wasm
test:
	set -e; for suite in compiler custom_project language project c17_backend c17_programs debugger; do python3 tests/$$suite.py; done
