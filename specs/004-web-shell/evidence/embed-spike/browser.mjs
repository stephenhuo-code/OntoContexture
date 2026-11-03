import {chromium, expect} from '@playwright/test';
import {mkdir, readdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
const origin='http://127.0.0.1:4174';
const output=process.env.SPIKE_EVIDENCE_DIR;
const hostDir=process.env.SPIKE_HOST_DIR;
if(!output || !hostDir) throw new Error('Set SPIKE_EVIDENCE_DIR and SPIKE_HOST_DIR to temporary directories');
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const evidence={browser:browser.version(),requests:[],errors:[],blockedExternal:[],checks:[]};
page.setDefaultTimeout(10000);
page.on('pageerror',e=>evidence.errors.push(e.message));
await page.route('**/*',async route=>{
 const url=new URL(route.request().url());
 if(url.origin!==origin){evidence.blockedExternal.push(url.origin);return route.abort();}
 if(!url.pathname.startsWith('/bff/spike/')) return route.continue();
 const apiPath=url.pathname.slice('/bff/spike'.length);
 evidence.requests.push({path:apiPath,method:route.request().method()});
 let data={};
 if(apiPath==='/v1/info') data={accounts_enabled:false,single_user:true,features:{},server_version:'isolated-fixture',branding:null};
 else if(apiPath==='/v1/me') data={user_id:'isolated-spike-user',is_admin:false};
 else if(apiPath==='/v1/sessions') data={data:[],has_more:false};
 else if(apiPath==='/v1/sessions/projects' || apiPath==='/v1/projects/order') data=[];
 else if(apiPath==='/v1/hosts') data={hosts:[]};
 else if(apiPath==='/v1/extensions') data={object:'list',data:[]};
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
});
page.on('websocket',ws=>{evidence.websocketEvents??=[];evidence.websocketEvents.push({url:ws.url()});ws.on('socketerror',e=>evidence.websocketEvents.push({error:String(e)}));ws.on('close',()=>evidence.websocketEvents.push({closed:true}));});
const check=async(name,fn)=>{await fn();evidence.checks.push({name,result:'runtime_pass'});};
try{
 await page.goto(origin+'/workbench/not-a-page');
 await check('initial mount and deep link',async()=>{
  await expect(page.getByText('Page not found',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>window.spikeVersions.react)).toBe('18.3.1');
  await expect(page.locator('.omnigent-app')).toHaveCount(1);
 });
 await check('CSS host isolation',async()=>{
  expect(await page.locator('#host-chrome').evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgb(233, 237, 241)');
  expect(await page.locator('#host-chrome h1').evaluate(el=>getComputedStyle(el).fontSize)).toBe('19px');
 });
 await check('reload retains route',async()=>{await page.reload();await expect(page.getByText('Page not found',{exact:true})).toBeVisible();});
 await check('shared Router navigation and lazy settings chunk',async()=>{
  await page.locator('#host-chrome').getByRole('link',{name:'Settings',exact:true}).click();
  await expect(page.locator('#host-chrome output')).toHaveText('/workbench/settings/general');
  await expect(page.locator('.omnigent-app')).toContainText('Configure general Omnigent behavior.');
 });
 await check('back and forward',async()=>{
  await page.goBack();await expect(page.getByText('Page not found',{exact:true})).toBeVisible();
  await page.goForward();await expect(page.locator('#host-chrome output')).toHaveText('/workbench/settings/general');
 });
 await page.getByRole('link',{name:'Unknown',exact:true}).click();
 await check('Radix portal remains inside scope',async()=>{
  await page.getByRole('button',{name:'Filter sessions',exact:true}).click();
  await expect(page.getByRole('menu')).toBeVisible();
  expect(await page.getByRole('menu').evaluate(el=>!!el.closest('.omnigent-app'))).toBe(true);
  await page.keyboard.press('Escape');
 });
 await check('unmount and remount',async()=>{
  await page.getByRole('button',{name:'Unmount',exact:true}).click();
  await expect(page.locator('.omnigent-app')).toHaveCount(0);
  await page.getByRole('button',{name:'Mount',exact:true}).click();
  await expect(page.getByText('Page not found',{exact:true})).toBeVisible();
 });
 const workers=(await readdir(path.join(hostDir,'dist/assets'))).filter(n=>/^(editor|pdf)\.worker.*\.js$/.test(n));
 expect(workers.length).toBe(2);
 await check('both emitted module workers load',async()=>{
  evidence.workers=[];
  for(const worker of workers){
   const response=await page.request.get(origin+'/assets/'+worker);
   expect(response.status()).toBe(200);
   const result=await page.evaluate(async url=>{
    return await new Promise(resolve=>{
     const w=new Worker(url,{type:'module'});
     const timer=setTimeout(()=>{w.terminate();resolve({loaded:true,error:null});},500);
     w.onerror=e=>{clearTimeout(timer);w.terminate();resolve({loaded:false,error:e.message});};
    });
   },origin+'/assets/'+worker);
   expect(result.error).toBeNull();evidence.workers.push({name:worker,...result});
  }
 });
 await check('all static assets without external network',async()=>{
  for(const file of (await readdir(path.join(hostDir,'dist/assets'))).filter(n=>!n.endsWith('.map'))){
   const response=await page.request.get(origin+'/assets/'+file);
   if(response.status()!==200) throw new Error(`asset ${file} status ${response.status()}`);
  }
 });
 await check('transport hooks cancellation and WebSocket lifecycle',async()=>{
  evidence.transport=await page.evaluate(()=>window.runBoundaryProbe());
  expect(evidence.transport.first).toContain('first chunk');
  expect(evidence.transport.abortName).toBe('AbortError');
  expect(evidence.transport.status).toBe(401);
  expect(evidence.transport.socketUrl).toBe(origin.replace('http:', 'ws:')+'/bff/probe/v1/probe/socket');
  expect(evidence.transport.socket).toEqual({message:'fixture ready',code:1000,clean:true});
  await expect.poll(async()=>{
   evidence.transportServer=await (await page.request.get('http://127.0.0.1:4175/probe-stats')).json();
   return evidence.transportServer.streamClosed;
  }).toBeGreaterThan(0);
  expect(evidence.transportServer.upgradePaths).toContain('/v1/probe/socket');
  expect(evidence.transportServer.upgradePaths).toContain('/v1/sessions/updates');
 });
 await check('no uncaught runtime error',async()=>expect(evidence.errors).toEqual([]));
 await page.screenshot({path:path.join(output,'mounted.png')});
 evidence.result='runtime_pass';
}catch(error){
 evidence.result='runtime_fail';evidence.failure=String(error);
 try {evidence.transportServer=await (await page.request.get('http://127.0.0.1:4175/probe-stats')).json();}catch{}
 evidence.body=(await page.locator('body').innerText()).slice(0,6000);
 await page.screenshot({path:path.join(output,'failure.png')});
 process.exitCode=1;
}finally{
 await writeFile(path.join(output,'runtime.json'),JSON.stringify(evidence,null,2)+'\n');
 console.log(JSON.stringify(evidence,null,2));
 await browser.close();
}
