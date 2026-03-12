/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone', // necesario para Docker multi-stage build
};
export default nextConfig;
