import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const currentDir = dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  transpilePackages: ["memrise-memory-sdk"],
  turbopack: {
    root: resolve(currentDir, "../.."),
  },
};

export default nextConfig;
