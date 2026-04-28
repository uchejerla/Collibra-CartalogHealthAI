/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow the backend Railway URL or localhost in dev
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    return [
      {
        source:      "/api/:path*",
        destination: `${apiBase}/:path*`,
      },
    ]
  },
  // Strict mode for catching React issues early
  reactStrictMode: true,
}

module.exports = nextConfig
