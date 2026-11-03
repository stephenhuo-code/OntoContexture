import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
 plugins: [react()],
 resolve: {dedupe: ['react','react-dom','react-router','react-router-dom']},
 server: {proxy: {'/bff/spike': {target: 'http://127.0.0.1:4175', ws: true, rewrite: p => p.replace(/^\/bff\/spike/, '')}, '/bff/probe': {target: 'http://127.0.0.1:4175', ws: true, rewrite: p => p.replace(/^\/bff\/probe/, '')}}},
 build: { sourcemap: true },
});
