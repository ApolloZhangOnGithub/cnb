import { i18n, i18nUI } from '@/lib/i18n';
import { Provider } from '@/components/provider';
import { source } from '@/lib/source';
import { DocsLayout } from 'fumadocs-ui/layouts/docs';
import { baseOptions } from '@/lib/layout.shared';
import { REPO_URL } from '@/lib/urls';
import { CustomSidebar } from '@/components/custom-sidebar';
import { ThemeToggle, LanguageSwitch } from '@/components/theme-toggle';
import { HeaderNav } from '@/components/header-nav';
import { DocsWrapper, FooterWrapper } from '@/components/docs-wrapper';
import { AuthButton } from '@/components/auth-button';

function CnbLogo() {
  return (
    <svg width="228" height="28" viewBox="11 4 373 44" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Cnb Developer Docs" style={{ verticalAlign: 'middle' }}>
      <line x1="16" y1="8" x2="38" y2="8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      <line x1="38" y1="8" x2="27" y2="42" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      <line x1="27" y1="42" x2="16" y2="8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      <circle cx="16" cy="8" r="5" fill="#D97757"/><circle cx="38" cy="8" r="5" fill="#D97757"/><circle cx="27" cy="42" r="5" fill="#D97757"/>
      <circle cx="27" cy="19" r="3" fill="currentColor"/>
      <path transform="translate(72.0, 36) scale(0.032, -0.032)" d="M364 -16Q269 -16 197.0 28.5Q125 73 85.0 156.0Q45 239 45 354Q45 469 85.0 552.5Q125 636 197.0 681.0Q269 726 364 726Q493 726 564.0 661.0Q635 596 657 484L566 478Q551 554 502.0 598.0Q453 642 364 642Q296 642 244.5 607.5Q193 573 164.0 508.5Q135 444 135 354Q135 264 164.0 200.0Q193 136 244.5 102.0Q296 68 364 68Q457 68 508.0 116.5Q559 165 572 248L663 242Q650 165 612.0 107.0Q574 49 511.5 16.5Q449 -16 364 -16Z" fill="currentColor"/>
      <path transform="translate(94.5, 36) scale(0.032, -0.032)" d="M80 0V530H157L159 435Q180 490 223.5 516.0Q267 542 322 542Q383 542 422.5 515.0Q462 488 481.5 442.5Q501 397 501 341V0H417V317Q417 391 390.5 429.5Q364 468 304 468Q243 468 203.5 429.5Q164 391 164 317V0Z" fill="currentColor"/>
      <path transform="translate(113.1, 36) scale(0.032, -0.032)" d="M323 -12Q268 -12 225.0 12.5Q182 37 159 80L156 0H80V710H164V456Q184 489 226.0 515.5Q268 542 323 542Q393 542 444.0 508.0Q495 474 523.0 412.0Q551 350 551 265Q551 180 523.0 118.0Q495 56 444.0 22.0Q393 -12 323 -12ZM318 68Q385 68 424.0 121.0Q463 174 463 265Q463 357 424.0 409.5Q385 462 320 462Q247 462 205.5 409.5Q164 357 164 265Q164 174 205.0 121.0Q246 68 318 68Z" fill="currentColor"/>
      <path transform="translate(140.1, 36) scale(0.032, -0.032)" d="M92 0V710H312Q476 710 564.5 617.5Q653 525 653 354Q653 184 566.0 92.0Q479 0 318 0ZM178 84H312Q563 84 563 354Q563 626 312 626H178Z" fill="currentColor"/>
      <path transform="translate(162.3, 36) scale(0.032, -0.032)" d="M287 -12Q212 -12 157.5 22.0Q103 56 73.5 118.5Q44 181 44 265Q44 349 73.5 411.0Q103 473 156.5 507.5Q210 542 283 542Q352 542 405.0 509.5Q458 477 487.5 415.0Q517 353 517 264V239H132Q137 154 177.5 111.0Q218 68 287 68Q339 68 372.5 92.5Q406 117 419 157L509 150Q488 79 429.5 33.5Q371 -12 287 -12ZM132 313H425Q419 390 380.5 426.0Q342 462 283 462Q222 462 182.5 424.5Q143 387 132 313Z" fill="currentColor"/>
      <path transform="translate(180.3, 36) scale(0.032, -0.032)" d="M215 0 22 530H114L268 86L422 530H514L321 0Z" fill="currentColor"/>
      <path transform="translate(197.4, 36) scale(0.032, -0.032)" d="M287 -12Q212 -12 157.5 22.0Q103 56 73.5 118.5Q44 181 44 265Q44 349 73.5 411.0Q103 473 156.5 507.5Q210 542 283 542Q352 542 405.0 509.5Q458 477 487.5 415.0Q517 353 517 264V239H132Q137 154 177.5 111.0Q218 68 287 68Q339 68 372.5 92.5Q406 117 419 157L509 150Q488 79 429.5 33.5Q371 -12 287 -12ZM132 313H425Q419 390 380.5 426.0Q342 462 283 462Q222 462 182.5 424.5Q143 387 132 313Z" fill="currentColor"/>
      <path transform="translate(215.4, 36) scale(0.032, -0.032)" d="M184 0Q138 0 109.0 24.0Q80 48 80 100V710H164V107Q164 74 197 74H243V0Z" fill="currentColor"/>
      <path transform="translate(223.9, 36) scale(0.032, -0.032)" d="M287 -12Q214 -12 159.0 22.0Q104 56 74.0 118.5Q44 181 44 265Q44 350 74.0 412.0Q104 474 159.0 508.0Q214 542 287 542Q360 542 414.5 508.0Q469 474 499.0 412.0Q529 350 529 265Q529 181 499.0 118.5Q469 56 414.5 22.0Q360 -12 287 -12ZM287 68Q360 68 400.5 120.5Q441 173 441 265Q441 357 400.5 409.5Q360 462 287 462Q214 462 173.0 409.5Q132 357 132 265Q132 173 173.0 120.5Q214 68 287 68Z" fill="currentColor"/>
      <path transform="translate(242.3, 36) scale(0.032, -0.032)" d="M80 -150V530H158L159 449Q183 495 225.5 518.5Q268 542 322 542Q401 542 451.5 503.0Q502 464 526.5 401.0Q551 338 551 265Q551 192 526.5 129.0Q502 66 451.5 27.0Q401 -12 322 -12Q270 -12 227.5 10.0Q185 32 164 70V-150ZM314 68Q383 68 423.0 120.0Q463 172 463 265Q463 358 423.0 410.0Q383 462 314 462Q245 462 204.5 412.5Q164 363 164 265Q164 168 204.0 118.0Q244 68 314 68Z" fill="currentColor"/>
      <path transform="translate(261.3, 36) scale(0.032, -0.032)" d="M287 -12Q212 -12 157.5 22.0Q103 56 73.5 118.5Q44 181 44 265Q44 349 73.5 411.0Q103 473 156.5 507.5Q210 542 283 542Q352 542 405.0 509.5Q458 477 487.5 415.0Q517 353 517 264V239H132Q137 154 177.5 111.0Q218 68 287 68Q339 68 372.5 92.5Q406 117 419 157L509 150Q488 79 429.5 33.5Q371 -12 287 -12ZM132 313H425Q419 390 380.5 426.0Q342 462 283 462Q222 462 182.5 424.5Q143 387 132 313Z" fill="currentColor"/>
      <path transform="translate(279.3, 36) scale(0.032, -0.032)" d="M80 0V530H154L157 432Q184 530 283 530H335V450H284Q164 450 164 320V0Z" fill="currentColor"/>
      <path transform="translate(299.4, 36) scale(0.032, -0.032)" d="M92 0V710H312Q476 710 564.5 617.5Q653 525 653 354Q653 184 566.0 92.0Q479 0 318 0ZM178 84H312Q563 84 563 354Q563 626 312 626H178Z" fill="currentColor"/>
      <path transform="translate(321.6, 36) scale(0.032, -0.032)" d="M287 -12Q214 -12 159.0 22.0Q104 56 74.0 118.5Q44 181 44 265Q44 350 74.0 412.0Q104 474 159.0 508.0Q214 542 287 542Q360 542 414.5 508.0Q469 474 499.0 412.0Q529 350 529 265Q529 181 499.0 118.5Q469 56 414.5 22.0Q360 -12 287 -12ZM287 68Q360 68 400.5 120.5Q441 173 441 265Q441 357 400.5 409.5Q360 462 287 462Q214 462 173.0 409.5Q132 357 132 265Q132 173 173.0 120.5Q214 68 287 68Z" fill="currentColor"/>
      <path transform="translate(339.9, 36) scale(0.032, -0.032)" d="M287 -12Q213 -12 158.5 22.0Q104 56 74.0 118.5Q44 181 44 265Q44 349 74.0 411.0Q104 473 158.5 507.5Q213 542 287 542Q379 542 439.0 494.5Q499 447 512 358L424 352Q415 405 378.0 433.5Q341 462 287 462Q214 462 173.0 409.5Q132 357 132 265Q132 173 173.0 120.5Q214 68 287 68Q341 68 378.0 98.0Q415 128 424 188L512 182Q499 94 439.0 41.0Q379 -12 287 -12Z" fill="currentColor"/>
      <path transform="translate(357.4, 36) scale(0.032, -0.032)" d="M273 -12Q164 -12 107.0 38.5Q50 89 44 167L132 173Q140 125 171.5 96.5Q203 68 273 68Q327 68 356.5 85.5Q386 103 386 142Q386 163 376.5 177.0Q367 191 339.0 201.5Q311 212 257 222Q183 236 141.0 257.0Q99 278 82.0 308.0Q65 338 65 380Q65 451 117.5 496.5Q170 542 266 542Q336 542 380.5 517.5Q425 493 448.0 454.0Q471 415 476 372L388 366Q384 404 356.5 433.0Q329 462 264 462Q207 462 180.0 440.0Q153 418 153 384Q153 345 178.0 326.5Q203 308 273 296Q351 283 395.0 263.0Q439 243 456.5 213.5Q474 184 474 142Q474 69 417.5 28.5Q361 -12 273 -12Z" fill="currentColor"/>
    </svg>
  );
}

