/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
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
