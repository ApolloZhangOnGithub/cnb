import Foundation
import os

private let logger = Logger(subsystem: "dev.cnb.CNBVision", category: "feishu")

enum FeishuLocalChatKind: String, Codable, Hashable, CaseIterable, Sendable {
    case group
    case privateChat

    var title: String {
        switch self {
        case .group:
            "群聊"
        case .privateChat:
            "私聊"
        }
    }
}

struct FeishuLocalChatPreferences: Codable, Equatable, Sendable {
    var chatKinds: [String: FeishuLocalChatKind] = [:]
    var mutedChatIDs: Set<String> = []
    var pinnedChatIDs: Set<String> = []
    var collapsedChatKinds: Set<FeishuLocalChatKind> = []
    var lastSeenAt: [String: TimeInterval] = [:]
    var userAuthState = FeishuUserAuthState()
    var globalNotificationsEnabled = true

    private static let storageKey = "dev.cnb.vision.feishu.localChatPreferences.v1"

    static func load() -> FeishuLocalChatPreferences {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let decoded = try? JSONDecoder().decode(FeishuLocalChatPreferences.self, from: data) else {
            return FeishuLocalChatPreferences()
        }
        return decoded
    }

    func save() {
        guard let data = try? JSONEncoder().encode(self) else {
            return
        }
        UserDefaults.standard.set(data, forKey: Self.storageKey)
    }
}

@MainActor
final class VisionFeishuMessagesViewModel: ObservableObject {
    @Published private(set) var settings = FeishuChatSettings()
    @Published private(set) var messages: [FeishuRemoteMessage] = []
    @Published private(set) var chats: [FeishuChatInfo] = []
    @Published private(set) var localPreferences = FeishuLocalChatPreferences.load()
    @Published private(set) var statusMessage = ""
    @Published private(set) var lastRefresh: Date?
    @Published var isRefreshing = false
    @Published var isSending = false
    @Published var isAuthorizing = false
    @Published var deviceAuthorization: FeishuDeviceAuthorization?
    @Published var selectedChatID = ""
    @Published var draft = ""
    @Published var attachedImageData: Data?

    private let client = FeishuChatClient()

    init() {
        reloadSettings()
    }

    var isReady: Bool {
        settings.isReady
    }

    var chatIDText: String {
        let values = settings.allChatIDs
        return values.isEmpty ? "未配置 chat_id" : values.joined(separator: "\n")
    }

    var chatIDs: [String] {
        settings.allChatIDs
    }

    var groupChatIDs: [String] {
        sortedChatIDs(chatIDs.filter { chatKind(for: $0) == .group })
    }

    var privateChatIDs: [String] {
        sortedChatIDs(chatIDs.filter { chatKind(for: $0) == .privateChat })
    }

    var contactChatIDs: [String] {
        privateChatIDs
    }

    var contactGroupIDs: [String] {
        groupChatIDs
    }

    var configuredChatCount: Int {
        settings.allChatIDs.count
    }

    var visibleMessages: [FeishuRemoteMessage] {
        messages.filter { $0.chatID == selectedChatID }
    }

    var canSend: Bool {
        canSubmitDraft && isUserAuthorized && !isSending
    }

    var canSubmitDraft: Bool {
        isReady && !selectedChatID.trimmed.isEmpty && (!draft.trimmed.isEmpty || attachedImageData != nil) && !isSending
    }

    var isUserAuthorized: Bool {
        effectiveUserAccessToken.isEmpty == false
    }

    var effectiveUserAccessToken: String {
        if !localPreferences.userAuthState.isUsable {
            return settings.userAccessToken.trimmed
        }
        return localPreferences.userAuthState.accessToken.trimmed
    }

    var selectedChatTitle: String {
        chatTitle(selectedChatID)
    }

    var selectedChatKind: FeishuLocalChatKind {
        chatKind(for: selectedChatID)
    }

    var totalUnreadCount: Int {
        chatIDs.reduce(0) { total, chatID in
            guard !isMuted(chatID) else {
                return total
            }
            return total + unreadCount(for: chatID)
        }
    }

    var globalNotificationsEnabled: Bool {
        localPreferences.globalNotificationsEnabled
    }

    var readableChatIDs: [String] {
        let readable = chats.filter(\.isReadable).map(\.chatID)
        return readable.isEmpty ? settings.allChatIDs : readable
    }

