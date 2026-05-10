import Foundation

@MainActor
final class FeishuChatViewModel: ObservableObject {
    @Published var settings: FeishuChatSettings
    @Published var messages: [FeishuChatMessage]
    @Published var draft: String = ""
    @Published var statusMessage: String = ""
    @Published var isSending = false
    @Published var isRefreshing = false
    @Published var isLoadingOlder = false
    @Published var hasMoreHistory = false
    @Published var didLoadInitialHistory = false
    @Published var scrollRequest: FeishuScrollRequest?

    private let client = FeishuChatClient()
    private let welcomeMessageID = UUID()
    private let pageSize = 30
    private let maxUpdatePages = 8
    private var nextHistoryPageToken = ""
    private var autoSyncTimer: Timer?

    init() {
        let loaded = FeishuChatSettingsStore.load()
        settings = loaded
        messages = [
            FeishuChatMessage(
                id: welcomeMessageID,
                role: .assistant,
                text: L10n.string("feishu.chat.welcome")
            )
        ]
        statusMessage = loaded.isReady
            ? L10n.string("feishu.status.ready")
            : L10n.string("feishu.status.needs_settings")
    }

    deinit {
        autoSyncTimer?.invalidate()
    }

    var canSend: Bool {
        settings.isReady && !draft.trimmed.isEmpty && !isSending
    }

