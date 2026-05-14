import SwiftUI

struct OverviewView: View {
    @ObservedObject var store: CNBStateStore
    @ObservedObject var feishuViewModel: FeishuChatViewModel
    @ObservedObject var adminTodoViewModel: CNBAdminTodoViewModel
    @State private var filter: OverviewProjectFilter = .smart
    @State private var isShowingAdminTodo = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HeaderView(
                    snapshot: store.snapshot,
                    isLoading: store.isLoading,
                    topProject: store.snapshot.topProjects.first,
                    onRefresh: { store.refresh() },
                    onOpenTopProject: openProject
                )

                if let errorMessage = store.errorMessage {
                    StatusMessage(text: errorMessage, systemImage: "exclamationmark.triangle.fill", tint: .orange)
                }

                LazyVGrid(columns: overviewColumns, spacing: 12) {
                    AdminTodoOverviewCard(viewModel: adminTodoViewModel) {
                        isShowingAdminTodo = true
                    }

                    DiagnosticsOverviewCard(
                        snapshot: store.snapshot,
                        errorMessage: store.errorMessage,
                        feishuViewModel: feishuViewModel,
                        adminTodoViewModel: adminTodoViewModel,
                        onRefresh: refreshDiagnostics,
                        onOpenChat: { store.selectedProjectID = CNBStateStore.feishuSelectionID },
                        onOpenAdminTodo: { isShowingAdminTodo = true }
                    )
                }

                LazyVGrid(columns: metricColumns, spacing: 12) {
                    MetricCard(
                        title: OverviewProjectFilter.smart.title,
                        value: store.snapshot.topProjects.count,
                        systemImage: "sparkle.magnifyingglass",
                        isSelected: filter == .smart
                    ) { filter = .smart }
                    MetricCard(
                        title: L10n.string("metric.projects"),
                        value: store.snapshot.boardProjects.count,
                        systemImage: "folder",
                        isSelected: filter == .all
                    ) { filter = .all }
                    MetricCard(
                        title: OverviewProjectFilter.attention.title,
                        value: store.snapshot.attentionProjects.count,
                        systemImage: "exclamationmark.triangle.fill",
                        isSelected: filter == .attention
                    ) { filter = .attention }
                    MetricCard(
                        title: L10n.string("metric.tasks"),
                        value: store.snapshot.activeTasks,
                        systemImage: "checklist",
                        isSelected: filter == .tasks
                    ) { filter = .tasks }
                    MetricCard(
                        title: L10n.string("metric.unread"),
                        value: store.snapshot.unreadMessages,
                        systemImage: "tray.full",
                        isSelected: filter == .unread
                    ) { filter = .unread }
                    MetricCard(
                        title: L10n.string("metric.sessions"),
                        value: store.snapshot.sessions,
                        systemImage: "terminal",
                        isSelected: filter == .sessions
                    ) { filter = .sessions }
                    MetricCard(
                        title: L10n.string("metric.no_board"),
                        value: store.snapshot.missingBoardProjects.count,
                        systemImage: "folder.badge.questionmark",
                        isSelected: filter == .noBoard
                    ) { filter = .noBoard }
                    MetricCard(
                        title: L10n.string("metric.stale"),
                        value: store.snapshot.staleRegistryEntries,
                        systemImage: "archivebox",
                        isSelected: false
                    ) { store.refresh() }
                }