    func reloadSettings() {
        guard let data = CNBRuntimeFileLocator.optionalData(named: "feishu_chat.json") else {
            settings = FeishuChatSettings()
            statusMessage = "没有找到 feishu_chat.json"
            return
        }

        do {
            let decoded = try JSONDecoder().decode(FeishuChatSettings.self, from: data)
            settings = decoded
            reconcileChatSelection()
            statusMessage = decoded.isReady ? "" : "飞书配置缺少 appID/appSecret/chatID"
        } catch {
            settings = FeishuChatSettings()
            selectedChatID = ""
            statusMessage = "无法读取 feishu_chat.json：\(error.localizedDescription)"
        }
    }

    func selectChat(_ chatID: String) {
        selectedChatID = chatID
        markChatSeen(chatID)
    }

    func refreshMessages() async {
        reloadSettings()
        guard settings.isReady else {
            return
        }

        isRefreshing = true
        defer {
            isRefreshing = false
        }

        let chatIDs = settings.allChatIDs
        var fetchedChats: [FeishuChatInfo] = []
        var fetchedMessages: [FeishuRemoteMessage] = []
        var failedChats: [String] = []
        for chatID in chatIDs {
            var chatInfo = (try? await client.fetchChatInfo(settings: settings.withChatID(chatID))) ?? FeishuChatInfo(
                chatID: chatID,
                name: "",
                chatMode: "",
                chatStatus: "",
                messageError: "",
                isReadable: true
            )
            do {
                let fetched = try await client.fetchRecentMessages(settings: settings.withChatID(chatID), limit: 36)
                chatInfo.isReadable = true
                fetchedMessages.append(contentsOf: fetched)
            } catch {
                chatInfo.isReadable = false
                chatInfo.messageError = error.localizedDescription
                failedChats.append(chatID)
            }
            fetchedChats.append(chatInfo)
        }

        chats = fetchedChats
        messages = deduped(fetchedMessages).sorted { $0.createdAt < $1.createdAt }
        if !selectedChatID.trimmed.isEmpty {
            markChatSeen(selectedChatID)
        }
        lastRefresh = Date()
        if failedChats.isEmpty {
            statusMessage = ""
        } else if messages.isEmpty {
            statusMessage = "\(failedChats.count) 个控制群读取失败"
        } else {
            statusMessage = "\(failedChats.count) 个控制群读取失败"
        }
    }

