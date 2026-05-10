import SwiftUI

struct ContentView: View {
    @ObservedObject var viewModel: CNBLiveActivityViewModel
    @StateObject private var feishuViewModel = FeishuChatViewModel()
    @StateObject private var adminTodoViewModel = CNBAdminTodoViewModel()
    @State private var selectedTab: CNBIslandTab = .feishu

    var body: some View {
        ZStack {
            Color(.systemGroupedBackground)
                .ignoresSafeArea()

            TabView(selection: $selectedTab) {
                CNBDashboardView(
                    viewModel: viewModel,
                    feishuViewModel: feishuViewModel,
                    adminTodoViewModel: adminTodoViewModel
                ) {
                    selectedTab = .feishu
                }
                .tabItem {
                    Label("tab.dashboard", systemImage: "rectangle.grid.2x2")
                }
                .tag(CNBIslandTab.dashboard)

                FeishuChatView(viewModel: feishuViewModel)
                .tabItem {
                    Label("tab.chat", systemImage: "message")
                }
                .tag(CNBIslandTab.feishu)
            }
        }
        .onAppear {
            viewModel.reload()
            adminTodoViewModel.reload()
        }
        .task {
            await viewModel.autostartIfRequested()
        }
    }
}

private enum CNBIslandTab: Hashable {
    case dashboard
    case feishu
}

private struct CNBDashboardView: View {
    @ObservedObject var viewModel: CNBLiveActivityViewModel
    @ObservedObject var feishuViewModel: FeishuChatViewModel
    @ObservedObject var adminTodoViewModel: CNBAdminTodoViewModel
    @State private var isRunningDiagnostics = false
    @State private var diagnosticsTimedOut = false
    @State private var isShowingAdminTodo = false
    var openChat: () -> Void

    var body: some View {
        GeometryReader { proxy in
            let layout = DashboardLayout(size: proxy.size)
            ScrollView {
                VStack(spacing: layout.sectionSpacing) {
                    header(layout)
                    primaryStatusCard(layout)
                    adminTodoCard(layout)
                    actionGrid(layout)
                    diagnosticsCard(layout)
                    liveActivityControls(layout)
                }
                .padding(.horizontal, layout.horizontalPadding)
                .padding(.top, layout.topPadding)
                .padding(.bottom, layout.bottomPadding)
            }
            .scrollIndicators(.hidden)
            .background(Color(.systemGroupedBackground))
            .refreshable {
                runDiagnostics()
            }
        }
        .sheet(isPresented: $isShowingAdminTodo) {
            AdminTodoDetailView(viewModel: adminTodoViewModel)
        }
    }

    private var state: CNBLiveState {
        viewModel.state
    }

