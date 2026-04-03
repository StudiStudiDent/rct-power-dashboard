import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      // FastAPI serves the built output
      pages: 'dist',
      assets: 'dist',
      fallback: 'index.html',  // SPA mode: all routes fall back to index.html
      precompress: false,
    }),
    // API calls go to the FastAPI backend (same origin via Cloudflare Tunnel)
    prerender: { entries: [] },
  },
};

export default config;