                ProjectTableView(
                    title: L10n.format("overview.filter.showing", filter.title),
                    projects: filteredProjects,
                    onSelect: openProject
                )
            }
            .padding(.top, DetailChromeMetrics.contentTopPadding)
            .padding(.horizontal, DetailChromeMetrics.contentHorizontalPadding)
            .padding(.bottom, DetailChromeMetrics.contentBottomPadding)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .navigationTitle("")
        .sheet(isPresented: $isShowingAdminTodo) {
            AdminTodoDetailView(viewModel: adminTodoViewModel)
                .frame(minWidth: 640, minHeight: 520)
        }
    }

    private var filteredProjects: [CNBProjectSummary] {
        let snapshot = store.snapshot
        switch filter {
        case .smart:
            return snapshot.topProjects.isEmpty ? snapshot.projects : snapshot.topProjects
        case .all:
            return snapshot.projects
        case .attention:
            return snapshot.attentionProjects
        case .tasks:
            return snapshot.projects.filter { $0.taskTotal > 0 }
        case .unread:
            return snapshot.projects.filter { $0.unreadMessages > 0 }
        case .sessions:
            return snapshot.projects.filter { $0.sessions > 0 }
        case .noBoard:
            return snapshot.missingBoardProjects
        }
    }

    private var metricColumns: [GridItem] {
        [GridItem(.adaptive(minimum: 132, maximum: 190), spacing: 12, alignment: .top)]
    }

    private var overviewColumns: [GridItem] {
        [GridItem(.adaptive(minimum: 300, maximum: 560), spacing: 12, alignment: .top)]
    }

    private func openProject(_ project: CNBProjectSummary) {
        store.selectedProjectID = project.id
    }

    private func refreshDiagnostics() {
        store.refresh()
        adminTodoViewModel.reload()
        feishuViewModel.reloadRuntimeSettings()
    }
}

private enum OverviewProjectFilter: Hashable {
    case smart
    case all
    case attention
    case tasks
    case unread
    case sessions
    case noBoard

    var title: String {
        switch self {
        case .smart:
            L10n.string("overview.filter.smart")
        case .all:
            L10n.string("overview.filter.all")
        case .attention:
            L10n.string("overview.filter.attention")
        case .tasks:
            L10n.string("metric.tasks")
        case .unread:
            L10n.string("metric.unread")
        case .sessions:
            L10n.string("metric.sessions")
        case .noBoard:
            L10n.string("metric.no_board")
        }
    }
}

private struct HeaderView: View {
    let snapshot: CNBSnapshot
    let isLoading: Bool
    let topProject: CNBProjectSummary?
    let onRefresh: () -> Void
    let onOpenTopProject: (CNBProjectSummary) -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: snapshot.status.systemImage)
                .font(.system(size: 30, weight: .semibold))
                .foregroundStyle(snapshot.status.tint)
                .frame(width: 40)

            VStack(alignment: .leading, spacing: 4) {
                Text(snapshot.title)
                    .font(.title2.bold())
                    .lineLimit(1)
                Text(snapshot.detail)
                    .foregroundStyle(.secondary)
                Text(L10n.format("snapshot.refreshed", snapshot.machineName, Formatters.time.string(from: snapshot.generatedAt)))
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }

            Spacer()

            HStack(spacing: 8) {
                if let topProject {
                    Button {
                        onOpenTopProject(topProject)
                    } label: {
                        Label(L10n.format("overview.action.open_top_project", topProject.name), systemImage: "arrow.right.circle")
                    }
                    .controlSize(.small)
                }

                Button {
                    onRefresh()
                } label: {
                    Image(systemName: isLoading ? "hourglass" : "arrow.clockwise")
                }
                .controlSize(.small)
                .help(L10n.string("overview.action.refresh"))
                .disabled(isLoading)
            }
        }
    }
}

private struct MetricCard: View {
    let title: String
    let value: Int
    let systemImage: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: systemImage)
                        .foregroundStyle(isSelected ? Color.accentColor : Color.secondary)
                    Spacer()
                    if isSelected {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(.tint)
                            .font(.caption)
                    }
                }

                Text("\(value)")
                    .font(.system(.title2, design: .rounded).weight(.semibold))
                    .monospacedDigit()
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(14)
            .frame(maxWidth: .infinity, minHeight: 104, alignment: .leading)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(isSelected ? Color.accentColor.opacity(0.65) : Color.clear, lineWidth: 1)
            }
            .contentShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .buttonStyle(.plain)
        .help(L10n.format("overview.filter.showing", title))
    }
}

