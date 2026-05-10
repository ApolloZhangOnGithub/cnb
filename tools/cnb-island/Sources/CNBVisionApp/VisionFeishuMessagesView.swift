import PhotosUI
import SwiftUI

private enum VisionFeishuSidebarMode: String, Hashable {
    case messages = "消息"
    case contacts = "通讯录"
}

struct VisionFeishuMessagesView: View {
    @StateObject private var viewModel = VisionFeishuMessagesViewModel()
    @State private var showingChatSettings = false
    @State private var showingLogin = false
    @State private var sidebarMode: VisionFeishuSidebarMode = .messages
    @State private var selectedPhoto: PhotosPickerItem?

    var body: some View {
        NavigationSplitView {
            sidebar
                .navigationTitle("CNB Vision")
        } detail: {
            transcript
                .navigationTitle(viewModel.selectedChatTitle)
        }
        .task {
            await viewModel.runAutoRefreshLoop()
        }
        .sheet(isPresented: $showingChatSettings) {
            VisionFeishuChatSettingsSheet(viewModel: viewModel)
        }
        .sheet(isPresented: $showingLogin) {
            VisionFeishuLoginSheet(viewModel: viewModel)
        }
        .onChange(of: selectedPhoto) { _, newItem in
            guard let newItem else { return }
            Task {
                if let data = try? await newItem.loadTransferable(type: Data.self) {
                    viewModel.attachedImageData = data
                }
                selectedPhoto = nil
            }
        }
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 10) {
            if !viewModel.statusMessage.isEmpty {
                Text(viewModel.statusMessage)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Picker("侧边栏", selection: $sidebarMode) {
                Text("消息").tag(VisionFeishuSidebarMode.messages)
                Text("通讯录").tag(VisionFeishuSidebarMode.contacts)
            }
            .pickerStyle(.segmented)

            if sidebarMode == .messages {
                messagesList
            } else {
                contactsList
            }

            Spacer()
        }
        .padding(14)
    }

