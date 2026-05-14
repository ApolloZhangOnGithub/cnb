'use client';
import SearchDialog from '@/components/search';
import { RootProvider } from 'fumadocs-ui/provider/next';
import type { I18nProviderProps } from 'fumadocs-ui/contexts/i18n';
import { type ReactNode } from 'react';

export function Provider({
  children,
  locale,
  i18n,
}: {
  children: ReactNode;
  locale?: string;
  i18n?: Omit<I18nProviderProps, 'children'>;
}) {
  return (
    <RootProvider search={{ SearchDialog }} i18n={i18n} theme={{ enabled: false }}>
      {children}
    </RootProvider>
  );
}