private struct AdminTodoOverviewCard: View {
    @ObservedObject var viewModel: CNBAdminTodoViewModel
    let onOpen: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            OverviewSectionHeader(
                title: "ADMIN_TO_DO",
                detail: viewModel.statusMessage,
                systemImage: viewModel.hasActionableItems ? "list.bullet.clipboard.fill" : "checkmark.seal.fill",
                tint: viewModel.hasActionableItems ? .orange : .green
            )

            if viewModel.isLoaded {
                Text(viewModel.document.currentReleaseSummary)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(3)

                ForEach(viewModel.document.actionableSections.prefix(2)) { section in
                    AdminTodoInlineRow(section: section, action: onOpen)
                }

                if !viewModel.hasActionableItems {
                    Text("当前没有需要管理员凭证处理的事项。")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
            } else {
                OverviewIssueRow(
                    title: "维护待办未读取",
                    detail: "没有找到 ADMIN_TO_DO.md。可以用 CNB_ADMIN_TODO_PATH 指定文件，或从仓库根目录启动。",
                    actionTitle: "重试",
                    systemImage: "doc.badge.clock",
                    tint: .orange,
                    action: viewModel.reload
                )
            }

            Button(action: onOpen) {
                Label("查看全部维护待办", systemImage: "chevron.right.circle.fill")
                    .font(.subheadline.weight(.semibold))
                    .frame(maxWidth: .infinity, minHeight: 36)
            }
            .buttonStyle(.plain)
            .cnbGlassCardBackground(cornerRadius: 8, tint: Color.accentColor.opacity(0.08))
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .cnbGlassCardBackground(cornerRadius: 8, tint: viewModel.hasActionableItems ? Color.orange.opacity(0.08) : Color.green.opacity(0.05))
    }
}

private struct DiagnosticsOverviewCard: View {
    let snapshot: CNBSnapshot
    let errorMessage: String?
    @ObservedObject var feishuViewModel: FeishuChatViewModel
    @ObservedObject var adminTodoViewModel: CNBAdminTodoViewModel
    let onRefresh: () -> Void
    let onOpenChat: () -> Void
    let onOpenAdminTodo: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            OverviewSectionHeader(
                title: "诊断",
                detail: issueCount == 0 ? "没有发现阻塞项" : "有可操作事项，点卡片处理",
                systemImage: issueCount == 0 ? "checkmark.seal.fill" : "exclamationmark.triangle.fill",
                tint: issueCount == 0 ? .green : .orange
            )

            if let errorMessage {
                OverviewIssueRow(
                    title: "状态读取失败",
                    detail: errorMessage,
                    actionTitle: "重试",
                    systemImage: "externaldrive.badge.exclamationmark",
                    tint: .red,
                    action: onRefresh
                )
            }

            if snapshot.staleRegistryEntries > 0 {
                OverviewIssueRow(
                    title: "注册表有失效项目",
                    detail: "\(snapshot.staleRegistryEntries) 个项目路径已经不可用，刷新会重新清理本机状态。",
                    actionTitle: "刷新",
                    systemImage: "archivebox.fill",
                    tint: .orange,
                    action: onRefresh
                )
            }

            if !adminTodoViewModel.isLoaded {
                OverviewIssueRow(
                    title: "ADMIN_TO_DO 未读取",
                    detail: "mac 和 iOS 状态页都会基于这个文件提示维护待办。请同步或指定路径。",
                    actionTitle: "查看",
                    systemImage: "list.bullet.clipboard",
                    tint: .orange,
                    action: onOpenAdminTodo
                )
            } else if adminTodoViewModel.hasActionableItems {
                OverviewIssueRow(
                    title: "有维护待办",
                    detail: adminTodoViewModel.primaryAction?.summary ?? "打开后查看需要管理员处理的事项。",
                    actionTitle: "处理",
                    systemImage: "person.badge.key.fill",
                    tint: .orange,
                    action: onOpenAdminTodo
                )
            }

