'use client';

import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

export function DocsWrapper({ children, lang }: { children: ReactNode; lang: string }) {
  const pathname = usePathname();
  const isHome = pathname === `/${lang}` || pathname === `/${lang}/`;
  const isFullPage = isHome || pathname.includes('/login');

  return (
    <div className="docs-with-sidebar" style={isFullPage ? { marginLeft: 0 } : undefined}>
      {children}
    </div>
  );
}

export function FooterWrapper({ children, lang }: { children: ReactNode; lang: string }) {
  const pathname = usePathname();
  const isHome = pathname === `/${lang}` || pathname === `/${lang}/`;
  const isFullPage = isHome || pathname.includes('/login');

  return (
    <div className="docs-footer-wrapper" style={isFullPage ? { paddingLeft: '2rem' } : undefined}>
      {children}
    </div>
  );
}