    private func header(_ layout: DashboardLayout) -> some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                Text("状态与诊断")
                    .font(layout.headerFont)
                    .lineLimit(1)
                Text(overallSubtitle)
                    .font(layout.captionFont)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)
            }

            Spacer()

            Button {
                runDiagnostics()
            } label: {
                Image(systemName: isRunningDiagnostics ? "waveform.path.ecg" : "stethoscope")
                    .font(layout.controlIconFont)
                    .frame(width: layout.iconButtonSize, height: layout.iconButtonSize)
                    .cnbGlassCardBackground(cornerRadius: 10, tint: Color.accentColor.opacity(0.1))
            }
            .buttonStyle(.plain)
            .disabled(isRunningDiagnostics)
            .accessibilityLabel(Text("运行诊断"))
        }
        .padding(.top, 4)
    }

    private func primaryStatusCard(_ layout: DashboardLayout) -> some View {
        VStack(alignment: .leading, spacing: layout.cardInnerSpacing) {
            HStack(alignment: .top, spacing: 12) {
                if isRunningDiagnostics {
                    ProgressView()
                        .frame(width: layout.statusGlyphSize, height: layout.statusGlyphSize)
                } else {
                    StatusGlyph(status: effectiveStatus, size: layout.statusGlyphSize)
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text(overallTitle)
                        .font(layout.statusTitleFont)
                        .lineLimit(2)
                        .minimumScaleFactor(0.82)
                        .fixedSize(horizontal: false, vertical: true)

                    Text(overallDetail)
                        .font(layout.bodyFont)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)
                }

                Spacer(minLength: 8)
            }

            HStack(spacing: 8) {
                StatusBadge(status: effectiveStatus)
                SyncFreshnessBadge(age: syncAge, isStale: syncIsStale)
                Spacer()
                if diagnosticsTimedOut {
                    Text("检查超时")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.red)
                } else {
                    Text(state.updatedAt, style: .time)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
        }
        .cardStyle(padding: layout.cardPadding)
    }

    private func adminTodoCard(_ layout: DashboardLayout) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(
                title: "ADMIN_TO_DO",
                detail: adminTodoViewModel.statusMessage,
                systemImage: adminTodoViewModel.hasActionableItems ? "list.bullet.clipboard.fill" : "checkmark.seal.fill",
                tint: adminTodoViewModel.hasActionableItems ? .orange : .green
            )

            if adminTodoViewModel.isLoaded {
                VStack(alignment: .leading, spacing: 8) {
                    Text(adminTodoViewModel.document.currentReleaseSummary)
                        .font(layout.bodyFont)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)

                    ForEach(adminTodoViewModel.document.actionableSections.prefix(2)) { section in
                        AdminTodoInlineRow(section: section) {
                            isShowingAdminTodo = true
                        }
                    }

                    if !adminTodoViewModel.hasActionableItems {
                        Text("当前没有需要管理员凭证处理的事项。")
                            .font(layout.bodyFont)
                            .foregroundStyle(.secondary)
                    }
                }
            } else {
                DiagnosticIssueRow(
                    title: "待办未同步",
                    detail: "请用运行脚本把根目录 ADMIN_TO_DO.md 同步到手机。状态页会自动读取这个文件。",
                    actionTitle: "重试",
                    systemImage: "doc.badge.clock",
                    tint: .orange,
                    action: runDiagnostics
                )
            }

            Button {
                isShowingAdminTodo = true
            } label: {
                Label("查看全部维护待办", systemImage: "chevron.right.circle.fill")
                    .font(.subheadline.weight(.semibold))
                    .frame(maxWidth: .infinity, minHeight: 42)
            }
            .cnbGlassControlButton()
        }
        .cardStyle(padding: layout.cardPadding)
    }

    private func actionGrid(_ layout: DashboardLayout) -> some View {
        LazyVGrid(columns: layout.metricColumns, spacing: layout.gridSpacing) {
            StatusActionTile(
                title: "项目",
                value: projectValue,
                detail: projectDetail,
                actionTitle: "查看待办",
                systemImage: "folder.badge.gearshape",
                tint: adminTodoViewModel.hasActionableItems ? .orange : .blue,
                layout: layout,
                action: { isShowingAdminTodo = true }
            )
            StatusActionTile(
                title: "设备",
                value: deviceValue,
                detail: state.machineName,
                actionTitle: "更新锁屏",
                systemImage: "iphone.gen3.radiowaves.left.and.right",
                tint: .purple,
                layout: layout
            ) {
                Task { await viewModel.updateActivity() }
            }
            StatusActionTile(
                title: "连接",
                value: feishuViewModel.settings.isReady
                    ? "飞书已就绪"
                    : "等待同步",
                detail: connectionDetail,
                actionTitle: feishuViewModel.settings.isReady ? "打开对话" : "重试同步",
                systemImage: "link",
                tint: feishuViewModel.settings.isReady ? .green : .orange,
                layout: layout,
                action: feishuViewModel.settings.isReady ? openChat : runDiagnostics
            )
            StatusActionTile(
                title: "同步",
                value: syncIsStale
                    ? "已过期"
                    : "正常",
                detail: syncDetail,
                actionTitle: "诊断",
                systemImage: "arrow.triangle.2.circlepath",
                tint: syncIsStale ? .red : .teal,
                layout: layout,
                action: runDiagnostics
            )
        }
    }

    private func diagnosticsCard(_ layout: DashboardLayout) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(
                title: "诊断",
                detail: issueCount == 0 ? "没有发现阻塞项" : "有需要处理的状态",
                systemImage: issueCount == 0 ? "checkmark.seal.fill" : "exclamationmark.triangle.fill",
                tint: issueCount == 0 ? .green : .orange
            )

            if diagnosticsTimedOut {
                DiagnosticIssueRow(
                    title: "检查超时",
                    detail: "同步文件或连接状态没有及时返回。先保持 Mac companion 和手机连接，再重试。",
                    actionTitle: "重试同步",
                    systemImage: "timer",
                    tint: .red,
                    action: runDiagnostics
                )
            }

            if syncIsStale {
                DiagnosticIssueRow(
                    title: "状态同步过旧",
                    detail: "手机里的状态文件已经超过 3 分钟未更新，可能是 Mac 没有重新导出或设备桥接没有复制成功。",
                    actionTitle: "重试同步",
                    systemImage: "clock.badge.exclamationmark",
                    tint: .red,
                    action: runDiagnostics
                )
            }

            if !feishuViewModel.settings.isReady {
                DiagnosticIssueRow(
                    title: "飞书连接未同步",
                    detail: "手机端没有完整的 appID、appSecret、chatID。请让 Mac 重新生成并复制 feishu_chat.json。",
                    actionTitle: "重试同步",
                    systemImage: "macbook.and.iphone",
                    tint: .orange,
                    action: runDiagnostics
                )
            }

            if let failure = readableFeishuFailure {
                DiagnosticIssueRow(
                    title: "连接失败",
                    detailText: failure,
                    actionTitle: "打开对话",
                    systemImage: "network.slash",
                    tint: .red,
                    action: openChat
                )
            }

            if state.pendingActions > 0 {
                DiagnosticIssueRow(
                    title: "项目有待确认动作",
                    detail: "有项目状态需要人工确认，先进入对话页发指令给值班通道。",
                    actionTitle: "打开对话",
                    systemImage: "person.crop.circle.badge.exclamationmark",
                    tint: .orange,
                    action: openChat
                )
            }

            if let message = viewModel.message, message.localizedCaseInsensitiveContains("failed") || message.contains("失败") {
                DiagnosticIssueRow(
                    title: "实时活动更新失败",
                    detailText: message,
                    actionTitle: "更新锁屏",
                    systemImage: "platter.filled.bottom.iphone",
                    tint: .red
                ) {
                    Task { await viewModel.updateActivity() }
                }
            }

            if issueCount == 0 {
                DiagnosticIssueRow(
                    title: "状态正常",
                    detail: "状态文件、待办文件和飞书配置都可读取。需要新状态时可以重新诊断。",
                    actionTitle: "重新检查",
                    systemImage: "checkmark.circle.fill",
                    tint: .green,
                    action: runDiagnostics
                )
            }
        }
        .cardStyle(padding: layout.cardPadding)
    }

    private func liveActivityControls(_ layout: DashboardLayout) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(
                title: "实时活动",
                detail: "更新锁屏和灵动岛显示。",
                systemImage: "platter.filled.bottom.iphone",
                tint: .blue
            )

            if let message = viewModel.message {
                StatusMessage(text: message)
            }

            LazyVGrid(columns: layout.controlColumns, spacing: layout.gridSpacing) {
                ControlButton(title: "action.reload", systemImage: "arrow.clockwise") {
                    viewModel.reload()
                }
                ControlButton(title: "action.start", systemImage: "play.fill") {
                    Task { await viewModel.startActivity() }
                }
                ControlButton(title: "action.update", systemImage: "arrow.triangle.2.circlepath") {
                    Task { await viewModel.updateActivity() }
                }
                ControlButton(title: "action.end", systemImage: "stop.fill", role: .destructive) {
                    Task { await viewModel.endActivity() }
                }
            }
        }
        .cardStyle(padding: layout.cardPadding)
    }

    private var effectiveStatus: CNBActivityStatus {
        if diagnosticsTimedOut || syncIsStale {
            return .blocked
        }
        if adminTodoViewModel.hasActionableItems || state.pendingActions > 0 {
            return .attention
        }
        if isRunningDiagnostics {
            return .updating
        }
        return state.status
    }

    private var syncAge: TimeInterval {
        max(0, Date().timeIntervalSince(state.updatedAt))
    }

    private var syncIsStale: Bool {
        syncAge > 180
    }

    private var issueCount: Int {
        var count = 0
        if diagnosticsTimedOut { count += 1 }
        if syncIsStale { count += 1 }
        if !adminTodoViewModel.isLoaded { count += 1 }
        if !feishuViewModel.settings.isReady { count += 1 }
        if readableFeishuFailure != nil { count += 1 }
        if state.pendingActions > 0 { count += 1 }
        if let message = viewModel.message, message.localizedCaseInsensitiveContains("failed") || message.contains("失败") {
            count += 1
        }
        return count
    }

    private var overallTitle: String {
        if diagnosticsTimedOut {
            return "诊断超时"
        }
        if syncIsStale {
            return "状态同步过旧"
        }
        if adminTodoViewModel.hasActionableItems {
            return "有维护待办"
        }
        if state.pendingActions > 0 {
            return "项目需要处理"
        }
        if isRunningDiagnostics {
            return "正在检查"
        }
        switch state.status {
        case .quiet:
            return "当前正常"
        case .working:
            return "项目运行中"
        case .attention:
            return "项目需要处理"
        case .blocked:
            return "存在阻塞"
        case .shuttingDown:
            return "正在收尾"
        case .updating:
            return "正在检查"
        }
    }

    private var overallSubtitle: String {
        issueCount == 0 ? "总览正常，状态页用于诊断" : "有可操作事项，点卡片处理"
    }

    private var overallDetail: String {
        if diagnosticsTimedOut {
            return "检查超过 8 秒没有完成。可能是同步文件没有复制、服务没有启动，或网络请求卡住。"
        }
        if syncIsStale {
            return "手机读取到的是旧状态。请让 Mac companion 重新导出并通过脚本复制到手机。"
        }
        if let primary = adminTodoViewModel.primaryAction {
            return "\(primary.heading)：\(primary.summary)"
        }
        if isRunningDiagnostics {
            return "正在重新读取本地状态、飞书配置和 ADMIN_TO_DO。"
        }
        return state.localizedDetail
    }

    private var projectValue: String {
        if adminTodoViewModel.hasActionableItems {
            return "有待办"
        }
        if state.pendingActions > 0 {
            return "需确认"
        }
        return "正常"
    }

    private var projectDetail: String {
        if let primary = adminTodoViewModel.primaryAction {
            return primary.heading
        }
        if state.pendingActions > 0 {
            return "项目有待确认动作，进入对话页处理。"
        }
        return "查看 ADMIN_TO_DO 和当前发布状态。"
    }

    private var deviceValue: String {
        state.machineName.isEmpty ? "未知" : "已连接"
    }

    private var connectionDetail: String {
        feishuViewModel.settings.isReady
            ? "使用 Mac 同步的飞书配置，可直接发送消息。"
            : "等待 Mac 复制 feishu_chat.json 后才能发送。"
    }

    private var syncDetail: String {
        let minutes = max(0, Int(syncAge / 60))
        if minutes == 0 {
            return "刚刚同步"
        }
        return "\(minutes) 分钟前同步"
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
            return "网络不可达。请确认手机联网，并且 Mac bridge 的公网回调地址可访问。"
        }
        if lower.contains("http 401") || lower.contains("http 403") {
            return "飞书权限或凭证失败。请检查 appSecret、机器人入群状态和消息权限。"
        }
        return text
    }

    private func runDiagnostics() {
        guard !isRunningDiagnostics else {
            return
        }
        isRunningDiagnostics = true
        diagnosticsTimedOut = false

        Task { @MainActor in
            Task { @MainActor in
                try? await Task.sleep(for: .seconds(8))
                if isRunningDiagnostics {
                    diagnosticsTimedOut = true
                    isRunningDiagnostics = false
                }
            }

            viewModel.reload()
            feishuViewModel.reloadRuntimeSettings()
            adminTodoViewModel.reload()
            try? await Task.sleep(for: .milliseconds(350))

            if isRunningDiagnostics {
                isRunningDiagnostics = false
            }
        }
    }
}

