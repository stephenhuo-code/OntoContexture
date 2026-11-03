import './transport.js';
import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter, Link, useLocation} from 'react-router-dom';
import {OmnigentApp, setOmnigentHostConfig} from './embed/omnigent-embed.js';
import './embed/omnigent-embed.css';
import './style.css';
const fetcher = (path, init) => {
 window.spikeRequests.push({path, method: init?.method ?? 'GET'});
 return fetch('/bff/spike' + path, init);
};
const hostConfig = {
 fetcher,
 resolveWebSocketUrl: path => `ws://${location.host}/bff/spike${path}`,
 serverIdentity: 'isolated-spike-only',
};
window.spikeRequests = [];
window.spikeVersions = {react: React.version};
setOmnigentHostConfig(hostConfig);
function Host(){
 const [mounted, setMounted] = useState(true);
 const loc = useLocation();
 return <><header id="host-chrome"><h1>Host compatibility probe</h1><nav>
 <Link to="/workbench/">Workbench</Link> | <Link to="/workbench/settings/general">Settings</Link> | <Link to="/workbench/not-a-page">Unknown</Link>
 </nav><button onClick={()=>setMounted(!mounted)}>{mounted ? 'Unmount' : 'Mount'}</button><output>{loc.pathname}</output></header>
 <main style={{height: 'calc(100vh - 100px)'}}>{mounted && <OmnigentApp {...hostConfig} basename="/workbench"/>}</main></>;
}
createRoot(document.getElementById('root')).render(<BrowserRouter><Host/></BrowserRouter>);
