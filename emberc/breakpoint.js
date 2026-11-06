// Execute a WASM main and verify a breakpoint at a DWARF-resolved instruction.
const inspector = require('node:inspector');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const session = new inspector.Session();
session.connect();
let armed = false, hit = false, expected, failure;
session.on('Debugger.paused', ({params}) => {
  try {
    assert.equal(params.callFrames[0].location.columnNumber, expected);
    hit = true;
  } catch (error) { failure = error; }
  session.post('Debugger.resume');
});
session.on('Debugger.scriptParsed', ({params}) => {
  if (params.scriptLanguage !== 'WebAssembly') return;
  expected = params.codeOffset + Number(process.argv[3]);
  session.post('Debugger.setBreakpoint', {
    location: {scriptId: params.scriptId, lineNumber: 0, columnNumber: expected}
  }, (error, response) => {
    if (error) { failure = error; return; }
    try { assert.equal(response.actualLocation.columnNumber, expected); armed = true; }
    catch (error) { failure = error; }
  });
});
session.post('Debugger.enable');
const mod = new WebAssembly.Module(fs.readFileSync(process.argv[2]));
const instance = new WebAssembly.Instance(mod);
const result = instance.exports.main();
session.disconnect();
if (failure) throw failure;
assert.ok(armed && hit, 'Source breakpoint was not reached');
console.log(JSON.stringify({breakpoint_hit: hit, wasm_byte_offset: expected, result}));