private struct DashboardLayout {
    var size: CGSize

    private var compactHeight: Bool {
        size.height < 720
    }

    private var narrowWidth: Bool {
        size.width < 380
    }

    var horizontalPadding: CGFloat {
        narrowWidth ? 12 : 16
    }

    var topPadding: CGFloat {
        compactHeight ? 8 : 14
    }

    var bottomPadding: CGFloat {
        compactHeight ? 88 : 104
    }

    var sectionSpacing: CGFloat {
        compactHeight ? 10 : 12
    }

    var gridSpacing: CGFloat {
        compactHeight ? 8 : 10
    }

    var cardPadding: CGFloat {
        compactHeight ? 10 : 12
    }

    var cardInnerSpacing: CGFloat {
        compactHeight ? 10 : 12
    }

    var iconButtonSize: CGFloat {
        compactHeight ? 34 : 38
    }

    var statusGlyphSize: CGFloat {
        compactHeight ? 38 : 44
    }

    var metricColumns: [GridItem] {
        [
            GridItem(.flexible(minimum: 132), spacing: gridSpacing),
            GridItem(.flexible(minimum: 132), spacing: gridSpacing)
        ]
    }

    var controlColumns: [GridItem] {
        size.width < 360
            ? [GridItem(.flexible(), spacing: gridSpacing)]
            : metricColumns
    }