    func sendDraft() async {
        let text = draft.trimmed
        let imageData = attachedImageData
        let targetChatID = selectedChatID.trimmed
        guard !targetChatID.isEmpty, (!text.isEmpty || imageData != nil) else {
            return
        }
        let sendSettings = settingsWithUserAuth()
        let tokenSnippet = String(sendSettings.userAccessToken.trimmed.prefix(8))
        logger.info("sendDraft: chat=\(targetChatID.prefix(12)) token=\(tokenSnippet)... text=\(!text.isEmpty) image=\(imageData != nil)")
        guard !sendSettings.userAccessToken.trimmed.isEmpty else {
            statusMessage = "缺少用户授权，不能以用户身份发送"
            return
        }

        draft = ""
        attachedImageData = nil
        isSending = true
        statusMessage = ""
        defer {
            isSending = false
        }

        do {
            if !text.isEmpty {
                let result = try await client.sendAsUser(text: text, settings: sendSettings.withChatID(targetChatID))
                logger.info("sendDraft: text sent OK messageID=\(result.messageID.prefix(12))")
                messages.append(FeishuRemoteMessage(
                    messageID: result.messageID.isEmpty ? UUID().uuidString : result.messageID,
                    text: text,
                    senderLabel: sendSettings.userName.trimmed.isEmpty ? "Me" : sendSettings.userName,
                    createdAt: Date(),
                    updatedAt: Date(),
                    role: .user,
                    chatID: targetChatID
                ))
            }
            if let imageData {
                let imageKey = try await client.uploadImage(data: imageData, settings: sendSettings)
                let result = try await client.sendImageAsUser(imageKey: imageKey, settings: sendSettings.withChatID(targetChatID))
                messages.append(FeishuRemoteMessage(
                    messageID: result.messageID.isEmpty ? UUID().uuidString : result.messageID,
                    text: "[图片]",
                    senderLabel: sendSettings.userName.trimmed.isEmpty ? "Me" : sendSettings.userName,
                    createdAt: Date(),
                    updatedAt: Date(),
                    role: .user,
                    chatID: targetChatID
                ))
            }
            messages = deduped(messages).sorted { $0.createdAt < $1.createdAt }
            lastRefresh = Date()
            statusMessage = ""
            await refreshMessages()
        } catch {
            if !text.isEmpty { draft = text }
            if imageData != nil { attachedImageData = imageData }
            // 权限不足（230027）：清除 token，下次发送会触发重新授权
            if error.localizedDescription.contains("230027") || error.localizedDescription.contains("send_as_user") {
                localPreferences.userAuthState = FeishuUserAuthState()
                saveLocalPreferences()
            }
            logger.error("sendDraft FAILED: \(error)")
            let fullError = "sendDraft FAILED [\(Date())] chat=\(targetChatID) text=\(!text.isEmpty) image=\(imageData != nil) error=\(error.localizedDescription)"
            if let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
                try? fullError.write(to: docs.appendingPathComponent("send-error.log"), atomically: true, encoding: .utf8)
            }
        }
    }

    func startUserAuthorization() async {
        guard settings.isReady, !isAuthorizing else {
            return
        }
        isAuthorizing = true
        statusMessage = ""
        defer {
            isAuthorizing = false
        }
        do {
            let authorization = try await client.startUserDeviceAuthorization(settings: settings)
            deviceAuthorization = authorization
            let token = try await client.pollUserDeviceToken(deviceCode: authorization.deviceCode, settings: settings, interval: authorization.interval, expiresIn: authorization.expiresIn)
            localPreferences.userAuthState = token
            saveLocalPreferences()
            deviceAuthorization = nil
            statusMessage = ""
        } catch {
            logger.error("auth FAILED: \(error)")
            statusMessage = "飞书授权失败：\(error.localizedDescription)"
        }
    }

    func shortChatLabel(_ chatID: String) -> String {
        chatID.shortChatID
    }

    func chatTitle(_ chatID: String) -> String {
        chats.first { $0.chatID == chatID }?.displayName ?? shortChatLabel(chatID)
    }

    func chatDetail(_ chatID: String) -> String {
        guard let chat = chats.first(where: { $0.chatID == chatID }) else {
            return "加载中"
        }
        if !chat.isReadable {
            let error = chat.messageError.replacingOccurrences(of: "HTTP 400: ", with: "")
            return "不可读 · \(error)"
        }
        guard let latest = messages.last(where: { $0.chatID == chatID }) else {
            return "暂无消息"
        }
        return latest.text
            .replacingOccurrences(of: "\n", with: " ")
            .trimmed
    }

    func chatKind(for chatID: String) -> FeishuLocalChatKind {
        let id = chatID.trimmed
        if let local = localPreferences.chatKinds[id] {
            return local
        }
        if chats.first(where: { $0.chatID == id })?.chatMode == "p2p" {
            return .privateChat
        }
        return .group
    }

    func setChatKind(_ kind: FeishuLocalChatKind, for chatID: String) {
        let id = chatID.trimmed
        guard !id.isEmpty else {
            return
        }
        localPreferences.chatKinds[id] = kind
        saveLocalPreferences()
    }

    func moveChats(_ chatIDs: [String], to kind: FeishuLocalChatKind) {
        for chatID in chatIDs {
            setChatKind(kind, for: chatID)
        }
    }

    func isCollapsed(_ kind: FeishuLocalChatKind) -> Bool {
        localPreferences.collapsedChatKinds.contains(kind)
    }

    func toggleCollapsed(_ kind: FeishuLocalChatKind) {
        if localPreferences.collapsedChatKinds.contains(kind) {
            localPreferences.collapsedChatKinds.remove(kind)
        } else {
            localPreferences.collapsedChatKinds.insert(kind)
        }
        saveLocalPreferences()
    }

    func unreadCount(for kind: FeishuLocalChatKind) -> Int {
        chatIDs
            .filter { chatKind(for: $0) == kind }
            .reduce(0) { total, chatID in
                guard !isMuted(chatID) else {
                    return total
                }
                return total + unreadCount(for: chatID)
            }
    }

    func unreadCount(for chatID: String) -> Int {
        let id = chatID.trimmed
        let seenAt = Date(timeIntervalSince1970: localPreferences.lastSeenAt[id] ?? 0)
        return messages.filter { $0.chatID == id && $0.createdAt > seenAt }.count
    }

    func isMuted(_ chatID: String) -> Bool {
        localPreferences.mutedChatIDs.contains(chatID.trimmed)
    }

    func setMuted(_ muted: Bool, for chatID: String) {
        updateSet(\.mutedChatIDs, contains: chatID.trimmed, enabled: muted)
    }

    func isPinned(_ chatID: String) -> Bool {
        localPreferences.pinnedChatIDs.contains(chatID.trimmed)
    }

    func setPinned(_ pinned: Bool, for chatID: String) {
        updateSet(\.pinnedChatIDs, contains: chatID.trimmed, enabled: pinned)
    }

    func setGlobalNotificationsEnabled(_ enabled: Bool) {
        localPreferences.globalNotificationsEnabled = enabled
        saveLocalPreferences()
    }

    func markSelectedChatSeen() {
        markChatSeen(selectedChatID)
    }

    func markChatSeen(_ chatID: String) {
        let id = chatID.trimmed
        guard !id.isEmpty else {
            return
        }
        let latest = messages
            .filter { $0.chatID == id }
            .map(\.createdAt)
            .max() ?? Date()
        localPreferences.lastSeenAt[id] = max(localPreferences.lastSeenAt[id] ?? 0, latest.timeIntervalSince1970)
        saveLocalPreferences()
    }

    func selectMostRecentUnreadChat() {
        guard let message = messages
            .filter({ unreadCount(for: $0.chatID) > 0 && !isMuted($0.chatID) })
            .max(by: { $0.createdAt < $1.createdAt }) else {
            return
        }
        selectChat(message.chatID)
    }

    func runAutoRefreshLoop() async {
        await refreshMessages()
        while !Task.isCancelled {
            try? await Task.sleep(nanoseconds: 12_000_000_000)
            await refreshMessages()
        }
    }

    private func reconcileChatSelection() {
        let ids = settings.allChatIDs
        if selectedChatID.trimmed.isEmpty || !ids.contains(selectedChatID.trimmed) {
            selectedChatID = ids.first ?? ""
        }
    }

    private func deduped(_ messages: [FeishuRemoteMessage]) -> [FeishuRemoteMessage] {
        var seen = Set<String>()
        return messages.filter { seen.insert($0.sourceKey).inserted }
    }

    private func settingsWithUserAuth() -> FeishuChatSettings {
        let token = effectiveUserAccessToken
        guard !token.isEmpty else {
            return settings
        }
        return FeishuChatSettings(
            appID: settings.appID,
            appSecret: settings.appSecret,
            chatID: settings.chatID,
            chatIDs: settings.chatIDs,
            botName: settings.botName,
            userAccessToken: token,
            userName: localPreferences.userAuthState.userName.trimmed.isEmpty ? settings.userName : localPreferences.userAuthState.userName,
            replyMessageID: settings.replyMessageID,
            webhookURL: settings.webhookURL,
            verificationToken: settings.verificationToken
        )
    }

    private func sortedChatIDs(_ ids: [String]) -> [String] {
        ids.sorted { lhs, rhs in
            let lhsPinned = isPinned(lhs)
            let rhsPinned = isPinned(rhs)
            if lhsPinned != rhsPinned {
                return lhsPinned
            }
            let lhsLast = messages.last(where: { $0.chatID == lhs })?.createdAt ?? .distantPast
            let rhsLast = messages.last(where: { $0.chatID == rhs })?.createdAt ?? .distantPast
            if lhsLast != rhsLast {
                return lhsLast > rhsLast
            }
            return chatTitle(lhs).localizedStandardCompare(chatTitle(rhs)) == .orderedAscending
        }
    }

    private func updateSet(
        _ keyPath: WritableKeyPath<FeishuLocalChatPreferences, Set<String>>,
        contains chatID: String,
        enabled: Bool
    ) {
        guard !chatID.isEmpty else {
            return
        }
        if enabled {
            localPreferences[keyPath: keyPath].insert(chatID)
        } else {
            localPreferences[keyPath: keyPath].remove(chatID)
        }
        saveLocalPreferences()
    }

    private func saveLocalPreferences() {
        localPreferences.save()
    }
}
