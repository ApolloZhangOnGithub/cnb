import Foundation

struct FeishuChatClient {
    private let baseURL = URL(string: "https://open.feishu.cn")!

    func send(text: String, settings: FeishuChatSettings) async throws -> FeishuSendResult {
        let token = try await tenantAccessToken(settings: settings)
        let content = try jsonString(["text": text])
        let replyID = settings.replyMessageID.trimmed

        let request: URLRequest
        if replyID.isEmpty {
            request = try openAPIRequest(
                path: "/open-apis/im/v1/messages",
                queryItems: [URLQueryItem(name: "receive_id_type", value: "chat_id")],
                token: token,
                body: [
                    "receive_id": settings.chatID.trimmed,
                    "msg_type": "text",
                    "content": content,
                ]
            )
        } else {
            request = try openAPIRequest(
                path: "/open-apis/im/v1/messages/\(replyID.urlPathEncoded)/reply",
                token: token,
                body: [
                    "msg_type": "text",
                    "content": content,
                ]
            )
        }

        let response = try await perform(request, as: FeishuMessageResponse.self)
        try response.validate()
        let messageID = response.data?.messageID ?? ""
        let bridgeDetail = await notifyBridgeIfConfigured(text: text, messageID: messageID, settings: settings)
        return FeishuSendResult(messageID: messageID, bridgeDetail: bridgeDetail)
    }

    func fetchRecentMessages(settings: FeishuChatSettings, limit: Int = 20) async throws -> [FeishuRemoteMessage] {
        let token = try await tenantAccessToken(settings: settings)
        let request = try openAPIRequest(
            method: "GET",
            path: "/open-apis/im/v1/messages",
            queryItems: [
                URLQueryItem(name: "container_id_type", value: "chat"),
                URLQueryItem(name: "container_id", value: settings.chatID.trimmed),
                URLQueryItem(name: "sort_type", value: "ByCreateTimeDesc"),
                URLQueryItem(name: "page_size", value: String(max(1, min(limit, 50)))),
            ],
            token: token,
            body: nil
        )
        let response = try await perform(request, as: FeishuMessagesResponse.self)
        try response.validate()
        return (response.data?.items ?? []).compactMap { item in
            guard let text = item.displayText, !text.isEmpty else {
                return nil
            }
            return FeishuRemoteMessage(
                messageID: item.messageID,
                text: text,
                senderLabel: item.senderLabel,
                createdAt: item.createdDate,
                updatedAt: item.updatedDate,
                role: item.senderRole
            )
        }
    }

    private func tenantAccessToken(settings: FeishuChatSettings) async throws -> String {
        let request = try openAPIRequest(
            path: "/open-apis/auth/v3/tenant_access_token/internal",
            token: nil,
            body: [
                "app_id": settings.appID.trimmed,
                "app_secret": settings.appSecret.trimmed,
            ]
        )
        let response = try await perform(request, as: FeishuTokenResponse.self)
        try response.validate()
        guard let token = response.tenantAccessToken, !token.isEmpty else {
            throw FeishuChatError.api("tenant_access_token missing")
        }
        return token
    }

    private func notifyBridgeIfConfigured(text: String, messageID: String, settings: FeishuChatSettings) async -> String {
        guard settings.canNotifyBridge, !messageID.isEmpty else {
            return ""
        }
        do {
            let response = try await notifyBridge(text: text, messageID: messageID, settings: settings)
            if response.ok == true {
                return response.detail ?? "bridge notified"
            }
            return response.error ?? response.detail ?? "bridge returned ok=false"
        } catch {
            return error.localizedDescription
        }
    }

    private func notifyBridge(
        text: String,
        messageID: String,
        settings: FeishuChatSettings
    ) async throws -> BridgeWebhookResponse {
        guard let url = URL(string: settings.webhookURL.trimmed) else {
            throw FeishuChatError.invalidURL
        }
        let payload: [String: Any] = [
            "token": settings.verificationToken.trimmed,
            "event": [
                "sender": ["sender_id": ["open_id": "cnb-island-app"]],
                "message": [
                    "message_id": messageID,
                    "chat_id": settings.chatID.trimmed,
                    "message_type": "text",
                    "content": ["text": text],
                ],
            ],
        ]
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json; charset=utf-8", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        return try await perform(request, as: BridgeWebhookResponse.self)
    }

