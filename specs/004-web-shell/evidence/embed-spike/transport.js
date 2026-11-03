// Probe the locked source module in an isolated build, without a product proxy.
import {hostFetch, resolveWebSocketUrl, setOmnigentHostConfig} from '../upstream/web/src/lib/host.ts';
window.runBoundaryProbe = async () => {
 setOmnigentHostConfig({
  fetcher: (p, init) => fetch('/bff/probe' + p, init),
  resolveWebSocketUrl: p => `ws://${location.host}/bff/probe${p}`,
 });
 const abort = new AbortController();
 const stream = await hostFetch('/v1/probe/stream', {signal: abort.signal});
 const reader = stream.body.getReader();
 const first = new TextDecoder().decode((await reader.read()).value);
 abort.abort();
 let abortName;
 try {await reader.read();} catch(error) {abortName=error.name;}
 const denied = await hostFetch('/v1/probe/unauthorized');
 const socketUrl = resolveWebSocketUrl('/v1/probe/socket');
 const socket = await new Promise((resolve,reject) => {
  const ws = new WebSocket(socketUrl);
  let message;
  const timer=setTimeout(()=>{ws.close();reject(Error('WS timeout'));},3000);
  ws.onerror=()=>{clearTimeout(timer);reject(Error('WS error'));};
  ws.onmessage=e=>{message=e.data;ws.close(1000,'probe complete');};
  ws.onclose=e=>{clearTimeout(timer);resolve({message,code:e.code,clean:e.wasClean});};
 });
 return {first,abortName,status:denied.status,socketUrl,socket};
};
