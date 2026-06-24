/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    // Where the browser reaches the FastAPI backend. Override via .env.local.
    NEXT_PUBLIC_API_BASE:
      process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000",
  },
};

export default nextConfig;
