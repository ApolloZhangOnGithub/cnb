'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { REPO_URL } from '@/lib/urls';

const triggerStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '0.25rem',
  fontSize: '0.875rem',
  fontWeight: 500,
  color: 'var(--color-fd-muted-foreground)',
  background: 'transparent',
  border: 'none',
  padding: '0.375rem 0.75rem',
  borderRadius: '9999px',
  cursor: 'pointer',
  fontFamily: 'inherit',
  transition: 'background 0.15s, color 0.15s',
} as const;

const menuStyle = {
  position: 'absolute' as const,
  top: 'calc(100% + 0.25rem)',
  right: 0,
  minWidth: '12rem',
  background: 'var(--color-fd-popover)',
  border: '0.5px solid var(--color-fd-border)',
  borderRadius: '0.5rem',
  boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
  padding: '0.25rem',
  zIndex: 100,
};

const itemStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.5rem',
  padding: '0.5rem 0.75rem',
  fontSize: '0.8125rem',
  color: 'var(--color-fd-foreground)',
  textDecoration: 'none',
  borderRadius: '0.375rem',
  transition: 'background 0.1s',
} as const;

export function ResourcesDropdown({ lang }: { lang: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button type="button" style={triggerStyle} onClick={() => setOpen(!open)}>
        Resources
        <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" style={{ flexShrink: 0 }}>
          <path d="M16.134 6.16a.5.5 0 1 1 .732.68l-6.5 7-.077.068a.5.5 0 0 1-.655-.068l-6.5-7-.062-.08a.5.5 0 0 1 .718-.667l.076.067L10 12.767z"/>
        </svg>
      </button>
      {open && (
        <div style={menuStyle}>
          <a href="https://c-n-b.space/download" style={itemStyle} onClick={() => setOpen(false)}>
            Download Apps
          </a>
          <Link href={`/${lang}/resources/`} style={itemStyle} onClick={() => setOpen(false)}>
            Templates & Docs
          </Link>
          <div style={{ height: '0.5px', background: 'var(--color-fd-border)', margin: '0.25rem 0.5rem' }} />
          <a href={REPO_URL} target="_blank" rel="noreferrer" style={itemStyle} onClick={() => setOpen(false)}>
            GitHub
          </a>
          <a href="https://www.npmjs.com/package/claude-nb" target="_blank" rel="noreferrer" style={itemStyle} onClick={() => setOpen(false)}>
            npm
          </a>
        </div>
      )}
    </div>
  );
}