function SiteHeader({ lang }: { lang: string }) {
  return (
    <header className="site-header">
      <a href={`/docs/${lang}/`} style={{ display: 'inline-flex', alignItems: 'center', height: '100%', width: '16rem', flexShrink: 0, paddingLeft: '0.5rem', textDecoration: 'none', color: 'inherit' }}>
        <CnbLogo />
      </a>
      <HeaderNav lang={lang} />
      <div className="site-header-right">
        <ThemeToggle />
        <LanguageSwitch lang={lang} />
        <AuthButton lang={lang} />
      </div>
    </header>
  );
}

const linkStyle = { fontSize: '0.75rem' as const, color: 'var(--color-fd-foreground)', textDecoration: 'none' as const };

function Footer({ lang }: { lang: string }) {
  const isZh = lang === 'zh';
  return (
    <footer>
      <div style={{
        display: 'flex',
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: '3rem',
        justifyContent: 'space-between',
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <a href="/docs/" style={{ textDecoration: 'none' }}>
            <CnbLogo />
          </a>
          <div style={{ display: 'flex', gap: '1.5rem' }}>
            <a href={REPO_URL} target="_blank" rel="noreferrer" aria-label="GitHub" style={{ color: 'var(--color-fd-muted-foreground)' }}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
            </a>
          </div>
        </div>

        {/* Link columns */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(120px, auto))', gap: '2rem' }}>
          {/* Product */}
          <div>
            <h3 style={{ fontSize: '0.75rem', color: 'var(--color-fd-muted-foreground)', marginBottom: '0.5rem' }}>{isZh ? '产品' : 'Product'}</h3>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <li><a href={`/docs/${lang}/`} style={linkStyle}>{isZh ? '首页' : 'Home'}</a></li>
              <li><a href={`/docs/${lang}/guide/getting-started/`} style={linkStyle}>{isZh ? '快速开始' : 'Getting Started'}</a></li>
              <li><a href={`/docs/${lang}/guide/commands/`} style={linkStyle}>{isZh ? '命令' : 'Commands'}</a></li>
              <li><a href="https://blog.c-n-b.space/posts" style={linkStyle}>Blog</a></li>
            </ul>
          </div>

          {/* Learn */}
          <div>
            <h3 style={{ fontSize: '0.75rem', color: 'var(--color-fd-muted-foreground)', marginBottom: '0.5rem' }}>{isZh ? '了解' : 'Learn'}</h3>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <li><a href={`/docs/${lang}/reference/pricing/`} style={linkStyle}>{isZh ? '定价与用量' : 'Pricing'}</a></li>
              <li><a href={`/docs/${lang}/reference/roadmap/`} style={linkStyle}>{isZh ? '路线图' : 'Roadmap'}</a></li>
              <li><a href={`/docs/${lang}/guide/skills/`} style={linkStyle}>{isZh ? '技能' : 'Skills'}</a></li>
              <li><a href={`/docs/${lang}/guide/feishu-bridge/`} style={linkStyle}>{isZh ? '飞书集成' : 'Feishu Bridge'}</a></li>
            </ul>
          </div>

          {/* Help */}
          <div>
            <h3 style={{ fontSize: '0.75rem', color: 'var(--color-fd-muted-foreground)', marginBottom: '0.5rem' }}>{isZh ? '帮助' : 'Help'}</h3>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <li><a href={REPO_URL} target="_blank" rel="noreferrer" style={linkStyle}>GitHub</a></li>
              <li><a href="https://www.npmjs.com/package/claude-nb" target="_blank" rel="noreferrer" style={linkStyle}>npm</a></li>
              <li><a href={`/docs/${lang}/`} style={linkStyle}>MIT License</a></li>
            </ul>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default async function LangLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  return (
    <Provider locale={lang} i18n={i18nUI.provider(lang)}>
      <SiteHeader lang={lang} />
      <CustomSidebar tree={source.pageTree[lang]} lang={lang} />
      <DocsWrapper lang={lang}>
        <DocsLayout tree={source.pageTree[lang]} {...baseOptions(lang)}>
          {children}
        </DocsLayout>
      </DocsWrapper>
      <FooterWrapper lang={lang}>
        <Footer lang={lang} />
      </FooterWrapper>
    </Provider>
  );
}

export function generateStaticParams() {
  return i18n.languages.map((lang) => ({ lang }));
}