    private func openAPIRequest(
        method: String = "POST",
        path: String,
        queryItems: [URLQueryItem] = [],
        token: String?,
        body: [String: Any]?
    ) throws -> URLRequest {
        var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false)
        components?.path = path
        components?.queryItems = queryItems.isEmpty ? nil : queryItems
        guard let url = components?.url else {
            throw FeishuChatError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json; charset=utf-8", forHTTPHeaderField: "Content-Type")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Request-Id")
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        return request
    }

    private func perform<Response: Decodable>(_ request: URLRequest, as type: Response.Type) async throws -> Response {
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw FeishuChatError.transport("missing HTTP response")
        }
        guard (200..<300).contains(http.statusCode) else {
            let detail = String(data: data, encoding: .utf8) ?? "HTTP \(http.statusCode)"
            throw FeishuChatError.transport("HTTP \(http.statusCode): \(detail)")
        }
        return try JSONDecoder().decode(type, from: data)
    }

    private func jsonString(_ object: [String: String]) throws -> String {
        let data = try JSONSerialization.data(withJSONObject: object)
        guard let text = String(data: data, encoding: .utf8) else {
            throw FeishuChatError.encoding
        }
        return text
    }
}

enum FeishuChatError: LocalizedError {
    case invalidURL
    case encoding
    case transport(String)
    case api(String)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            "Invalid Feishu OpenAPI URL"
        case .encoding:
            "Unable to encode Feishu request"
        case .transport(let detail):
            detail
        case .api(let detail):
            detail
        }
    }
}

private protocol FeishuAPIEnvelope {
    var code: Int { get }
    var msg: String? { get }
}

private extension FeishuAPIEnvelope {
    func validate() throws {
        guard code == 0 else {
            throw FeishuChatError.api(msg ?? "Feishu OpenAPI returned code \(code)")
        }
    }
}

private struct FeishuTokenResponse: Decodable, FeishuAPIEnvelope {
    var code: Int
    var msg: String?
    var tenantAccessToken: String?

    enum CodingKeys: String, CodingKey {
        case code
        case msg
        case tenantAccessToken = "tenant_access_token"
    }
}

private struct FeishuMessageResponse: Decodable, FeishuAPIEnvelope {
    var code: Int
    var msg: String?
    var data: FeishuMessageData?
}

private struct FeishuMessagesResponse: Decodable, FeishuAPIEnvelope {
    var code: Int
    var msg: String?
    var data: FeishuMessageListData?
}

private struct BridgeWebhookResponse: Decodable {
    var ok: Bool?
    var detail: String?
    var error: String?
}

private struct FeishuMessageData: Decodable {
    var messageID: String?

    enum CodingKeys: String, CodingKey {
        case messageID = "message_id"
    }
}

private struct FeishuMessageListData: Decodable {
    var items: [FeishuMessageItem]
}

private struct FeishuMessageItem: Decodable {
    var messageID: String
    var msgType: String
    var body: FeishuMessageBody?
    var sender: FeishuMessageSender?
    var createTime: String?
    var updateTime: String?

    enum CodingKeys: String, CodingKey {
        case messageID = "message_id"
        case msgType = "msg_type"
        case body
        case sender
        case createTime = "create_time"
        case updateTime = "update_time"
    }

    var displayText: String? {
        guard let raw = body?.content, !raw.isEmpty else {
            return nil
        }
        guard let data = raw.data(using: .utf8),
              let payload = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return raw
        }
        let rendered = FeishuMessageContentRenderer.render(msgType: msgType, payload: payload)
        return rendered.isEmpty ? raw : rendered
    }

    var senderLabel: String {
        FeishuMessageSenderMapper.label(senderType: sender?.senderType)
    }

    var senderRole: FeishuChatRole {
        FeishuMessageSenderMapper.role(msgType: msgType, senderType: sender?.senderType)
    }

    var createdDate: Date {
        date(fromMilliseconds: createTime)
    }

    var updatedDate: Date {
        date(fromMilliseconds: updateTime, fallback: createdDate)
    }

    private func date(fromMilliseconds raw: String?, fallback: Date = Date()) -> Date {
        guard let raw, let millis = Double(raw) else {
            return fallback
        }
        return Date(timeIntervalSince1970: millis / 1000)
    }
}

private struct FeishuMessageBody: Decodable {
    var content: String
}

private struct FeishuMessageSender: Decodable {
    var senderType: String?

    enum CodingKeys: String, CodingKey {
        case senderType = "sender_type"
    }
}

private extension String {
    var urlPathEncoded: String {
        addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? self
    }
}
