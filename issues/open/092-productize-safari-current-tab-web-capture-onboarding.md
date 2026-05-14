---
number: 92
title: "Productize Safari current-tab web capture onboarding"
state: OPEN
labels: ["enhancement", "phase:2", "experiment", "infra"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
---

# #92 Productize Safari current-tab web capture onboarding

**State:** OPEN
**Labels:** enhancement, phase:2, experiment, infra

---

## 背景

用户有时已经在 Safari 打开了一个不能重开、不能 print、也不适合用 Computer Use 粗暴读取的网页，需要把当前页面内容显式交给 cnb/agent。

cnb 侧已经有 `cnb capture ingest` 协议和 `.cnb/captures/<id>/` artifact；sidecar repo `/Users/zhangkezhen/Desktop/Toolbase_Skills/cnb-web-capture` 已经有本地提交 `fe82238 feat: add Safari loopback web capture`。

## 当前验证结果

- `npm test` 通过：10 个测试。
- `xcodebuild` Safari containing app 通过。
- `pluginkit` 能登记 `com.cnb.CNBWebCapture.Extension`。
- loopback server 能真实调用 `cnb capture ingest`，并写入 `~/.cnb/captures`。
- 已验证新增 capture：`20260509T231121Z-example-browser-page-14c35b898b`。

## 当前启用方式（开发态）

1. 启动本机 bridge：

```bash
cd /Users/zhangkezhen/Desktop/Toolbase_Skills/cnb-web-capture
node native-host/cnb-web-capture-server.mjs \
  --cnb /Users/zhangkezhen/Desktop/Toolbase_Skills/claudes-code/bin/cnb \
  --global \
  --no-notify \
  --allow-unauthenticated
```

2. 构建 Safari containing app：

```bash
xcodebuild \
  -project safari-app/CNBWebCapture/CNBWebCapture.xcodeproj \
  -scheme CNBWebCapture \
  -configuration Debug \
  -derivedDataPath /private/tmp/cnb-web-capture-dd \
  CODE_SIGN_STYLE=Manual CODE_SIGN_IDENTITY=- DEVELOPMENT_TEAM= build
```

3. 启动 app 让系统登记 extension：

```bash
open -n /private/tmp/cnb-web-capture-dd/Build/Products/Debug/CNBWebCapture.app
```

4. 在 Safari Settings / Extensions 中启用 `cnb Web Capture`，打开目标页面后点击扩展按钮。

备注：如果 Safari 不显示本地 ad-hoc extension，需要确认是否需要 Safari 开发菜单中的 unsigned extension 开关，或改成正式 Developer ID 签名/打包。

## 设计结论

Safari Web Extension 保持 sandbox 才能稳定登记；因此不要让 extension 直接执行桌面里的 `bin/cnb` 或写 `~/.cnb`。默认路径应为：

1. 用户点击扩展按钮。
2. content script 只读取当前 tab DOM/selection。
3. background script 尝试 native messaging。
4. 失败时 fallback 到 `http://127.0.0.1:47327/capture`。
5. loopback server 作为普通本地进程调用 `cnb capture ingest`。

这条路径不需要 macOS Accessibility，也不需要 Screen Recording。

## 后续开发任务

- [ ] 把 sidecar 的启动/停止做成 cnb 子命令或 `tools/web-capture/` 管理脚本，例如 `cnb capture bridge start/status/stop`。
- [ ] 决定 sidecar 代码是继续独立 repo、作为 cnb submodule/vendor，还是生成式 scaffold；保留 cnb 协议为稳定边界。
- [ ] 产品化 Safari app：bundle id、签名、安装位置、启动项/菜单栏状态、日志位置。
- [ ] 做 token 握手：默认 bridge 不应长期 `--allow-unauthenticated`，extension/server 需要共享 token 或一次性 session。
- [ ] 增加 agent 可读的 README/runbook，明确如何启动 bridge、启用 Safari extension、检查 capture 结果。
- [ ] 补端到端人工验收脚本：启动 bridge -> 构建/启动 app -> 用户启用 extension -> 点击当前 tab -> `cnb capture list/show` 出现真实页面标题和 URL。
- [ ] 明确失败提示：bridge 未启动、extension 未启用、Safari native messaging 不可用、payload 太大、cnb ingest 失败。

## 验收标准

- 用户不需要开启无障碍或截图权限。
- 用户不需要重开 URL 或 print 页面。
- Safari 当前 tab 的 title/url/selection/article/page text/sanitized html 能进入 cnb capture artifact。
- `cnb capture list --global` 和 `cnb capture show --global <id>` 能看到刚导出的页面。
- 未启动 bridge 时扩展有清晰错误；启动 bridge 后一键 capture 成功。
- README/工具说明足够后续 agent 不读全部源码也能继续维护。

## 相关本地证据

- cnb repo: `/Users/zhangkezhen/Desktop/Toolbase_Skills/claudes-code`
- sidecar repo: `/Users/zhangkezhen/Desktop/Toolbase_Skills/cnb-web-capture`
- sidecar commit: `fe82238 feat: add Safari loopback web capture`
- generated Safari app build path: `/private/tmp/cnb-web-capture-dd/Build/Products/Debug/CNBWebCapture.app`

