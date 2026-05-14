import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { appName } from './shared';
import { i18n } from './i18n';

export function baseOptions(lang?: string): BaseLayoutProps {
  return {
    nav: {
      title: appName,
      url: `/${lang ?? 'zh'}`,
      enabled: false,
    },
    i18n,
  };
}
