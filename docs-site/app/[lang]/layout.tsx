import { i18n, i18nUI } from '@/lib/i18n';
import { Provider } from '@/components/provider';
import { source } from '@/lib/source';
import { DocsLayout } from 'fumadocs-ui/layouts/docs';
import { baseOptions } from '@/lib/layout.shared';
import { CustomSidebar } from '@/components/custom-sidebar';
import { ThemeToggle, LanguageSwitch } from '@/components/theme-toggle';

function SiteHeader({ lang }: { lang: string }) {
  return (
    <header className="site-header">
      <a href="https://c-n-b.space" className="site-header-brand">cnb docs</a>
      <div className="site-header-right">
        <ThemeToggle />
        <LanguageSwitch lang={lang} />
        <div className="header-divider" aria-hidden="true" />
        <a href="https://github.com/ApolloZhangOnGithub/cnb">GitHub</a>
        <a href="https://www.npmjs.com/package/claude-nb" className="header-btn-primary">npm</a>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="site-footer">
      <div className="max-w-[1200px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <span>cnb is open source, local-first software. Human supervision required.</span>
        <div className="flex gap-6">
          <a href="https://c-n-b.space">Home</a>
          <a href="https://github.com/ApolloZhangOnGithub/cnb">GitHub</a>
          <a href="https://github.com/ApolloZhangOnGithub/cnb/blob/master/LICENSE">MIT License</a>
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
      <CustomSidebar tree={source.pageTree[lang]} />
      <div className="docs-with-sidebar">
        <DocsLayout tree={source.pageTree[lang]} {...baseOptions(lang)}>
          {children}
        </DocsLayout>
      </div>
      <Footer />
    </Provider>
  );
}

export function generateStaticParams() {
  return i18n.languages.map((lang) => ({ lang }));
}
