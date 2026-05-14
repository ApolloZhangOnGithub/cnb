import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();

/** @type {import('next').NextConfig} */
const config = {
  output: 'export',
  basePath: '/docs',
  trailingSlash: true,
  reactStrictMode: true,
  typescript: { ignoreBuildErrors: true }, // TODO: fix PageTree import in custom-sidebar.tsx
};

export default withMDX(config);
