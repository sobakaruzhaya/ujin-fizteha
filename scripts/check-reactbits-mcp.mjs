import { spawn } from 'node:child_process';
const child = spawn('npx', ['-y', 'shadcn@latest', 'mcp'], { cwd: process.cwd(), stdio: ['pipe', 'pipe', 'inherit'] });
const send = m => child.stdin.write(JSON.stringify({jsonrpc:'2.0',...m})+'\n');
let buffer='';
const timeout=setTimeout(()=>{console.error('MCP timeout');child.kill();process.exit(1)},120000);
child.stdout.on('data', chunk=>{buffer+=chunk;let i;while((i=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,i);buffer=buffer.slice(i+1);let r;try{r=JSON.parse(line)}catch{continue}
 if(r.error){console.error(r.error);clearTimeout(timeout);child.kill();process.exit(1)}
 if(r.id===1){send({method:'notifications/initialized'});send({id:2,method:'tools/list',params:{}})}
 if(r.id===2){console.log('MCP handshake OK. Tools:',r.result.tools.map(t=>t.name).join(', '));const tool=r.result.tools.find(t=>t.name==='search_items_in_registries');if(!tool)throw Error('Registry search tool unavailable');send({id:3,method:'tools/call',params:{name:tool.name,arguments:{registries:['@react-bits'],query:'CountUp',limit:2}}});}
 if(r.id===3){console.log(JSON.stringify(r.result));clearTimeout(timeout);child.kill();process.exit(r.result.isError?1:0)}
}});
send({id:1,method:'initialize',params:{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'power-guardian-verification',version:'1.0.0'}}});
