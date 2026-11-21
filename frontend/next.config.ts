import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [
      {
        source: "/mock-tracker",
        destination: "http://127.0.0.1:8000/mock-tracker",
      },
      {
        source: "/api/mock-tracker/:path*",
        destination: "http://127.0.0.1:8000/api/mock-tracker/:path*",
      },
    ];
  },
};

export default nextConfig;