    var headerFont: Font {
        compactHeight ? .headline.weight(.semibold) : .title3.weight(.semibold)
    }

    var statusTitleFont: Font {
        compactHeight ? .subheadline.weight(.semibold) : .headline.weight(.semibold)
    }

    var sectionTitleFont: Font {
        compactHeight ? .subheadline.weight(.semibold) : .headline
    }

    var bodyFont: Font {
        compactHeight ? .caption : .callout
    }

    var captionFont: Font {
        compactHeight ? .caption2 : .caption
    }

    var controlIconFont: Font {
        compactHeight ? .caption.weight(.semibold) : .subheadline.weight(.semibold)
    }
}

private struct StatusActionTile: View {
    var title: String
    var value: String
    var detail: String
    var actionTitle: String
    var systemImage: String
    var tint: Color
    var layout: DashboardLayout
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: systemImage)
                        .font(layout.sectionTitleFont)
                        .foregroundStyle(tint)
                    Text(title)
                        .font(layout.captionFont.weight(.semibold))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                    Spacer(minLength: 0)
                }

                Text(value)
                    .font(.headline.weight(.semibold))
                    .foregroundStyle(.primary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)

                Text(detail)
                    .font(layout.captionFont)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)

                HStack(spacing: 4) {
                    Text(actionTitle)
                        .font(.caption.weight(.semibold))
                    Image(systemName: "chevron.right")
                        .font(.caption2.weight(.bold))
                }
                .foregroundStyle(tint)
            }
            .frame(maxWidth: .infinity, minHeight: 118, alignment: .leading)
            .padding(layout.cardPadding)
            .cnbGlassCardBackground(cornerRadius: 8, tint: tint.opacity(0.08))
            .contentShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
    }
}

