export const appName = 'cnb';
export const docsRoute = '';
export const docsImageRoute = '/og';
export const docsContentRoute = '/llms.mdx';

export const gitConfig = {
  user: 'ApolloZhangOnGithub',
  repo: 'cnb',
  branch: 'master',
};

export const repoBase = `https://github.com/${gitConfig.user}/${gitConfig.repo}`;
export const repoBlobBase = `${repoBase}/blob/${gitConfig.branch}`;
export const appPaths = {
  mac: `${repoBlobBase}/apps/mac`,
  island: `${repoBlobBase}/apps/island`,
  contributing: `${repoBlobBase}/CONTRIBUTING.md`,
  claudemd: `${repoBlobBase}/CLAUDE.md`,
  security: `${repoBlobBase}/SECURITY.md`,
  license: `${repoBlobBase}/LICENSE`,
};
export const siteUrls = {
  home: 'https://c-n-b.space',
  download: 'https://c-n-b.space/download',
  blog: 'https://blog.c-n-b.space/feed',
  docs: 'https://platform.c-n-b.space/docs',
  npm: 'https://www.npmjs.com/package/claude-nb',
};
