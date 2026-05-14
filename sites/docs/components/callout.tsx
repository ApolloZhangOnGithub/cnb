import type { ReactNode, CSSProperties } from 'react';

const baseStyle: CSSProperties = {
  display: 'flex',
  width: '100%',
  borderRadius: '0.5rem',
  padding: '0.75rem 1rem',
  gap: '0.25rem',
  alignItems: 'flex-start',
  fontSize: '0.875rem',
  lineHeight: '1.625',
  margin: '1.5rem 0',
};

const iconWrap: CSSProperties = {
  display: 'flex',
  marginRight: '0.5rem',
  flexShrink: 0,
  paddingTop: '1.375px',
};

const iconBox: CSSProperties = {
  width: 20,
  height: 20,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
};

const contentStyle: CSSProperties = {
  flexGrow: 1,
  minWidth: 0,
};

// Info (blue) — matches Anthropic's "Note" callout
const infoStyle: CSSProperties = {
  ...baseStyle,
  border: '0.5px solid #2b82d9',
  background: 'rgba(43, 130, 217, 0.1)',
  color: '#1b6abf',
};

// Warning (yellow) — matches Anthropic's "Warning" callout
const warningStyle: CSSProperties = {
  ...baseStyle,
  border: '0.5px solid #d4a72c',
  background: 'rgba(212, 167, 44, 0.1)',
  color: '#8a6d10',
};

// Tip (neutral) — matches Anthropic's "Tip" callout with lightbulb
const tipStyle: CSSProperties = {
  ...baseStyle,
  border: '0.5px solid rgba(30, 30, 29, 0.12)',
  background: '#f3f2ed',
  color: '#141413',
};

const InfoIcon = () => (
  <div style={iconWrap}>
    <div style={iconBox}>
      <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" style={{ flexShrink: 0 }} aria-hidden="true">
        <path d="M10 2.5a7.5 7.5 0 1 1 0 15 7.5 7.5 0 0 1 0-15m0 1a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13m.1 5.51a.5.5 0 0 1 .4.49v3h1a.5.5 0 0 1 0 1h-3a.5.5 0 0 1 0-1h1V10h-1a.5.5 0 0 1 0-1H10zM10 6.5A.75.75 0 1 1 10 8a.75.75 0 0 1 0-1.5"/>
      </svg>
    </div>
  </div>
);

const WarningIcon = () => (
  <div style={iconWrap}>
    <div style={iconBox}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }} aria-hidden="true">
        <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>
      </svg>
    </div>
  </div>
);

const TipIcon = () => (
  <div style={iconWrap}>
    <div style={iconBox}>
      <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" style={{ flexShrink: 0 }} aria-hidden="true">
        <path d="M12.5 17a.5.5 0 0 1 0 1h-5a.5.5 0 0 1 0-1zM10 2a6 6 0 0 1 4.081 10.398l-.242.213c-.512.427-.839.964-.839 1.513V15.5a.5.5 0 0 1-.5.5h-5a.5.5 0 0 1-.5-.5v-1.376c0-.48-.25-.951-.656-1.348l-.183-.165A6 6 0 0 1 10 2m0 1a5 5 0 0 0-3.2 8.843l.237.213c.537.523.963 1.234.963 2.068V15h1.5v-3.793L7.146 8.854l-.064-.079a.5.5 0 0 1 .693-.693l.079.064L10 10.293l2.146-2.147.079-.064a.5.5 0 0 1 .693.693l-.064.079-2.354 2.353V15H12v-.876c0-.953.557-1.746 1.2-2.281l.2-.178A5 5 0 0 0 10 3"/>
      </svg>
    </div>
  </div>
);

export function Info({ children }: { children: ReactNode }) {
  return (
    <div style={infoStyle} className="not-prose">
      <InfoIcon />
      <div style={contentStyle}>{children}</div>
    </div>
  );
}

export function Warning({ children }: { children: ReactNode }) {
  return (
    <div style={warningStyle} className="not-prose">
      <WarningIcon />
      <div style={contentStyle}>{children}</div>
    </div>
  );
}

export function Tip({ children }: { children: ReactNode }) {
  return (
    <div style={tipStyle} className="not-prose">
      <TipIcon />
      <div style={contentStyle}>{children}</div>
    </div>
  );
}
