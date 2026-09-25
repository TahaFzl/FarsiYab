import type { NextConfig } from "next";

const apiUrl = process.env.FARSIYAB_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Browser requests to /api/* go to the FastAPI server. In production Caddy
  // routes /api/* to the API before it reaches Next.js (deploy/Caddyfile),
  // which also keeps the SSE progress stream unbuffered.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