    func startAutoSync() {
        guard autoSyncTimer == nil else {
            return
        }

        if settings.isReady {
            Task { await syncLatestMessages(userInitiated: false) }
        }

        autoSyncTimer = Timer.scheduledTimer(withTimeInterval: 20, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.syncLatestMessages(userInitiated: false)
            }
        }
    }

    func saveSettings() {
        FeishuChatSettingsStore.save(settings)
        resetHistoryState()
        statusMessage = settings.isReady
            ? L10n.string("feishu.status.saved")
            : L10n.string("feishu.status.needs_settings")
        if settings.isReady {
            Task { await syncLatestMessages(userInitiated: true) }
        }
    }

    func reloadRuntimeSettings() {
        settings = FeishuChatSettingsStore.load()
        resetHistoryState()
        statusMessage = settings.isReady
            ? L10n.string("feishu.status.ready")
            : L10n.string("feishu.status.needs_settings")
        if settings.isReady {
            Task { await syncLatestMessages(userInitiated: true) }
        }
    }

    func sendDraft() async {
        let text = draft.trimmed
        guard settings.isReady else {
            statusMessage = L10n.string("feishu.status.needs_settings")
            return
        }
        guard !text.isEmpty else {
            return
        }

        draft = ""
        var outgoing = FeishuChatMessage(role: .user, text: text, deliveryState: .sending)
        messages.append(outgoing)
        isSending = true
        statusMessage = L10n.string("feishu.status.sending")

        do {
            let result = try await client.send(text: text, settings: settings)
            outgoing.deliveryState = .sent
            outgoing.remoteMessageID = result.messageID
            replaceMessage(outgoing)
            statusMessage = sentStatusText(result)
            if !result.bridgeDetail.isEmpty {
                messages.append(
                    FeishuChatMessage(
                        role: .system,
                        text: result.bridgeDetail,
                        deliveryState: .sent
                    )
                )
            }
        } catch {
            outgoing.deliveryState = .failed
            replaceMessage(outgoing)
            statusMessage = L10n.format("feishu.status.failed", error.localizedDescription)
            messages.append(
                FeishuChatMessage(
                    role: .system,
                    text: error.localizedDescription,
                    deliveryState: .failed
                )
            )
        }

        isSending = false
    }

    func refreshRecentMessages() async {
        await syncLatestMessages(userInitiated: true)
    }

    func loadOlderMessages() async {
        guard settings.isReady else {
            statusMessage = L10n.string("feishu.status.needs_settings")
            return
        }
        guard hasMoreHistory, !nextHistoryPageToken.trimmed.isEmpty, !isLoadingOlder else {
            return
        }

        let preserveID = firstHistoryMessageID
        isLoadingOlder = true
        statusMessage = L10n.string("feishu.history.loading")

        do {
            let page = try await client.fetchMessages(
                settings: settings,
                limit: pageSize,
                pageToken: nextHistoryPageToken
            )
            let summary = prependOlderMessages(page.messages)
            nextHistoryPageToken = page.nextPageToken
            hasMoreHistory = page.hasMore
            statusMessage = L10n.format("feishu.status.loaded_older", summary.inserted)
            if summary.inserted > 0, let preserveID {
                scrollRequest = FeishuScrollRequest(
                    messageID: preserveID,
                    anchor: .top,
                    animated: false
                )
            }
        } catch {
            statusMessage = L10n.format("feishu.status.failed", error.localizedDescription)
        }

        isLoadingOlder = false
    }

    private func syncLatestMessages(userInitiated: Bool) async {
        guard settings.isReady else {
            if userInitiated || !didLoadInitialHistory {
                statusMessage = L10n.string("feishu.status.needs_settings")
            }
            return
        }
        guard !isRefreshing else {
            return
        }

        isRefreshing = true
        let wasInitialLoad = !didLoadInitialHistory
        if userInitiated || wasInitialLoad {
            statusMessage = L10n.string("feishu.status.refreshing")
        }

        do {
            let page = try await fetchLatestUpdateWindow()
            let summary = mergeNewestMessages(page.messages)
            if wasInitialLoad {
                nextHistoryPageToken = page.nextPageToken
                hasMoreHistory = page.hasMore
                didLoadInitialHistory = true
            }
            if userInitiated || wasInitialLoad || summary.changedCount > 0 {
                statusMessage = L10n.format("feishu.status.synced", summary.changedCount)
            }
        } catch {
            if userInitiated || wasInitialLoad {
                statusMessage = L10n.format("feishu.status.failed", error.localizedDescription)
            }
        }

        isRefreshing = false
    }

    private func replaceMessage(_ message: FeishuChatMessage) {
        guard let index = messages.firstIndex(where: { $0.id == message.id }) else {
            return
        }
        messages[index] = message
    }

    private func sentStatusText(_ result: FeishuSendResult) -> String {
        if settings.canNotifyBridge {
            return L10n.format("feishu.status.sent_with_bridge", result.messageID.isEmpty ? "-" : result.messageID)
        }
        return L10n.format("feishu.status.sent", result.messageID.isEmpty ? "-" : result.messageID)
    }

    private func resetHistoryState() {
        messages = [
            FeishuChatMessage(
                id: welcomeMessageID,
                role: .assistant,
                text: L10n.string("feishu.chat.welcome")
            )
        ]
        nextHistoryPageToken = ""
        hasMoreHistory = false
        didLoadInitialHistory = false
        scrollRequest = nil
    }

    private var firstHistoryMessageID: UUID? {
        messages.first { !$0.remoteMessageID.isEmpty }?.id ?? messages.first?.id
    }

    private func fetchLatestUpdateWindow() async throws -> FeishuMessagePage {
        let firstPage = try await client.fetchMessages(settings: settings, limit: pageSize)
        let loadedRemoteIDs = Set(messages.map(\.remoteMessageID).filter { !$0.isEmpty })
        guard firstPage.hasMore, !firstPage.nextPageToken.trimmed.isEmpty, !loadedRemoteIDs.isEmpty else {
            return firstPage
        }

        var allMessages = firstPage.messages
        var fetchedRemoteIDs = Set(firstPage.messages.map(\.messageID))
        var nextPageToken = firstPage.nextPageToken
        var fetchedPageCount = 1
        let targetPageCount = min(
            maxUpdatePages,
            max(1, Int(ceil(Double(max(loadedRemoteIDs.count, pageSize)) / Double(pageSize))) + 1)
        )

        while fetchedPageCount < targetPageCount,
              !loadedRemoteIDs.isSubset(of: fetchedRemoteIDs),
              !nextPageToken.trimmed.isEmpty {
            let page = try await client.fetchMessages(
                settings: settings,
                limit: pageSize,
                pageToken: nextPageToken
            )
            allMessages.append(contentsOf: page.messages)
            fetchedRemoteIDs.formUnion(page.messages.map(\.messageID))
            fetchedPageCount += 1
            guard page.hasMore else {
                break
            }
            nextPageToken = page.nextPageToken
        }

        return FeishuMessagePage(
            messages: allMessages,
            nextPageToken: firstPage.nextPageToken,
            hasMore: firstPage.hasMore
        )
    }

    private func mergeNewestMessages(_ remote: [FeishuRemoteMessage]) -> FeishuMergeSummary {
        var summary = FeishuMergeSummary()
        var additions: [FeishuChatMessage] = []
        for item in remote.reversed() {
            if let index = messages.firstIndex(where: { $0.remoteMessageID == item.messageID }) {
                if applyRemoteMessage(item, to: &messages[index]) {
                    summary.updated += 1
                }
            } else {
                additions.append(chatMessage(from: item))
                summary.inserted += 1
            }
        }

        guard !additions.isEmpty else {
            return summary
        }
        removeWelcomeMessage()
        messages.append(contentsOf: additions)
        requestScrollToBottom(animated: true)
        return summary
    }

    private func prependOlderMessages(_ remote: [FeishuRemoteMessage]) -> FeishuMergeSummary {
        var summary = FeishuMergeSummary()
        var additions: [FeishuChatMessage] = []
        for item in remote.reversed() {
            if let index = messages.firstIndex(where: { $0.remoteMessageID == item.messageID }) {
                if applyRemoteMessage(item, to: &messages[index]) {
                    summary.updated += 1
                }
            } else {
                additions.append(chatMessage(from: item))
                summary.inserted += 1
            }
        }

        guard !additions.isEmpty else {
            return summary
        }
        removeWelcomeMessage()
        messages.insert(contentsOf: additions, at: 0)
        return summary
    }

    private func chatMessages(from remote: [FeishuRemoteMessage]) -> [FeishuChatMessage] {
        remote.reversed().map(chatMessage(from:))
    }

    private func chatMessage(from item: FeishuRemoteMessage) -> FeishuChatMessage {
        FeishuChatMessage(
            role: item.role,
            text: item.text,
            createdAt: item.createdAt,
            deliveryState: .sent,
            remoteMessageID: item.messageID,
            remoteUpdatedAt: item.updatedAt,
            senderLabel: item.senderLabel
        )
    }

    private func applyRemoteMessage(_ item: FeishuRemoteMessage, to message: inout FeishuChatMessage) -> Bool {
        let remoteIsNewer = message.remoteUpdatedAt.map { item.updatedAt > $0 } ?? true
        let contentChanged = message.text != item.text
            || message.role != item.role
            || message.senderLabel != item.senderLabel
            || message.deliveryState != .sent
        guard remoteIsNewer || contentChanged else {
            return false
        }

        message.role = item.role
        message.text = item.text
        message.createdAt = item.createdAt
        message.deliveryState = .sent
        message.remoteUpdatedAt = item.updatedAt
        message.senderLabel = item.senderLabel
        return true
    }

    private func removeWelcomeMessage() {
        messages.removeAll { $0.id == welcomeMessageID }
    }

    private func requestScrollToBottom(animated: Bool) {
        guard let id = messages.last?.id else {
            return
        }
        scrollRequest = FeishuScrollRequest(messageID: id, anchor: .bottom, animated: animated)
    }
}

private struct FeishuMergeSummary {
    var inserted = 0
    var updated = 0

    var changedCount: Int {
        inserted + updated
    }
}

private enum FeishuChatSettingsStore {
    private static let defaultsKey = "CNBMacCompanion.FeishuChatSettings"

    static func load() -> FeishuChatSettings {
        let stored = loadDefaults()
        guard let runtime = FeishuConfigReader.loadRuntimeSettings() else {
            return stored
        }
        return stored.mergingRuntime(runtime)
    }

    static func save(_ settings: FeishuChatSettings) {
        guard let data = try? JSONEncoder().encode(settings) else {
            return
        }
        UserDefaults.standard.set(data, forKey: defaultsKey)
    }

    private static func loadDefaults() -> FeishuChatSettings {
        guard let data = UserDefaults.standard.data(forKey: defaultsKey),
              let settings = try? JSONDecoder().decode(FeishuChatSettings.self, from: data) else {
            return FeishuChatSettings()
        }
        return settings
    }
}
