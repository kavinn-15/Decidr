import type { NextConfig } from "next";

const backendUrl = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  async rewrites() {
    return [
      {
        source: "/mock-tracker",
        destination: `${backendUrl}/mock-tracker`,
      },
      {
        source: "/api/mock-tracker/:path*",
        destination: `${backendUrl}/api/mock-tracker/:path*`,
      },
    ];
  },
};

export default nextConfig;
