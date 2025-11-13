/** @type {import('next').NextConfig} */
const PUBLIC_ENV = {
  NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL,
  NEXT_PUBLIC_HEALTHCHECK_URL: process.env.NEXT_PUBLIC_HEALTHCHECK_URL,
};

const nextConfig = {
  output: 'export',
  reactStrictMode: true,
  experimental: {
    reactCompiler: false,
  },
  trailingSlash: true,
  env: PUBLIC_ENV,
};

export default nextConfig;