private struct SectionHeader: View {
    var title: String
    var detail: String
    var systemImage: String
    var tint: Color

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

private struct DiagnosticIssueRow: View {
    var title: String
    var detail: String
    var actionTitle: String
    var systemImage: String
    var tint: Color
    var action: () -> Void

    init(
        title: String,
        detail: String,
        actionTitle: String,
        systemImage: String,
        tint: Color,
        action: @escaping () -> Void
    ) {
        self.title = title
        self.detail = detail
        self.actionTitle = actionTitle
        self.systemImage = systemImage
        self.tint = tint
        self.action = action
    }

    init(
        title: String,
        detailText: String,
        actionTitle: String,
        systemImage: String,
        tint: Color,
        action: @escaping () -> Void
    ) {
        self.init(
            title: title,
            detail: detailText,
            actionTitle: actionTitle,
            systemImage: systemImage,
            tint: tint,
            action: action
        )
    }

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
            .background(tint.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
            .contentShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
    }
}

private struct SyncFreshnessBadge: View {
    var age: TimeInterval
    var isStale: Bool

    var body: some View {
        Text(label)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(tint.opacity(0.12), in: Capsule())
            .foregroundStyle(tint)
    }

    private var label: String {
        if isStale {
            return "同步过旧"
        }
        let minutes = Int(age / 60)
        return minutes == 0 ? "刚刚同步" : "\(minutes) 分钟前"
    }

    private var tint: Color {
        isStale ? .red : .teal
    }
}

private struct AdminTodoInlineRow: View {
    var section: CNBAdminTodoSection
    var action: () -> Void

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
            .background(Color.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
            .contentShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
    }
}

private struct AdminTodoDetailView: View {
    @ObservedObject var viewModel: CNBAdminTodoViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    SectionHeader(
                        title: viewModel.document.title,
                        detail: viewModel.statusMessage,
                        systemImage: "list.bullet.clipboard",
                        tint: viewModel.hasActionableItems ? .orange : .green
                    )
                    .padding(12)
                    .cnbGlassCardBackground(cornerRadius: 8, tint: Color.accentColor.opacity(0.08))

