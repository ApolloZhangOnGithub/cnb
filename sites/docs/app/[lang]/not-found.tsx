import Link from 'next/link';

export default function NotFound() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 'calc(100vh - 3.5rem)',
      textAlign: 'center',
      padding: '2rem',
    }}>
      <div>
        <div style={{ fontSize: '6rem', fontWeight: 700, letterSpacing: '-0.04em', color: 'var(--color-fd-foreground)', lineHeight: 1 }}>
          404
        </div>
        <div style={{ fontSize: '1.25rem', color: 'var(--color-fd-muted-foreground)', marginTop: '1rem', marginBottom: '2rem' }}>
          This page could not be found.
        </div>
        <Link
          href="/"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.625rem 1.25rem',
            borderRadius: '0.5rem',
            background: 'var(--color-fd-foreground)',
            color: 'var(--color-fd-background)',
            fontSize: '0.875rem',
            fontWeight: 600,
            textDecoration: 'none',
          }}
        >
          Back to docs
        </Link>
      </div>
    </div>
  );
}
