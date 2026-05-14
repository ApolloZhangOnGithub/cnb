'use client';

import { useState, type CSSProperties } from 'react';
import { usePathname } from 'next/navigation';

const container: CSSProperties = {
  borderTop: '0.5px solid rgba(30,30,29,0.12)',
  paddingTop: '1.5rem',
  marginTop: '3rem',
};

const title: CSSProperties = {
  fontSize: '0.875rem',
  fontWeight: 500,
  color: '#3c3b37',
  marginBottom: '0.75rem',
};

const btnGroup: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.5rem',
  marginBottom: '1rem',
};

const btn = (active: boolean): CSSProperties => ({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '2.25rem',
  height: '2.25rem',
  borderRadius: '0.5rem',
  border: '0.5px solid rgba(30,30,29,0.12)',
  background: active ? '#e6e5dc' : 'transparent',
  cursor: 'pointer',
  transition: 'background 0.15s',
  color: '#3c3b37',
});

const textareaStyle: CSSProperties = {
  width: '100%',
  maxWidth: '28rem',
  minHeight: '4rem',
  padding: '0.5rem 0.75rem',
  borderRadius: '0.5rem',
  border: '0.5px solid rgba(30,30,29,0.12)',
  fontSize: '0.875rem',
  fontFamily: 'inherit',
  resize: 'vertical',
  background: '#ffffff',
  color: '#3c3b37',
  outline: 'none',
};

const submitBtn: CSSProperties = {
  marginTop: '0.5rem',
  padding: '0.375rem 1rem',
  borderRadius: '0.375rem',
  border: 'none',
  background: '#141413',
  color: '#ffffff',
  fontSize: '0.8125rem',
  fontWeight: 500,
  cursor: 'pointer',
  fontFamily: 'inherit',
};

const labelStyle: CSSProperties = {
  fontSize: '0.8125rem',
  color: '#726f65',
  marginBottom: '0.375rem',
  display: 'block',
};

const thankYou: CSSProperties = {
  fontSize: '0.875rem',
  color: '#726f65',
};

const ThumbUp = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88"/>
  </svg>
);

const ThumbDown = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88"/>
  </svg>
);

export function PageFeedback({ lang }: { lang?: string }) {
  const pathname = usePathname();
  const isZh = lang === 'zh';
  const [vote, setVote] = useState<'up' | 'down' | null>(null);
  const [comment, setComment] = useState('');
  const [submitted, setSubmitted] = useState(false);

  async function submit(v: 'up' | 'down', msg?: string) {
    try {
      await fetch('https://blog.c-n-b.space/api/docs-feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ page: pathname, vote: v, comment: msg || '' }),
      });
    } catch {}
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <div style={container} className="not-prose">
        <p style={thankYou}>{isZh ? '感谢你的反馈！' : 'Thanks for your feedback!'}</p>
      </div>
    );
  }

  return (
    <div style={container} className="not-prose">
      <p style={title}>{isZh ? '这个页面有帮助吗？' : 'Was this page helpful?'}</p>
      <div style={btnGroup}>
        <button
          type="button"
          style={btn(vote === 'up')}
          onClick={() => { setVote('up'); if (!comment) submit('up'); }}
          aria-label="Thumbs up"
          aria-pressed={vote === 'up'}
        ><ThumbUp /></button>
        <button
          type="button"
          style={btn(vote === 'down')}
          onClick={() => setVote('down')}
          aria-label="Thumbs down"
          aria-pressed={vote === 'down'}
        ><ThumbDown /></button>
      </div>
      {vote === 'down' && (
        <div>
          <label style={labelStyle}>{isZh ? '我们可以如何改进这个页面？（可选）' : 'How can we improve this page? (optional)'}</label>
          <textarea
            style={textareaStyle}
            value={comment}
            onChange={e => setComment(e.target.value)}
            placeholder={isZh ? '告诉我们哪里可以做得更好...' : 'Tell us what could be better...'}
          />
          <div>
            <button type="button" style={submitBtn} onClick={() => submit('down', comment)}>
              {isZh ? '提交' : 'Submit'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
