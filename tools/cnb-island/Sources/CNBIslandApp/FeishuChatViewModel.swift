import Foundation

@MainActor
final class FeishuChatViewModel: ObservableObject {
    @Published var settings: FeishuChatSettings
    @Published var messages: [FeishuChatMessage]
    @Published var draft: String = ""
    @Published var statusMessage: String = ""
    @Published var isSending = false
    @Published var isRefreshing = false

    private let client = FeishuChatClient()
    private let welcomeMessageID = UUID()
    private var autoSyncTimer: Timer?

    init() {
        let loaded = FeishuChatSettingsStore.load()
        settings = loaded
        messages = [
            FeishuChatMessage(
                id: welcomeMessageID,
                role: .assistant,
                text: NSLocalizedString("feishu.chat.welcome", comment: "")
            )
        ]
        statusMessage = statusText(for: loaded)
    }

    var canSend: Bool {
        settings.isReady && !draft.trimmed.isEmpty && !isSending
    }

    func startAutoSync() {
        guard autoSyncTimer == nil else {
            return
        }

        if reloadRuntimeSettings(showStatus: false) {
            Task { await refreshRecentMessages(showStatus: false) }
        }
        autoSyncTimer = Timer.scheduledTimer(withTimeInterval: 20, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard self?.reloadRuntimeSettings(showStatus: false) == true else {
                    return
                }
                await self?.refreshRecentMessages(showStatus: false)
            }
        }
    }

    func stopAutoSync() {
        autoSyncTimer?.invalidate()
        autoSyncTimer = nil
    }

    func saveSettings() {
        FeishuChatSettingsStore.save(settings)
        statusMessage = statusText(for: settings)
        if settings.isReady {
            Task { await refreshRecentMessages(showStatus: true) }
        }
    }

    @discardableResult
    func reloadRuntimeSettings(showStatus: Bool = true) -> Bool {
        let loaded = FeishuChatSettingsStore.load()
        let changed = loaded != settings
        settings = loaded
        if showStatus || changed {
            statusMessage = statusText(for: loaded)
        }
        return loaded.isReady
    }

    func sendDraft() async {
        let text = draft.trimmed
        guard reloadRuntimeSettings(showStatus: true) else {
            return
        }
        guard !text.isEmpty else {
            return
        }

        draft = ""
        var outgoing = FeishuChatMessage(role: .user, text: text, deliveryState: .sending)
        messages.append(outgoing)
        isSending = true
        statusMessage = NSLocalizedString("feishu.status.sending", comment: "")

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
            let format = NSLocalizedString("feishu.status.failedFormat", comment: "")
            statusMessage = String(format: format, locale: Locale.current, error.localizedDescription)
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
        await refreshRecentMessages(showStatus: true)
    }

    private func refreshRecentMessages(showStatus: Bool) async {
        guard reloadRuntimeSettings(showStatus: showStatus) else {
            return
        }
        guard !isRefreshing else {
            return
        }
        isRefreshing = true
        if showStatus {
            statusMessage = NSLocalizedString("feishu.status.refreshing", comment: "")
        }
        do {
            let remote = try await client.fetchRecentMessages(settings: settings)
            let summary = mergeRemoteMessages(remote)
            if showStatus || summary.changedCount > 0 {
                let format = NSLocalizedString("feishu.status.refreshedFormat", comment: "")
                statusMessage = String(format: format, locale: Locale.current, summary.changedCount)
            }
        } catch {
            let format = NSLocalizedString("feishu.status.failedFormat", comment: "")
            if showStatus {
                statusMessage = String(format: format, locale: Locale.current, error.localizedDescription)
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
            let format = NSLocalizedString("feishu.status.sentWithBridgeFormat", comment: "")
            return String(
                format: format,
                locale: Locale.current,
                result.messageID.isEmpty ? "-" : result.messageID
            )
        }
        let format = NSLocalizedString("feishu.status.sentFormat", comment: "")
        return String(format: format, locale: Locale.current, result.messageID.isEmpty ? "-" : result.messageID)
    }

    private func statusText(for settings: FeishuChatSettings) -> String {
        settings.isReady
            ? NSLocalizedString("feishu.status.ready", comment: "")
            : NSLocalizedString("feishu.status.needsSettings", comment: "")
    }

    private func mergeRemoteMessages(_ remote: [FeishuRemoteMessage]) -> FeishuMergeSummary {
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
        messages.removeAll { $0.id == welcomeMessageID }
        messages.append(contentsOf: additions)
        return summary
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
}

private struct FeishuMergeSummary {
    var inserted = 0
    var updated = 0

    var changedCount: Int {
        inserted + updated
    }
}

private enum FeishuChatSettingsStore {
    private static let defaultsKey = "CNBIsland.FeishuChatSettings"

    static func load() -> FeishuChatSettings {
        let stored = loadDefaults()
        guard let runtime = loadRuntimeConfig() else {
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

    private static func loadRuntimeConfig() -> FeishuChatSettings? {
        guard let data = CNBRuntimeFileLocator.optionalData(named: "feishu_chat.json") else {
            return nil
        }
        return try? JSONDecoder().decode(FeishuChatSettings.self, from: data)
    }
}
