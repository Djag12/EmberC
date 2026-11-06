const fs=require('fs');
(async()=>{for(const f of process.argv.slice(2)){const {instance}=await WebAssembly.instantiate(fs.readFileSync(f)); console.log(instance.exports.main());}})().catch(e=>{console.error(e);process.exit(1)});
