import type { NextConfig } from "next";

// next/font self-hosts Google Fonts at build time (no runtime request to fonts.googleapis.com),
// so the CSP doesn't need to allow that host. connect-src does need the API origin -- it's
// wherever NEXT_PUBLIC_API_BASE_URL points, not just this frontend's own origin.
const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self'",
  // framer-motion animates via inline style="" attributes; CSP's style-src covers those too
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiBaseUrl}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  // don't ship a public JS source map for the production demo; server-side error
  // monitoring (if ever added) uploads its own maps privately, this doesn't affect that
  productionBrowserSourceMaps: false,

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "geolocation=(), microphone=(), camera=()" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
        ],
      },
    ];
  },
};

export default nextConfig;
