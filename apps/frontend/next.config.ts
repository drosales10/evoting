import type { NextConfig } from "next";
import fs from "node:fs";
import path from "node:path";

function applyEnvFile(filePath: string) {
  if (!fs.existsSync(filePath)) return;
  const text = fs.readFileSync(filePath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (!process.env[key]) {
      process.env[key] = value;
    }
  }
}

const searchDirs = [
  process.cwd(),
  path.resolve(process.cwd(), "../.."),
  path.resolve(__dirname),
  path.resolve(__dirname, "../.."),
];

for (const dir of searchDirs) {
  applyEnvFile(path.join(dir, ".env.local"));
  applyEnvFile(path.join(dir, ".env"));
}

// Mirror backend APP_TIMEZONE into the public frontend var when unset.
if (!process.env.NEXT_PUBLIC_APP_TIMEZONE && process.env.APP_TIMEZONE) {
  process.env.NEXT_PUBLIC_APP_TIMEZONE = process.env.APP_TIMEZONE;
}
if (!process.env.NEXT_PUBLIC_APP_LOCALE && process.env.APP_LOCALE) {
  process.env.NEXT_PUBLIC_APP_LOCALE = process.env.APP_LOCALE;
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@evoting/shared"],
  async rewrites() {
    const backend = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(
      /\/$/,
      "",
    );
    // Same-origin /api and /health in local/dev avoid stale NEXT_PUBLIC hosts and CORS mismatches.
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/health", destination: `${backend}/health` },
      { source: "/health/:path*", destination: `${backend}/health/:path*` },
    ];
  },
};

export default nextConfig;
