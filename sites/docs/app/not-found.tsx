export default function NotFound() {
  return (
    <html lang="en">
      <body style={{
        margin: 0,
        background: '#f9f8f5',
        fontFamily: 'var(--font-geist-sans), system-ui, sans-serif',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        textAlign: 'center',
        padding: '2rem',
      }}>
        <div>
          <div style={{ fontSize: '6rem', fontWeight: 700, letterSpacing: '-0.04em', color: '#141413', lineHeight: 1 }}>
            404
          </div>
          <div style={{ fontSize: '1.25rem', color: '#726f65', marginTop: '1rem', marginBottom: '2rem' }}>
            This page could not be found.
          </div>
          <a
            href="/docs/zh/"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.625rem 1.25rem',
              borderRadius: '0.5rem',
              background: '#141413',
              color: '#ffffff',
              fontSize: '0.875rem',
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            Back to docs
          </a>
        </div>
      </body>
    </html>
  );
}
