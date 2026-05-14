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

struct FeishuWatchSettings: Equatable, Sendable {
    var configURL: URL
    var host: String
    var port: Int
    var token: String
    var projectRoot: String

    init(
        configURL: URL = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".cnb/config.toml"),
        host: String = "127.0.0.1",
        port: Int = 8765,
        token: String = "",
        projectRoot: String = ""
    ) {
        self.configURL = configURL
        self.host = host
        self.port = max(1, min(port, 65535))
        self.token = token
        self.projectRoot = projectRoot
    }

    var bindHost: String {
        host.trimmed.isEmpty ? "127.0.0.1" : host.trimmed
    }

    var displayHost: String {
        switch bindHost {
        case "0.0.0.0", "::", "":
            return "127.0.0.1"
        default:
            return bindHost
        }
    }

    func localURL(port overridePort: Int? = nil, embedded: Bool = false) -> URL {
        var components = URLComponents()
        components.scheme = "http"
        components.host = displayHost
        components.port = overridePort ?? port
        var queryItems: [URLQueryItem] = []
        if !token.trimmed.isEmpty {
            queryItems.append(URLQueryItem(name: "token", value: token.trimmed))
        }
        if embedded {
            queryItems.append(URLQueryItem(name: "embed", value: "1"))
        }
        components.queryItems = queryItems.isEmpty ? nil : queryItems
        return components.url ?? URL(string: "http://127.0.0.1:\(overridePort ?? port)")!
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

struct FeishuMessagePage: Hashable, Sendable {
    var messages: [FeishuRemoteMessage]
    var nextPageToken: String
    var hasMore: Bool
}

enum FeishuScrollAnchor: Hashable, Sendable {
    case top
    case bottom
}

struct FeishuScrollRequest: Identifiable, Hashable, Sendable {
    var id = UUID()
    var messageID: UUID
    var anchor: FeishuScrollAnchor
    var animated: Bool
}

extension String {
    var trimmed: String {
        trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
