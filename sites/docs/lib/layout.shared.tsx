import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { appName } from './shared';

export function baseOptions(lang?: string): BaseLayoutProps {
  return {
    nav: {
      title: appName,
      url: `/${lang ?? 'zh'}`,
      enabled: false,
    },
    i18n: false,
    links: [],
  };
}
