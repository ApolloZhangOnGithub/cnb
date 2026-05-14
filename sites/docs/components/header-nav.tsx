'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { ResourcesDropdown } from './resources-dropdown';

const pillActive = {
  fontSize: '0.875rem',
  fontWeight: 500,
  color: 'var(--color-fd-foreground)',
  textDecoration: 'none' as const,
  padding: '0.375rem 0.875rem',
  borderRadius: '9999px',
  background: 'var(--color-fd-accent)',
};

const pillInactive = {
  fontSize: '0.875rem',
  fontWeight: 500,
  color: 'var(--color-fd-muted-foreground)',
  textDecoration: 'none' as const,
  padding: '0.375rem 0.875rem',
  borderRadius: '9999px',
  background: 'transparent',
};

export function HeaderNav({ lang }: { lang: string }) {
  const pathname = usePathname();
  const isAgents = pathname.includes('/agents');
  const isHome = pathname === `/${lang}` || pathname === `/${lang}/`;
  const isDev = !isAgents && !isHome;

  return (
    <nav style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', justifyContent: 'center', height: '100%' }}>
      <Link href={`/${lang}/guide/getting-started/`} style={isDev ? pillActive : pillInactive}>For Human</Link>
      <Link href={`/${lang}/agents/`} style={isAgents ? pillActive : pillInactive}>For Tongxue</Link>
      <ResourcesDropdown lang={lang} />
    </nav>
  );
}

export function useSection(): string {
  const pathname = usePathname();
  return pathname.includes('/agents') ? 'agents' : 'developer';
}
