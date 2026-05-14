'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function AuthButton({ lang }: { lang: string }) {
  const [loggedIn, setLoggedIn] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setLoggedIn(!!getCookie('token'));
  }, []);

  if (!mounted) {
    return <div style={{ width: '3.5rem', height: '2rem' }} />;
  }

  if (loggedIn) {
    return (
      <a
        href="https://blog.c-n-b.space/logout"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '2rem',
          padding: '0 0.75rem',
          borderRadius: '0.375rem',
          fontSize: '0.75rem',
          fontWeight: 500,
          border: '0.5px solid var(--color-fd-border)',
          color: 'var(--color-fd-muted-foreground)',
          textDecoration: 'none',
        }}
      >
        Log out
      </a>
    );
  }

  return (
    <Link
      href={`/${lang}/login/`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '2rem',
        padding: '0 0.75rem',
        borderRadius: '0.375rem',
        fontSize: '0.75rem',
        fontWeight: 600,
        background: 'var(--color-fd-foreground)',
        color: 'var(--color-fd-background)',
        textDecoration: 'none',
        whiteSpace: 'nowrap',
      }}
    >
      Log in
    </Link>
  );
}
