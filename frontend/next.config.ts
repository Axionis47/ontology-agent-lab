import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  poweredByHeader: false,
  turbopack: {
    rules: {
      "globals.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
