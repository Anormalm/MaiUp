import type { NextConfig } from 'next';

const previewHost = process.env.MAIUP_PREVIEW_HOST?.trim();

const nextConfig: NextConfig = {
  allowedDevOrigins: previewHost ? [previewHost] : [],
};

export default nextConfig;
