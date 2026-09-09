import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'MaiUp · maimai DX International 上分推荐',
  description: '从可校对的 B50 数据出发，生成有依据的个性化上分建议。',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
