import Foundation

enum FeishuChatRole: String, Codable, Hashable, Sendable {
    case user
    case assistant
    case system
}

enum FeishuDeliveryState: String, Codable, Hashable, Sendable {
    case local
    case sending
    case sent
    case failed
}

struct FeishuChatMessage: Identifiable, Codable, Hashable, Sendable {
    var id: UUID
    var role: FeishuChatRole
    var text: String
    var createdAt: Date
    var deliveryState: FeishuDeliveryState
    var remoteMessageID: String
    var remoteUpdatedAt: Date?
    var senderLabel: String

    init(
        id: UUID = UUID(),
        role: FeishuChatRole,
        text: String,
        createdAt: Date = Date(),
        deliveryState: FeishuDeliveryState = .local,
        remoteMessageID: String = "",
        remoteUpdatedAt: Date? = nil,
        senderLabel: String = ""
    ) {
        self.id = id
        self.role = role
        self.text = text
        self.createdAt = createdAt
        self.deliveryState = deliveryState
        self.remoteMessageID = remoteMessageID
        self.remoteUpdatedAt = remoteUpdatedAt
        self.senderLabel = senderLabel
    }
}

struct FeishuChatSettings: Codable, Equatable, Sendable {
    var appID: String
    var appSecret: String
    var chatID: String
    var replyMessageID: String
    var webhookURL: String
    var verificationToken: String

    init(
        appID: String = "",
        appSecret: String = "",
        chatID: String = "",
        replyMessageID: String = "",
        webhookURL: String = "",
        verificationToken: String = ""
    ) {
        self.appID = appID
        self.appSecret = appSecret
        self.chatID = chatID
        self.replyMessageID = replyMessageID
        self.webhookURL = webhookURL
        self.verificationToken = verificationToken
    }

    var isReady: Bool {
        !appID.trimmed.isEmpty && !appSecret.trimmed.isEmpty && !chatID.trimmed.isEmpty
    }

    var canNotifyBridge: Bool {
        !webhookURL.trimmed.isEmpty
    }

    func mergingRuntime(_ runtime: FeishuChatSettings) -> FeishuChatSettings {
        FeishuChatSettings(
            appID: runtime.appID.trimmed.isEmpty ? appID : runtime.appID,
            appSecret: runtime.appSecret.trimmed.isEmpty ? appSecret : runtime.appSecret,
            chatID: runtime.chatID.trimmed.isEmpty ? chatID : runtime.chatID,
            replyMessageID: runtime.replyMessageID.trimmed.isEmpty ? replyMessageID : runtime.replyMessageID,
            webhookURL: runtime.webhookURL.trimmed.isEmpty ? webhookURL : runtime.webhookURL,
            verificationToken: runtime.verificationToken.trimmed.isEmpty ? verificationToken : runtime.verificationToken
        )
    }
}

struct FeishuSendResult: Hashable, Sendable {
    var messageID: String
    var bridgeDetail: String
}

struct FeishuRemoteMessage: Hashable, Sendable {
    var messageID: String
    var text: String
    var senderLabel: String
    var createdAt: Date
    var updatedAt: Date
    var role: FeishuChatRole
}

extension String {
    var trimmed: String {
        trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