    private var transcript: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 14) {
                        if viewModel.visibleMessages.isEmpty {
                            emptyState
                        } else {
                            ForEach(viewModel.visibleMessages, id: \.sourceKey) { message in
                                VisionFeishuMessageRow(message: message)
                                    .id(message.sourceKey)
                            }
                        }
                    }
                    .padding(28)
                }
                .background(.black.opacity(0.04))
                .onChange(of: viewModel.visibleMessages.count) { _, _ in
                    guard let last = viewModel.visibleMessages.last?.sourceKey else {
                        return
                    }
                    withAnimation(.easeOut(duration: 0.2)) {
                        proxy.scrollTo(last, anchor: .bottom)
                    }
                }
            }
            Divider()
            composer
        }
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                if viewModel.globalNotificationsEnabled, viewModel.totalUnreadCount > 0 {
                    Button {
                        viewModel.selectMostRecentUnreadChat()
                    } label: {
                        Label("\(viewModel.totalUnreadCount)", systemImage: "bell.badge.fill")
                    }
                    .help("未读消息")
                }

                Button {
                    showingChatSettings = true
                } label: {
                    Image(systemName: "gearshape")
                }
                .help("群聊设置")
            }
        }
    }

    private var messagesList: some View {
        List {
            chatSection(title: "群聊", systemImage: "person.3", chatIDs: viewModel.groupChatIDs, kind: .group)
            chatSection(title: "私聊", systemImage: "person.crop.circle", chatIDs: viewModel.privateChatIDs, kind: .privateChat)
        }
        .listStyle(.sidebar)
        .frame(minHeight: 420)
    }

    private func chatSection(title: String, systemImage: String, chatIDs: [String], kind: FeishuLocalChatKind) -> some View {
        Section {
            if !viewModel.isCollapsed(kind) {
                if chatIDs.isEmpty {
                    Text("拖到这里")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, minHeight: 34, alignment: .leading)
                } else {
                    ForEach(chatIDs, id: \.self) { chatID in
                        chatRow(chatID)
                    }
                }
            }
        } header: {
            Button {
                viewModel.toggleCollapsed(kind)
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: viewModel.isCollapsed(kind) ? "chevron.right" : "chevron.down")
                        .font(.caption.weight(.semibold))
                        .frame(width: 12)
                    Label(title, systemImage: systemImage)
                        .font(.headline)
                    Text("\(chatIDs.count)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    let unread = viewModel.unreadCount(for: kind)
                    if unread > 0 {
                        unreadBadge(unread)
                    }
                }
            }
            .buttonStyle(.plain)
        }
    }

    private var contactsList: some View {
        List {
            contactSection(title: "联系人", systemImage: "person.crop.circle", chatIDs: viewModel.contactChatIDs)
            contactSection(title: "群组", systemImage: "person.3", chatIDs: viewModel.contactGroupIDs)
        }
        .listStyle(.sidebar)
        .frame(minHeight: 420)
    }

    private func contactSection(title: String, systemImage: String, chatIDs: [String]) -> some View {
        Section {
            if chatIDs.isEmpty {
                Text("暂无")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 34, alignment: .leading)
            } else {
                ForEach(chatIDs, id: \.self) { chatID in
                    contactRow(chatID)
                }
            }
        } header: {
            Label("\(title) \(chatIDs.count)", systemImage: systemImage)
                .font(.headline)
        }
    }

    private func contactRow(_ chatID: String) -> some View {
        Button {
            sidebarMode = .messages
            viewModel.selectChat(chatID)
        } label: {
            HStack(spacing: 10) {
                Image(systemName: viewModel.chatKind(for: chatID) == .privateChat ? "person.crop.circle" : "person.3")
                    .foregroundStyle(.secondary)
                    .frame(width: 18)
                Text(viewModel.chatTitle(chatID))
                    .font(.footnote.weight(.medium))
                    .lineLimit(1)
                Spacer(minLength: 8)
                let unread = viewModel.unreadCount(for: chatID)
                if unread > 0 {
                    unreadBadge(unread)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .buttonStyle(.plain)
        .swipeActions(edge: .leading, allowsFullSwipe: false) {
            Button {
                sidebarMode = .messages
                viewModel.selectChat(chatID)
            } label: {
                Label("打开", systemImage: "message")
            }
            .tint(.blue)

            Button {
                viewModel.markChatSeen(chatID)
            } label: {
                Label("已读", systemImage: "checkmark.circle")
            }
            .tint(.green)
        }
        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
            Button {
                viewModel.setPinned(!viewModel.isPinned(chatID), for: chatID)
            } label: {
                Label(viewModel.isPinned(chatID) ? "取消置顶" : "置顶", systemImage: "pin")
            }
            .tint(.yellow)
        }
        .help(chatID)
    }

    private func chatRow(_ chatID: String) -> some View {
        Button {
            viewModel.selectChat(chatID)
        } label: {
            HStack(spacing: 8) {
                Image(systemName: viewModel.selectedChatID == chatID ? "checkmark.circle.fill" : "message")
                    .foregroundStyle(.secondary)
                    .frame(width: 16)

                VStack(alignment: .leading, spacing: 3) {
                    Text(viewModel.chatTitle(chatID))
                        .font(.footnote.weight(.medium))
                        .lineLimit(1)
                    Text(viewModel.chatDetail(chatID))
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }

                Spacer(minLength: 8)

                if viewModel.isMuted(chatID) {
                    Image(systemName: "bell.slash")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if viewModel.isPinned(chatID) {
                    Image(systemName: "pin.fill")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                let unread = viewModel.unreadCount(for: chatID)
                if unread > 0 {
                    unreadBadge(unread)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .buttonStyle(.plain)
        .swipeActions(edge: .leading, allowsFullSwipe: false) {
            Button {
                viewModel.markChatSeen(chatID)
            } label: {
                Label("已读", systemImage: "checkmark.circle")
            }
            .tint(.green)

            Button {
                viewModel.setChatKind(viewModel.chatKind(for: chatID) == .group ? .privateChat : .group, for: chatID)
            } label: {
                Label(viewModel.chatKind(for: chatID) == .group ? "私聊" : "群聊", systemImage: "arrow.left.arrow.right")
            }
            .tint(.blue)
        }
        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
            Button {
                viewModel.setPinned(!viewModel.isPinned(chatID), for: chatID)
            } label: {
                Label(viewModel.isPinned(chatID) ? "取消置顶" : "置顶", systemImage: "pin")
            }
            .tint(.yellow)

            Button {
                viewModel.setMuted(!viewModel.isMuted(chatID), for: chatID)
            } label: {
                Label(viewModel.isMuted(chatID) ? "取消静音" : "静音", systemImage: viewModel.isMuted(chatID) ? "bell" : "bell.slash")
            }
            .tint(.orange)
        }
        .contextMenu {
            Button(viewModel.isPinned(chatID) ? "取消置顶" : "置顶") {
                viewModel.setPinned(!viewModel.isPinned(chatID), for: chatID)
            }
            Button(viewModel.isMuted(chatID) ? "取消静音" : "静音") {
                viewModel.setMuted(!viewModel.isMuted(chatID), for: chatID)
            }
        }
        .help(chatID)
    }

    private func unreadBadge(_ count: Int) -> some View {
        Text(count > 99 ? "99+" : "\(count)")
            .font(.caption2.weight(.bold))
            .foregroundStyle(.white)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(.red, in: Capsule())
    }

    private var composer: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let imageData = viewModel.attachedImageData {
                attachmentPreview(imageData)
            }
            HStack(alignment: .bottom, spacing: 12) {
                TextField("输入消息", text: $viewModel.draft, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(1...4)
                    .onSubmit {
                        Task { await viewModel.sendDraft() }
                    }

                PhotosPicker(selection: $selectedPhoto, matching: .images) {
                    Image(systemName: "paperclip")
                }
                .buttonStyle(.bordered)

                Button {
                    if viewModel.isUserAuthorized {
                        Task { await viewModel.sendDraft() }
                    } else {
                        showingLogin = true
                    }
                } label: {
                    Text(viewModel.isUserAuthorized ? "发送" : "登录")
                }
                .buttonStyle(.borderedProminent)
                .disabled(!viewModel.canSubmitDraft && viewModel.isUserAuthorized)
            }
        }
        .padding(18)
        .background(.regularMaterial)
    }

    private func attachmentPreview(_ imageData: Data) -> some View {
        HStack(spacing: 8) {
            if let uiImage = UIImage(data: imageData) {
                Image(uiImage: uiImage)
                    .resizable()
                    .scaledToFit()
                    .frame(maxHeight: 120)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            Button {
                viewModel.attachedImageData = nil
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
            Spacer()
        }
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 14) {
            Image(systemName: "message.badge")
                .font(.system(size: 42))
                .foregroundStyle(.secondary)
            Text(viewModel.isReady ? "还没有读取到消息" : "先同步飞书配置")
                .font(.title2.weight(.semibold))
            Text(viewModel.isReady ? "左侧选择一个群聊；消息会自动更新。" : "在 Mac 上导出 feishu_chat.json，并用运行脚本复制到 AVP app 容器。")
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .visionPanel()
    }
}

private struct VisionFeishuLoginSheet: View {
    @ObservedObject var viewModel: VisionFeishuMessagesViewModel
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                if viewModel.isUserAuthorized {
                    Label("已完成飞书用户授权", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                } else if let authorization = viewModel.deviceAuthorization {
                    Text("打开飞书授权页，输入验证码。")
                        .foregroundStyle(.secondary)
                    Text(authorization.userCode)
                        .font(.system(size: 34, weight: .bold, design: .monospaced))
                        .textSelection(.enabled)
                    Button {
                        if let url = URL(string: authorization.verificationURLComplete) {
                            openURL(url)
                        }
                    } label: {
                        Label("打开飞书授权", systemImage: "safari")
                    }
                    .buttonStyle(.borderedProminent)
                    ProgressView("等待授权")
                } else {
                    Text("发送消息需要飞书用户授权。授权完成后，AVP 直接连接飞书 OpenAPI 发送。")
                        .foregroundStyle(.secondary)
                    Button {
                        Task { await viewModel.startUserAuthorization() }
                    } label: {
                        Label("开始授权", systemImage: "person.crop.circle.badge.checkmark")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(viewModel.isAuthorizing)
                }
            }
            .padding(24)
            .navigationTitle("飞书登录")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") {
                        dismiss()
                    }
                }
            }
            .frame(minWidth: 460, minHeight: 320)
            .onChange(of: viewModel.isUserAuthorized) { _, authorized in
                if authorized {
                    dismiss()
                }
            }
        }
    }
}

private struct VisionFeishuChatSettingsSheet: View {
    @ObservedObject var viewModel: VisionFeishuMessagesViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section(viewModel.selectedChatTitle) {
                    Toggle("置顶", isOn: pinnedBinding)
                    Toggle("静音", isOn: mutedBinding)

                    Button("标为已读") {
                        viewModel.markSelectedChatSeen()
                    }
                }

                Section("全局") {
                    Toggle("未读提醒", isOn: notificationsBinding)
                    HStack {
                        Text("未读")
                        Spacer()
                        Text("\(viewModel.totalUnreadCount)")
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("群聊设置")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") {
                        dismiss()
                    }
                }
            }
            .frame(minWidth: 460, minHeight: 360)
        }
    }

    private var mutedBinding: Binding<Bool> {
        Binding {
            viewModel.isMuted(viewModel.selectedChatID)
        } set: { muted in
            viewModel.setMuted(muted, for: viewModel.selectedChatID)
        }
    }

    private var pinnedBinding: Binding<Bool> {
        Binding {
            viewModel.isPinned(viewModel.selectedChatID)
        } set: { pinned in
            viewModel.setPinned(pinned, for: viewModel.selectedChatID)
        }
    }

    private var notificationsBinding: Binding<Bool> {
        Binding {
            viewModel.globalNotificationsEnabled
        } set: { enabled in
            viewModel.setGlobalNotificationsEnabled(enabled)
        }
    }
}

private struct VisionFeishuMessageRow: View {
    let message: FeishuRemoteMessage

    var body: some View {
        HStack(alignment: .bottom) {
            if message.role == .user {
                Spacer(minLength: 120)
            }

            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 7) {
                HStack(spacing: 8) {
                    Text(message.senderLabel)
                        .font(.caption.weight(.semibold))
                    Text(message.createdAt.formatted(date: .omitted, time: .shortened))
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }

                Text(message.text)
                    .font(.body)
                    .foregroundStyle(message.role == .user ? .white : .primary)
                    .textSelection(.enabled)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(bubbleBackground, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            .frame(maxWidth: 720, alignment: message.role == .user ? .trailing : .leading)

            if message.role != .user {
                Spacer(minLength: 120)
            }
        }
    }

    private var bubbleBackground: Color {
        switch message.role {
        case .user:
            .blue
        case .assistant:
            .gray.opacity(0.18)
        case .system:
            .orange.opacity(0.18)
        }
    }

}

private extension View {
    func visionPanel() -> some View {
        padding(18)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
    }
}
