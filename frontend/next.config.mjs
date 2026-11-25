/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      ...["chairtimehq.com", "www.chairtimehq.com"].map(host => ({
        source: "/:path*",
        has: [{ type: "host", value: host.replaceAll(".", "\\.") }],
        destination: "https://www.daytello.com/:path*",
        permanent: true,
      })),
      {
        source: '/admin/agenda',
        destination: '/admin/today',
        permanent: true,
      },
      {
        source: '/agenda',
        destination: '/admin/today',
        permanent: true,
      },
      {
        source: '/today',
        destination: '/admin/today',
        permanent: true,
      },
      {
        source: '/book',
        destination: '/',
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
