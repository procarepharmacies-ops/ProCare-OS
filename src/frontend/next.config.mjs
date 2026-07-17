/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    // Where the browser reaches the FastAPI backend. Override via .env.local.
    // `??` keeps an explicit empty string ("" = same-origin, used in Docker
    // where /api is proxied to the backend below).
    NEXT_PUBLIC_API_BASE:
      process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8100",
  },
  // In the container deployment the browser calls the frontend's own origin and
  // Next.js proxies /api/* to the backend service (server-side, no CORS). Enabled
  // only when BACKEND_INTERNAL is set (e.g. http://backend:8000 in compose); in
  // local dev it's unset, so the app uses the absolute API base above unchanged.
  async rewrites() {
    const backend = process.env.BACKEND_INTERNAL;
    if (!backend) return [];
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
