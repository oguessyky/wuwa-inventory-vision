import type { NextConfig } from 'next';

// The help site (D210): plain files for GitHub Pages, under the repository's own path
// (NEXT_BASE_PATH=/wuwa-inventory-vision when the workflow builds it; nothing locally).
const base = process.env.NEXT_BASE_PATH || '';

const config: NextConfig = {
  output: 'export',
  basePath: base,
  trailingSlash: true,
  images: { unoptimized: true },
  env: { NEXT_PUBLIC_BASE_PATH: base },
  reactStrictMode: true,
};

export default config;
