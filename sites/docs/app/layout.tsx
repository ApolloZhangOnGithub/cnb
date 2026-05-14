import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import './global.css';

export default async function Layout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang?: string }>;
}) {
  const { lang } = await params;
  return (
    <html lang={lang ?? 'zh'} className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <head>
        <link rel="icon" href="/docs/logo.svg" type="image/svg+xml" />
      </head>
      <body className="flex flex-col min-h-screen">
        {children}
      </body>
    </html>
  );
}