            if !feishuViewModel.settings.isReady {
                OverviewIssueRow(
                    title: "飞书连接未就绪",
                    detail: "appID、appSecret 或 chatID 不完整。mac 和 iOS 都需要同一份飞书配置。",
                    actionTitle: "打开对话",
                    systemImage: "macbook.and.iphone",
                    tint: .orange,
                    action: onOpenChat
                )
            }

            if let failure = readableFeishuFailure {
                OverviewIssueRow(
                    title: "飞书连接失败",
                    detail: failure,
                    actionTitle: "打开对话",
                    systemImage: "network.slash",
                    tint: .red,
                    action: onOpenChat
                )
            }

            if snapshot.pendingActions > 0 || snapshot.blockedSessions > 0 {
                OverviewIssueRow(
                    title: "项目需要处理",
                    detail: "有待确认动作或阻塞会话，进入对话页发指令给值班通道。",
                    actionTitle: "打开对话",
                    systemImage: "person.crop.circle.badge.exclamationmark",
                    tint: .orange,
                    action: onOpenChat
                )
            }

            if issueCount == 0 {
                OverviewIssueRow(
                    title: "状态正常",
                    detail: "本机项目、维护待办和飞书配置都可读取。需要新状态时可以重新诊断。",
                    actionTitle: "重新检查",
                    systemImage: "checkmark.circle.fill",
                    tint: .green,
                    action: onRefresh
                )
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .cnbGlassCardBackground(cornerRadius: 8, tint: issueCount == 0 ? Color.green.opacity(0.05) : Color.orange.opacity(0.08))
    }

    private var issueCount: Int {
        var count = 0
        if errorMessage != nil { count += 1 }
        if snapshot.staleRegistryEntries > 0 { count += 1 }
        if !adminTodoViewModel.isLoaded || adminTodoViewModel.hasActionableItems { count += 1 }
        if !feishuViewModel.settings.isReady { count += 1 }
        if readableFeishuFailure != nil { count += 1 }
        if snapshot.pendingActions > 0 || snapshot.blockedSessions > 0 { count += 1 }
        return count
    }

    private var readableFeishuFailure: String? {
        let text = feishuViewModel.statusMessage
        guard text.localizedCaseInsensitiveContains("failed") || text.contains("失败") else {
            return nil
        }
        return Self.readableFailure(from: text)
    }

    private static func readableFailure(from text: String) -> String {
        let lower = text.lowercased()
        if lower.contains("address already in use") || text.contains("端口占用") {
            return "端口已被占用。请关闭占用本地 webhook 端口的旧进程，或改用新的端口后重启 bridge。"
        }
        if lower.contains("connection refused") || lower.contains("-1004") || lower.contains("could not connect") {
            return "服务未启动或本机 bridge 没有监听。请先启动 Feishu bridge，再重试。"
        }
        if lower.contains("timed out") || lower.contains("-1001") || text.contains("超时") {
            return "连接超时。可能是网络不可达、隧道不可用，或 Feishu OpenAPI 没有响应。"
        }
        if lower.contains("not connected to internet") || lower.contains("-1009") || text.contains("网络不可达") {
            return "网络不可达。请确认联网，并且 Mac bridge 的公网回调地址可访问。"
        }
        if lower.contains("http 401") || lower.contains("http 403") {
            return "飞书权限或凭证失败。请检查 appSecret、机器人入群状态和消息权限。"
        }
        return text
    }
}

private struct OverviewSectionHeader: View {
    let title: String
    let detail: String
    let systemImage: String
    let tint: Color

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: systemImage)
                .font(.headline.weight(.semibold))
                .foregroundStyle(tint)
                .frame(width: 28, height: 28)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline.weight(.semibold))
                    .lineLimit(1)
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer(minLength: 0)
        }
    }
}

