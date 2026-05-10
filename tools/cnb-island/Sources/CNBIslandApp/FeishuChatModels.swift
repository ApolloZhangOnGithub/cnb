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
    var chatIDs: [String]
    var botName: String
    var userAccessToken: String
    var userName: String
    var replyMessageID: String
    var webhookURL: String
    var verificationToken: String

    init(
        appID: String = "",
        appSecret: String = "",
        chatID: String = "",
        chatIDs: [String] = [],
        botName: String = "",
        userAccessToken: String = "",
        userName: String = "",
        replyMessageID: String = "",
        webhookURL: String = "",
        verificationToken: String = ""
    ) {
        self.appID = appID
        self.appSecret = appSecret
        self.chatID = chatID
        self.chatIDs = chatIDs
        self.botName = botName
        self.userAccessToken = userAccessToken
        self.userName = userName
        self.replyMessageID = replyMessageID
        self.webhookURL = webhookURL
        self.verificationToken = verificationToken
    }

    var isReady: Bool {
        !appID.trimmed.isEmpty && !appSecret.trimmed.isEmpty && !allChatIDs.isEmpty
    }

    var primaryChatID: String {
        allChatIDs.first ?? ""
    }

    var allChatIDs: [String] {
        var seen = Set<String>()
        return ([chatID] + chatIDs).compactMap { value in
            let trimmed = value.trimmed
            guard !trimmed.isEmpty, seen.insert(trimmed).inserted else {
                return nil
            }
            return trimmed
        }
    }

    var canNotifyBridge: Bool {
        !webhookURL.trimmed.isEmpty
    }

    func withChatID(_ chatID: String) -> FeishuChatSettings {
        FeishuChatSettings(
            appID: appID,
            appSecret: appSecret,
            chatID: chatID,
            chatIDs: chatIDs,
            botName: botName,
            userAccessToken: userAccessToken,
            userName: userName,
            replyMessageID: replyMessageID,
            webhookURL: webhookURL,
            verificationToken: verificationToken
        )
    }

    func mergingRuntime(_ runtime: FeishuChatSettings) -> FeishuChatSettings {
        FeishuChatSettings(
            appID: runtime.appID.trimmed.isEmpty ? appID : runtime.appID,
            appSecret: runtime.appSecret.trimmed.isEmpty ? appSecret : runtime.appSecret,
            chatID: runtime.chatID.trimmed.isEmpty ? chatID : runtime.chatID,
            chatIDs: runtime.allChatIDs.isEmpty ? chatIDs : runtime.allChatIDs,
            botName: runtime.botName.trimmed.isEmpty ? botName : runtime.botName,
            userAccessToken: runtime.userAccessToken.trimmed.isEmpty ? userAccessToken : runtime.userAccessToken,
            userName: runtime.userName.trimmed.isEmpty ? userName : runtime.userName,
            replyMessageID: runtime.replyMessageID.trimmed.isEmpty ? replyMessageID : runtime.replyMessageID,
            webhookURL: runtime.webhookURL.trimmed.isEmpty ? webhookURL : runtime.webhookURL,
            verificationToken: runtime.verificationToken.trimmed.isEmpty ? verificationToken : runtime.verificationToken
        )
    }

    enum CodingKeys: String, CodingKey {
        case appID
        case appSecret
        case chatID
        case chatIDs
        case botName
        case userAccessToken
        case userName
        case replyMessageID
        case webhookURL
        case verificationToken
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        appID = try container.decodeIfPresent(String.self, forKey: .appID) ?? ""
        appSecret = try container.decodeIfPresent(String.self, forKey: .appSecret) ?? ""
        chatID = try container.decodeIfPresent(String.self, forKey: .chatID) ?? ""
        chatIDs = try container.decodeIfPresent([String].self, forKey: .chatIDs) ?? []
        botName = try container.decodeIfPresent(String.self, forKey: .botName) ?? ""
        userAccessToken = try container.decodeIfPresent(String.self, forKey: .userAccessToken) ?? ""
        userName = try container.decodeIfPresent(String.self, forKey: .userName) ?? ""
        replyMessageID = try container.decodeIfPresent(String.self, forKey: .replyMessageID) ?? ""
        webhookURL = try container.decodeIfPresent(String.self, forKey: .webhookURL) ?? ""
        verificationToken = try container.decodeIfPresent(String.self, forKey: .verificationToken) ?? ""
    }
}

struct FeishuSendResult: Hashable, Sendable {
    var messageID: String
    var bridgeDetail: String
}

struct FeishuUserAuthState: Codable, Equatable, Sendable {
    var accessToken: String = ""
    var refreshToken: String = ""
    var expiresAt: TimeInterval = 0
    var refreshExpiresAt: TimeInterval = 0
    var userName: String = ""

    var isUsable: Bool {
        !accessToken.trimmed.isEmpty && Date().timeIntervalSince1970 < expiresAt - 60
    }
}

struct FeishuDeviceAuthorization: Hashable, Sendable {
    var deviceCode: String
    var userCode: String
    var verificationURL: String
    var verificationURLComplete: String
    var expiresIn: Int
    var interval: Int
}

struct FeishuRemoteMessage: Hashable, Sendable {
    var messageID: String
    var text: String
    var senderLabel: String
    var createdAt: Date
    var updatedAt: Date
    var role: FeishuChatRole
    var chatID: String = ""

    var sourceKey: String {
        chatID.trimmed.isEmpty ? messageID : "\(chatID)::\(messageID)"
    }
}

struct FeishuChatInfo: Hashable, Sendable {
    var chatID: String
    var name: String
    var chatMode: String
    var chatStatus: String
    var messageError: String
    var isReadable: Bool

    var displayName: String {
        if !name.trimmed.isEmpty {
            return name
        }
        if chatMode == "p2p" {
            return "私聊 \(chatID.shortChatID)"
        }
        return chatID.shortChatID
    }
}

extension String {
    var trimmed: String {
        trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var shortChatID: String {
        let value = trimmed
        guard value.count > 12 else {
            return value.isEmpty ? "-" : value
        }
        return "\(value.prefix(6))...\(value.suffix(4))"
    }
}
