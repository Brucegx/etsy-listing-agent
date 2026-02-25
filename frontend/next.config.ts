import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable standalone output for Docker deployments.
  // This bundles all dependencies into .next/standalone so the runtime image
  // only needs `node server.js` without a full node_modules tree.
  output: "standalone",
};

export default nextConfig;