private struct AdminTodoInlineRow: View {
    let section: CNBAdminTodoSection
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "exclamationmark.circle.fill")
                    .foregroundStyle(.orange)
                    .frame(width: 24, height: 24)

                VStack(alignment: .leading, spacing: 3) {
                    Text(section.heading)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.primary)
                        .lineLimit(2)
                    Text(section.summary)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }

                Spacer(minLength: 8)

                Image(systemName: "chevron.right")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.secondary)
            }
            .padding(10)
            .background(Color.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .contentShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

private struct OverviewIssueRow: View {
    let title: String
    let detail: String
    let actionTitle: String
    let systemImage: String
    let tint: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: systemImage)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(tint)
                    .frame(width: 24, height: 24)

                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.primary)
                        .lineLimit(2)
                    Text(detail)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)
                }

                Spacer(minLength: 8)

                Text(actionTitle)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(tint)
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)
            }
            .padding(10)
            .background(tint.opacity(0.08), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .contentShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

private struct AdminTodoDetailView: View {
    @ObservedObject var viewModel: CNBAdminTodoViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                OverviewSectionHeader(
                    title: viewModel.document.title,
                    detail: viewModel.statusMessage,
                    systemImage: "list.bullet.clipboard",
                    tint: viewModel.hasActionableItems ? .orange : .green
                )
                Spacer(minLength: 12)
                Button {
                    viewModel.reload()
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                Button("完成") {
                    dismiss()
                }
            }
            .padding(16)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if viewModel.isLoaded {
                        ForEach(viewModel.document.sections) { section in
                            AdminTodoSectionCard(section: section)
                        }
                    } else {
                        OverviewIssueRow(
                            title: "ADMIN_TO_DO 未读取",
                            detail: "没有找到 ADMIN_TO_DO.md。可以用 CNB_ADMIN_TODO_PATH 指定文件，或从仓库根目录启动。",
                            actionTitle: "重试",
                            systemImage: "doc.badge.clock",
                            tint: .orange,
                            action: viewModel.reload
                        )
                    }
                }
                .padding(16)
            }
        }
    }
}

private struct AdminTodoSectionCard: View {
    let section: CNBAdminTodoSection

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(section.heading)
                    .font(.headline.weight(.semibold))
                Spacer(minLength: 8)
                if section.isActionable {
                    Text("待处理")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.orange)
                }
            }

            ForEach(section.paragraphs, id: \.self) { paragraph in
                Text(paragraph)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }

            ForEach(section.bullets, id: \.self) { bullet in
                HStack(alignment: .top, spacing: 8) {
                    Circle()
                        .fill(Color.accentColor)
                        .frame(width: 5, height: 5)
                        .padding(.top, 7)
                    Text(bullet)
                        .font(.callout)
                        .textSelection(.enabled)
                }
            }

            ForEach(section.codeBlocks, id: \.self) { code in
                Text(code)
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
        }
        .padding(12)
        .cnbGlassCardBackground(cornerRadius: 8, tint: section.isActionable ? Color.orange.opacity(0.08) : Color.secondary.opacity(0.06))
    }
}

private struct StatusMessage: View {
    let text: String
    let systemImage: String
    let tint: Color

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: systemImage)
                .foregroundStyle(tint)
            Text(text)
                .lineLimit(2)
        }
        .font(.callout)
        .padding(12)
        .background(tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private extension View {
    @ViewBuilder
    func cnbGlassCardBackground(cornerRadius: CGFloat, tint: Color) -> some View {
        if #available(macOS 26.0, *) {
            background {
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .fill(.clear)
                    .glassEffect(.regular.tint(tint).interactive(), in: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
            }
        } else {
            background(.regularMaterial, in: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
        }
    }
}
