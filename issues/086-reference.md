---
number: 86
title: "研究：外部代码/文章引用记录与跨仓库 reference 机制"
state: OPEN
labels: ["question", "experiment", "infra"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
---

# #86 研究：外部代码/文章引用记录与跨仓库 reference 机制

**State:** OPEN
**Labels:** question, experiment, infra

---

## ROADMAP 检查

- [x] 已阅读 `ROADMAP.md`，确认本 issue 不与现有计划冲突或重复。

## 与 ROADMAP 的关系

ROADMAP 目前没有直接覆盖“开发过程中参考外部代码库、网页文章、论文、设计文档时如何记录来源”的规则。

相关但不重复：

- #47 讨论跨项目统一身份；本 issue 讨论跨仓库/跨资料来源的 provenance/reference 关系。
- #54 讨论上下文健康；本 issue 可以成为上下文健康的一部分，但重点是来源、许可、可追溯性和引用机制。
- #56 讨论 GitHub Wiki 维护；本 issue 若落地，Wiki/文档可能承载人类可读说明，但还需要机器可读记录。
- #76 讨论组织治理；本 issue 是工程治理和知识治理的一个具体开放问题。

建议暂列为研究/实验议题，不直接进入执行 backlog，除非先定义最低成本的规则。

## 描述

开放问题：当同学在开发中参考了别人的代码库、网页文章、博客、论文、issue、PR、Stack Overflow 回答等资料时，是否应该像学术写作一样记录 reference？如果要记录，仅仅在 README 或 PR 里写一个 reference 是否足够？对于 cnb 这种多同学、多仓库、长期记忆的组织系统，是否需要建立仓库之间、文件之间、任务之间的结构化引用机制？

初步判断：不能简单照搬“学术引用”。软件开发里至少有三类不同问题：

1. **法律/许可合规**：复制、改写、vendoring、forking 代码时，reference 不是核心；核心是许可证兼容、保留版权/许可/NOTICE、标明修改、必要时保留 license text。只写“参考了某仓库”可能远远不够。
2. **工程可追溯性**：即使只是参考文章、算法说明或设计思路，也应该能让后来的同学知道这个决策来自哪里，避免丢上下文或重复研究。
3. **信用与协作关系**：cnb 未来如果管理多个仓库，仓库之间可能存在“借鉴 / 派生 / vendored / depends-on / implements-paper / inspired-by”等关系；这更像知识图谱或 SBOM/provenance，而不是单纯 bibliography。

这不是法律意见。真正涉及许可证解释、商业分发、copyleft 兼容性时仍应咨询专业法律意见。

## 初步研究

- GitHub 文档提醒：没有许可证时，默认版权法仍适用，公开仓库并不等于别人可以复制、分发或制作衍生作品；仓库最好有清晰 license 文件。https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
- GitHub 支持仓库根目录的 `CITATION.cff`，用于告诉别人如何引用本仓库，并在 GitHub 上显示 “Cite this repository”。这解决的是“别人如何引用我们”，不是我们如何记录自己参考了谁。https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files
- Citation File Format 本身是人类和机器都可读的软件引用元数据格式，但其说明也承认它还不是完整的 transitive credit/attribution 机制。https://citation-file-format.github.io/about/
- REUSE 规范把每个文件或片段的版权与 SPDX license 信息放在 comment header、`.license` 或 `REUSE.toml` 等位置；这更适合处理“直接复制/改写代码片段”的许可追踪。https://reuse.software/spec-3.2/
- Apache-2.0 的 NOTICE 机制说明，某些许可证要求在衍生作品中保留 attribution notices；这说明“reference”有时是许可证义务的一部分，不只是礼貌。https://www.apache.org/legal/apply-license
- SPDX 是用于 SBOM、provenance、license、security 等供应链信息的开放标准；如果未来要做跨仓库、跨组件关系，SPDX/REUSE/CodeMeta 这类机器可读元数据值得参考。https://spdx.dev/about/overview/

## 设计要点

建议先定义一个轻量分层策略，而不是一刀切要求所有开发都写学术式 reference：

- **L0 背景阅读**：只是泛读、没有直接影响实现，不强制记录。
- **L1 设计/文章参考**：文章、论文、issue、PR、设计文档影响了方案，应在 issue/PR/design doc 中记录 URL、标题、访问日期或 commit/tag（如果适用）、采用了什么观点。
- **L2 代码片段复制或改写**：必须记录来源 URL、原仓库、commit/tag、文件路径、原许可证、保留的版权/NOTICE、我们改了什么；必要时用 SPDX/REUSE snippet 或 per-file 头部标记。
- **L3 vendored/forked/submodule/dependency**：必须有明确的依赖/供应链记录，例如 package manifest、submodule、`THIRD_PARTY.yml`、`NOTICE`、`LICENSES/`、SBOM 等；不能只靠一条 reference。
- **L4 cnb 管理的跨仓库关系**：记录结构化关系，例如 `depends-on`、`derived-from`、`inspired-by`、`implements`、`fork-of`、`replaces`、`mirrors`。这可以服务于未来的跨项目 dashboard、owner 交接、上下文恢复和知识合并。

一个可能的最小落地形态：

- 文档层：在 `.github/CONTRIBUTING.md` 增加 “External references and third-party code” 规则。
- 人类可读层：增加 `REFERENCES.md`，记录重要文章/仓库/论文引用。
- 机器可读层：增加 `.cnb/references.jsonl` 或 `references.yml`，每条记录包含：`kind`、`url`、`source_repo`、`source_commit`、`source_path`、`scope`、`license`、`relationship`、`notes`、`recorded_by`、`recorded_at`。
- 合规层：对 L2/L3 使用 `LICENSES/`、`NOTICE`、`THIRD_PARTY.yml`、SPDX license identifiers、REUSE comment headers/snippet markers。
- CLI 层：未来可增加 `cnb reference add/list/verify`，并在 CI 中做最低限度检查，例如出现 “copied from / based on / adapted from” 但没有 reference 记录时提醒。

## 需要决策的问题

1. cnb 是否要把“参考来源记录”纳入 contributor workflow？如果纳入，最低强制级别是 L1 还是只强制 L2/L3？
2. 参考网页文章/论文是否只放在 issue/PR/design doc 即可，还是也要进入机器可读 registry？
3. 对代码片段，是否采用 REUSE/SPDX snippet 作为默认格式？
4. 对 vendored/forked 代码，是否引入 `THIRD_PARTY.yml`、`NOTICE`、`LICENSES/` 或 SBOM？
5. 跨仓库 reference 是否应成为 cnb 的一等对象，和 ownership、task、project registry 一样被 CLI 管理？
6. 谁负责 review 这些 reference？代码 owner、code health owner，还是未来的 governance/knowledge owner？

## 验收标准（研究完成）

- 给出一页政策草案：什么时候必须记录、记录在哪里、记录哪些字段。
- 明确区分 attribution/reference/citation/dependency/license notice 这几个概念。
- 决定是否采用现有标准：CITATION.cff、REUSE、SPDX、CodeMeta、SBOM 中哪些适合 cnb。
- 如果决定落地最小实现，补充 `CONTRIBUTING.md` 规则，并定义一个最小 `references.yml` 或 `.cnb/references.jsonl` schema。
- 如果决定不做机制，也要写清楚理由：例如维护成本过高，只在 L2/L3 强制记录即可。

