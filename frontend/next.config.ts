import type { NextConfig } from "next";

const backendUrl = (
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "production" ? "https://decidr-backend.onrender.com" : "http://127.0.0.1:8000")
).replace(/\/+$/, "").replace(/\/api$/, "");

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
