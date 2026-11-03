// Local fixture only: never receives a product identity, cookie, or token.
import http from 'node:http';
import {createHash} from 'node:crypto';
const stats={streamStarted:0,streamClosed:0,upgradePaths:[],wsClosed:0,upgradeAttempts:[]};
const server=http.createServer((req,res)=>{
 if(req.url==='/probe-stats'){
  res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(stats));return;
 }
 if(req.url==='/v1/probe/stream'){
  stats.streamStarted++;
  res.writeHead(200,{'Content-Type':'application/x-ndjson','Cache-Control':'no-store'});
  res.write('{"probe":"first chunk"}\n');
  res.on('close',()=>stats.streamClosed++);return;
 }
 res.writeHead(401,{'Content-Type':'application/json'});res.end('{"error":"fixture_session_expired"}');
});
server.on('upgrade',(req,socket)=>{
 stats.upgradeAttempts.push({path:req.url,origin:req.headers.origin});
 if(!['/v1/probe/socket','/v1/sessions/updates'].includes(req.url) || req.headers.origin!=='http://127.0.0.1:4174'){
  socket.end('HTTP/1.1 403 Forbidden\r\n\r\n');return;
 }
 const accept=createHash('sha1').update(req.headers['sec-websocket-key']+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
 stats.upgradePaths.push(req.url);
 socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
 if(req.url==='/v1/probe/socket'){const ready=Buffer.from('fixture ready');socket.write(Buffer.concat([Buffer.from([0x81,ready.length]),ready]));}
 socket.on('data',data=>{if((data[0]&0x0f)===8)socket.end(Buffer.from([0x88,0x02,0x03,0xe8]));});
 socket.on('close',()=>stats.wsClosed++);
 socket.on('error',()=>{});
});
server.listen(4175,'127.0.0.1',()=>console.log('isolated transport fixture http://127.0.0.1:4175'));