                    if viewModel.isLoaded {
                        ForEach(viewModel.document.sections) { section in
                            AdminTodoSectionCard(section: section)
                        }
                    } else {
                        DiagnosticIssueRow(
                            title: "ADMIN_TO_DO 未同步",
                            detail: "运行 iPhone 脚本后会把根目录 ADMIN_TO_DO.md 复制到 app Documents。",
                            actionTitle: "重试",
                            systemImage: "doc.badge.clock",
                            tint: .orange
                        ) {
                            viewModel.reload()
                        }
                    }
                }
                .padding(16)
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("维护待办")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        viewModel.reload()
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .accessibilityLabel(Text("重新载入"))
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("完成") {
                        dismiss()
                    }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

private struct AdminTodoSectionCard: View {
    var section: CNBAdminTodoSection

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(section.heading)
                    .font(.headline.weight(.semibold))
                    .foregroundStyle(.primary)
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
                        .foregroundStyle(.primary)
                        .textSelection(.enabled)
                }
            }

            ForEach(section.codeBlocks, id: \.self) { code in
                Text(code)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(.primary)
                    .textSelection(.enabled)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(.tertiarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding(12)
        .cnbGlassCardBackground(
            cornerRadius: 8,
            tint: section.isActionable ? Color.orange.opacity(0.08) : Color(.secondarySystemGroupedBackground).opacity(0.16)
        )
    }
}

private struct ControlButton: View {
    var title: LocalizedStringKey
    var systemImage: String
    var role: ButtonRole?
    var action: () -> Void

    init(
        title: LocalizedStringKey,
        systemImage: String,
        role: ButtonRole? = nil,
        action: @escaping () -> Void
    ) {
        self.title = title
        self.systemImage = systemImage
        self.role = role
        self.action = action
    }

    var body: some View {
        Button(role: role, action: action) {
            Label {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)
            } icon: {
                Image(systemName: systemImage)
                    .font(.subheadline.weight(.semibold))
            }
            .frame(maxWidth: .infinity, minHeight: 42)
        }
        .cnbGlassControlButton()
    }
}

private struct StatusGlyph: View {
    var status: CNBActivityStatus
    var size: CGFloat

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 8)
                .fill(status.tint.opacity(0.14))
            Image(systemName: status.symbolName)
                .font(.title3.weight(.semibold))
                .foregroundStyle(status.tint)
        }
        .frame(width: size, height: size)
    }
}

private struct StatusBadge: View {
    var status: CNBActivityStatus

    var body: some View {
        Label {
            Text(status.title)
                .font(.caption.weight(.semibold))
        } icon: {
            Circle()
                .fill(status.tint)
                .frame(width: 7, height: 7)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(status.tint.opacity(0.12), in: Capsule())
        .foregroundStyle(status.tint)
    }
}

private struct StatusMessage: View {
    var text: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "info.circle")
                .foregroundStyle(.secondary)
            Text(text)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(Color(.tertiarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 8))
    }
}

private extension View {
    @ViewBuilder
    func cardStyle(padding: CGFloat = 12) -> some View {
        self
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .cnbGlassCardBackground(cornerRadius: 8, tint: Color(.secondarySystemGroupedBackground).opacity(0.16))
    }

    @ViewBuilder
    func cnbGlassCardBackground(cornerRadius: CGFloat, tint: Color) -> some View {
        if #available(iOS 26.0, *) {
            self
                .background {
                    RoundedRectangle(cornerRadius: cornerRadius)
                        .fill(.clear)
                        .glassEffect(.regular.tint(tint).interactive(), in: RoundedRectangle(cornerRadius: cornerRadius))
                }
        } else {
            self
                .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: cornerRadius))
        }
    }

    @ViewBuilder
    func cnbGlassControlButton() -> some View {
        if #available(iOS 26.0, *) {
            self.buttonStyle(.glass)
        } else {
            self.buttonStyle(.bordered)
        }
    }
}

private extension CNBActivityStatus {
    var title: LocalizedStringKey {
        switch self {
        case .quiet:
            "status.quiet"
        case .working:
            "status.working"
        case .attention:
            "status.attention"
        case .blocked:
            "status.blocked"
        case .shuttingDown:
            "status.shuttingDown"
        case .updating:
            "status.updating"
        }
    }

    var tint: Color {
        switch self {
        case .quiet:
            .green
        case .working:
            .blue
        case .attention:
            .orange
        case .blocked:
            .red
        case .shuttingDown:
            .purple
        case .updating:
            .teal
        }
    }

    var symbolName: String {
        switch self {
        case .quiet:
            "checkmark.circle.fill"
        case .working:
            "bolt.circle.fill"
        case .attention:
            "exclamationmark.circle.fill"
        case .blocked:
            "xmark.octagon.fill"
        case .shuttingDown:
            "moon.circle.fill"
        case .updating:
            "arrow.triangle.2.circlepath.circle.fill"
        }
    }
}
