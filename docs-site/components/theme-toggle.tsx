'use client';

import { useEffect, useState, useRef } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';

const SunIcon = () => (
  <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor"><path d="M10 15a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2a.5.5 0 0 1 .5-.5m-4.242-1.465a.5.5 0 0 1 .707.707L5.05 15.657a.5.5 0 0 1-.707-.707zm7.777 0a.5.5 0 0 1 .707 0l1.415 1.414a.501.501 0 0 1-.707.708l-1.415-1.415a.5.5 0 0 1 0-.707M10 6a4 4 0 1 1 0 8 4 4 0 0 1 0-8m0 1a3 3 0 1 0 0 6 3 3 0 0 0 0-6M4.5 9.5a.5.5 0 0 1 0 1h-2a.5.5 0 0 1 0-1zm13 0a.5.5 0 0 1 0 1h-2a.5.5 0 0 1 0-1zM4.343 4.343a.5.5 0 0 1 .707 0l1.415 1.414a.501.501 0 0 1-.707.708L4.343 5.05a.5.5 0 0 1 0-.707m10.607 0a.5.5 0 0 1 .707.707l-1.415 1.415a.5.5 0 0 1-.707-.707zM10 2a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 10 2"/></svg>
);

const MoonIcon = () => (
  <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2.5q.645.002 1.256.106l.079.02a.5.5 0 0 1 .12.887l-.071.04a5.567 5.567 0 0 0 2.35 10.614l.399-.015a5.6 5.6 0 0 0 1.15-.207l.08-.015a.5.5 0 0 1 .492.746l-.046.066A7.5 7.5 0 1 1 10 2.5m-.42 1.015a6.5 6.5 0 1 0 4.363 11.648l-.21.004A6.567 6.567 0 0 1 9.58 3.515M13.5 7a.5.5 0 0 1 .5.5V8a1 1 0 0 0 1 1h.5a.5.5 0 0 1 0 1H15a1 1 0 0 0-1 1v.5a.5.5 0 0 1-1 0V11a1 1 0 0 0-1-1h-.5a.5.5 0 0 1 0-1h.5a1 1 0 0 0 1-1v-.5a.5.5 0 0 1 .5-.5m2-3a1 1 0 1 1 0 2 1 1 0 0 1 0-2"/></svg>
);

const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
);

const ChevronDown = () => (
  <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" style={{ flexShrink: 0 }}><path d="M16.134 6.16a.5.5 0 1 1 .732.68l-6.5 7-.077.068a.5.5 0 0 1-.655-.068l-6.5-7-.062-.08a.5.5 0 0 1 .718-.667l.076.067L10 12.767z"/></svg>
);

export function ThemeToggle() {
  const [mode, setMode] = useState<'light' | 'dark'>('light');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setMode(document.documentElement.classList.contains('dark') ? 'dark' : 'light');
  }, []);

  if (!mounted) {
    return <button type="button" className="header-icon-btn" disabled><div style={{ width: 16, height: 16 }} /></button>;
  }

  return (
    <button
      type="button"
      className="header-icon-btn"
      onClick={() => {
        const next = mode === 'light' ? 'dark' : 'light';
        document.documentElement.classList.toggle('dark', next === 'dark');
        setMode(next);
      }}
      aria-label={mode === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
    >
      {mode === 'light' ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

const locales = [
  { code: 'en', label: 'English' },
  { code: 'zh', label: '中文' },
];

export function LanguageSwitch({ lang }: { lang: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  const current = locales.find(l => l.code === lang) || locales[0];

  return (
    <div ref={ref} className="lang-dropdown">
      <button type="button" className="header-ghost-btn" onClick={() => setOpen(!open)}>
        {current.label}
        <ChevronDown />
      </button>
      {open && (
        <div className="lang-dropdown-menu">
          {locales.map(l => {
            const href = pathname.replace(`/${lang}`, `/${l.code}`);
            const isActive = l.code === lang;
            return (
              <Link
                key={l.code}
                href={href}
                className={`lang-dropdown-item ${isActive ? 'lang-dropdown-item-active' : ''}`}
                onClick={() => setOpen(false)}
              >
                <span>{l.label}</span>
                {isActive && <CheckIcon />}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
