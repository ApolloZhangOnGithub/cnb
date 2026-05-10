# 管理员待办

这个文件记录需要 registry、仓库或组织凭证才能处理的维护事项。

## 写作规范

面向用户、状态页、实时活动、灵动岛和 Mac companion 的维护待办标题与摘要必须使用中文。命令、包名、URL、issue 链接、错误码和终端输出可以保留原文，避免破坏可执行信息。新增英文来源内容时，提交前先人工整理成中文可读说明。

后续结构化中文展示问题见：https://github.com/ApolloZhangOnGithub/cnb/issues/145

## 当前发布状态

`v0.5.44` 是当前已验证发布版本。

- GitHub Release: https://github.com/ApolloZhangOnGithub/cnb/releases/tag/v0.5.44
- npmjs package: `claude-nb@0.5.44`
- npmjs `latest`: `0.5.44`
- GitHub Packages mirror: `@apollozhangongithub/cnb@0.5.44`
- Release workflow: https://github.com/ApolloZhangOnGithub/cnb/actions/runs/25618433161
- 端到端发布流程已通过：npmjs Trusted Publishing、npmjs readback retry、全新安装 smoke、GitHub Packages mirror publish、GitHub Packages mirror verification。

## npm `stable` dist-tag

剩余阻塞：`stable` 标签还没有设置。

当前检查方式：

```bash
npm view claude-nb dist-tags --json
```

当前结果：

```json
{
  "latest": "0.5.44"
}
```

本地证据：

- `~/.npmrc` 里有 npmjs auth token 行。
- 当前 shell 环境没有 `NPM_TOKEN`。
- `npm whoami --registry=https://registry.npmjs.org/` 返回 `E401`。
- `npm dist-tag add claude-nb@0.5.44 stable` 返回 `E401`。

下一步维护动作：

```bash
npm login --registry=https://registry.npmjs.org/
npm whoami --registry=https://registry.npmjs.org/
npm dist-tag add claude-nb@0.5.44 stable --registry=https://registry.npmjs.org/
npm view claude-nb dist-tags --json
```

期望最终 dist-tags：

```json
{
  "latest": "0.5.44",
  "stable": "0.5.44"
}
```

跟踪 issue: https://github.com/ApolloZhangOnGithub/cnb/issues/100

## 可选的 GitHub Actions Secret

Trusted Publishing 现在已经可以在没有本地维护者 shell 的情况下处理 `npm publish`。但它目前不会移动 `stable`，因为 workflow 没有可用的 `NPM_TOKEN` secret。

如果维护者希望 release 时自动移动 `stable`：

1. 创建一个有效的 npm token，权限需要能修改 `claude-nb` 的 dist-tags。
2. 把它添加到 GitHub repository secret，名称为 `NPM_TOKEN`。
3. 正常发布下一个版本，并确认 `Try to move stable dist-tag` 步骤不再报告 auth notice。

不要把 npm token 存进仓库。

## Prepare Release 自动创建 PR

`Prepare Release` workflow 可以推送 release branches。当前仓库设置阻止 GitHub Actions 创建 pull request，所以 workflow 会降级为 warning，并把手动 compare link 写到 step summary。

可选维护动作：

- 如果希望 release PR 完全自动创建，在 repository settings 里允许 GitHub Actions 创建 PR。

保持当前禁用状态也可以接受，因为 release branch 和验证仍然会完成；只是 PR 点击需要人工处理。

## GitHub Packages 侧边栏

当前版本不需要处理。

发布 `@apollozhangongithub/cnb@0.5.44` mirror 后，仓库 Packages 侧边栏不应该再显示为空。继续把 npmjs `claude-nb` 作为用户安装的主路径；GitHub Packages 只作为可见性 mirror，除非未来有迁移 issue 改变这个策略。

## 未来 `c-n-b` 包名迁移

`c-n-b.space` 可以继续作为网站域名，但 `c-n-b` 还不是已发布 npm 包。不要在完成迁移前把它写成安装路径。

改 canonical npm 包名之前必须完成：

1. 确认 `npm view c-n-b` 返回 404 或已经指向本项目。
2. 为 `c-n-b` 配置 npm Trusted Publishing，绑定 `ApolloZhangOnGithub/cnb` 和 `.github/workflows/publish-npm.yml`。
3. 在同一个 PR 里修改 package metadata、release workflows、docs 和 site copy。
4. 发布一个真实 non-dev release，占用 `c-n-b` 包名。
5. 从干净临时 prefix 验证新包能安装 `cnb` 命令。
6. 验证后再移动 `latest` 和 `stable`。

跟踪 issue: https://github.com/ApolloZhangOnGithub/cnb/issues/132

## 站点 HTTPS

`http://c-n-b.space` 已经由 GitHub Pages 提供服务。GitHub Pages health 显示 apex 和 `www` DNS 记录有效，并由 Pages 服务；HTTPS 强制开启还需要等待 GitHub 证书签发。

证书出现后重试：

```bash
gh api --method PUT repos/ApolloZhangOnGithub/cnb/pages \
  -F https_enforced=true \
  -f cname='c-n-b.space'
```

## 2026-05-10 部署收口

custom-domain 部署已在 merge commit `c170c9c8` 后上线。`c-n-b` 包名迁移因 issue #132 暂停，因为 npm 包还不存在。

已完成：

- GitHub About homepage 是 `c-n-b.space`，没有尾部 slash。
- GitHub Pages deploy 成功，`http://c-n-b.space` 可以访问公开项目站点。
- PR #130 merge 前 checks 通过，merge 后 `master` CI、CodeQL、Graph Update 和 Pages 都完成。
- 当前已验证包仍是 `claude-nb@0.5.44`；docs 和 release workflows 在 #132 完成前继续使用它。

回滚/修复后续：

- 恢复 GitHub Release 标题，不要在包名真实迁移前显示 `c-n-b 0.5.44`、`c-n-b 0.5.43`、`c-n-b 0.5.31`。
- 公开安装链接继续指向 `https://www.npmjs.com/package/claude-nb`。

仍待处理：

1. 等 GitHub Pages 为 `c-n-b.space` 签发证书。
2. 重跑上面的 HTTPS enforcement 命令。
3. 完成 issue #132 后才能宣传 `c-n-b` 作为 npm 安装包名。
4. 持续提醒用户不要安装 npm 上无关的 `cnb` 包。
