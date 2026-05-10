import Foundation

struct FeishuChatClient {
    private let baseURL = URL(string: "https://open.feishu.cn")!
    private let accountsBaseURL = URL(string: "https://accounts.feishu.cn")!

    func send(text: String, settings: FeishuChatSettings) async throws -> FeishuSendResult {
        let token = try await tenantAccessToken(settings: settings)
        let content = try jsonString(["text": text])
        let replyID = settings.replyMessageID.trimmed
        let chatID = settings.primaryChatID

        let request: URLRequest
        if replyID.isEmpty {
            request = try openAPIRequest(
                path: "/open-apis/im/v1/messages",
                queryItems: [URLQueryItem(name: "receive_id_type", value: "chat_id")],
                token: token,
                body: [
                    "receive_id": chatID,
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

    func sendAsUser(text: String, settings: FeishuChatSettings) async throws -> FeishuSendResult {
        let token = settings.userAccessToken.trimmed
        guard !token.isEmpty else {
            throw FeishuChatError.api("missing user access token")
        }
        let content = try jsonString(["text": text])
        let request = try openAPIRequest(
            path: "/open-apis/im/v1/messages",
            queryItems: [URLQueryItem(name: "receive_id_type", value: "chat_id")],
            token: token,
            body: [
                "receive_id": settings.primaryChatID,
                "msg_type": "text",
                "content": content,
            ]
        )
        let response = try await perform(request, as: FeishuMessageResponse.self)
        try response.validate()
        return FeishuSendResult(messageID: response.data?.messageID ?? "", bridgeDetail: "")
    }

    func uploadImage(data: Data, settings: FeishuChatSettings) async throws -> String {
        let token = settings.userAccessToken.trimmed
        guard !token.isEmpty else {
            throw FeishuChatError.api("missing user access token")
        }
        let boundary = "Boundary-\(UUID().uuidString)"
        var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false)
        components?.path = "/open-apis/im/v1/images"
        guard let url = components?.url else {
            throw FeishuChatError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Request-Id")

        var body = Data()
        body.appendUTF8("--\(boundary)\r\n")
        body.appendUTF8("Content-Disposition: form-data; name=\"image_type\"\r\n\r\n")
        body.appendUTF8("message\r\n")
        body.appendUTF8("--\(boundary)\r\n")
        body.appendUTF8("Content-Disposition: form-data; name=\"image\"; filename=\"image.png\"\r\n")
        body.appendUTF8("Content-Type: image/png\r\n\r\n")
        body.append(data)
        body.appendUTF8("\r\n--\(boundary)--\r\n")
        request.httpBody = body

        let response = try await perform(request, as: FeishuImageUploadResponse.self)
        try response.validate()
        guard let imageKey = response.data?.imageKey, !imageKey.isEmpty else {
            throw FeishuChatError.api("image_key missing")
        }
        return imageKey
    }

    func sendImageAsUser(imageKey: String, settings: FeishuChatSettings) async throws -> FeishuSendResult {
        let token = settings.userAccessToken.trimmed
        guard !token.isEmpty else {
            throw FeishuChatError.api("missing user access token")
        }
        let content = try jsonString(["image_key": imageKey])
        let request = try openAPIRequest(
            path: "/open-apis/im/v1/messages",
            queryItems: [URLQueryItem(name: "receive_id_type", value: "chat_id")],
            token: token,
            body: [
                "receive_id": settings.primaryChatID,
                "msg_type": "image",
                "content": content,
            ]
        )
        let response = try await perform(request, as: FeishuMessageResponse.self)
        try response.validate()
        return FeishuSendResult(messageID: response.data?.messageID ?? "", bridgeDetail: "")
    }

    func startUserDeviceAuthorization(settings: FeishuChatSettings) async throws -> FeishuDeviceAuthorization {
        let request = try formRequest(
            baseURL: accountsBaseURL,
            path: "/oauth/v1/device_authorization",
            fields: [
                "client_id": settings.appID.trimmed,
                "client_secret": settings.appSecret.trimmed,
                "scope": "im:message im:message.send_as_user offline_access",
            ]
        )
        let response = try await perform(request, as: FeishuDeviceAuthorizationResponse.self)
        return FeishuDeviceAuthorization(
            deviceCode: response.deviceCode,
            userCode: response.userCode,
            verificationURL: response.verificationURI,
            verificationURLComplete: response.verificationURIComplete,
            expiresIn: response.expiresIn,
            interval: response.interval
        )
    }

    func pollUserDeviceToken(
        deviceCode: String,
        settings: FeishuChatSettings,
        interval: Int,
        expiresIn: Int
    ) async throws -> FeishuUserAuthState {
        let startedAt = Date()
        var waitSeconds = max(1, interval)
        while Date().timeIntervalSince(startedAt) < TimeInterval(expiresIn) {
            try await Task.sleep(nanoseconds: UInt64(waitSeconds) * 1_000_000_000)
            let result = try await requestUserDeviceToken(deviceCode: deviceCode, settings: settings)
            switch result {
            case .success(let token):
                let userName = (try? await fetchCurrentUserName(accessToken: token.accessToken)) ?? ""
                return FeishuUserAuthState(
                    accessToken: token.accessToken,
                    refreshToken: token.refreshToken,
                    expiresAt: token.expiresAt,
                    refreshExpiresAt: token.refreshExpiresAt,
                    userName: userName
                )
            case .pending:
                continue
            case .slowDown:
                waitSeconds += 5
            case .failed(let message):
                throw FeishuChatError.api(message)
            }
        }
        throw FeishuChatError.api("authorization timed out")
    }

    func fetchRecentMessages(settings: FeishuChatSettings, limit: Int = 20) async throws -> [FeishuRemoteMessage] {
        let token = try await tenantAccessToken(settings: settings)
        let chatID = settings.primaryChatID
        let request = try openAPIRequest(
            method: "GET",
            path: "/open-apis/im/v1/messages",
            queryItems: [
                URLQueryItem(name: "container_id_type", value: "chat"),
                URLQueryItem(name: "container_id", value: chatID),
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
                senderLabel: item.senderLabel(settings: settings),
                createdAt: item.createdDate,
                updatedAt: item.updatedDate,
                role: item.senderRole,
                chatID: chatID
            )
        }
    }

    func fetchChatInfo(settings: FeishuChatSettings) async throws -> FeishuChatInfo {
        let token = try await tenantAccessToken(settings: settings)
        let chatID = settings.primaryChatID
        let request = try openAPIRequest(
            method: "GET",
            path: "/open-apis/im/v1/chats/\(chatID.urlPathEncoded)",
            token: token,
            body: nil
        )
        let response = try await perform(request, as: FeishuChatInfoResponse.self)
        try response.validate()
        let data = response.data
        return FeishuChatInfo(
            chatID: chatID,
            name: data?.name ?? "",
            chatMode: data?.chatMode ?? "",
            chatStatus: data?.chatStatus ?? "",
            messageError: "",
            isReadable: true
        )
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
                    "chat_id": settings.primaryChatID,
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

    private func formRequest(baseURL: URL, path: String, fields: [String: String]) throws -> URLRequest {
        var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false)
        components?.path = path
        guard let url = components?.url else {
            throw FeishuChatError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Request-Id")
        request.httpBody = fields
            .map { key, value in
                "\(key.urlFormEncoded)=\(value.urlFormEncoded)"
            }
            .joined(separator: "&")
            .data(using: .utf8)
        return request
    }

    private enum FeishuOAuthPollResult {
        case success(FeishuUserAuthState)
        case pending
        case slowDown
        case failed(String)
    }

    private func requestUserDeviceToken(deviceCode: String, settings: FeishuChatSettings) async throws -> FeishuOAuthPollResult {
        let request = try formRequest(
            baseURL: baseURL,
            path: "/open-apis/authen/v2/oauth/token",
            fields: [
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": deviceCode,
                "client_id": settings.appID.trimmed,
                "client_secret": settings.appSecret.trimmed,
            ]
        )
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw FeishuChatError.transport("missing HTTP response")
        }
        if (200..<300).contains(http.statusCode) {
            let decoded = try JSONDecoder().decode(FeishuOAuthTokenResponse.self, from: data)
            let now = Date().timeIntervalSince1970
            return .success(FeishuUserAuthState(
                accessToken: decoded.accessToken,
                refreshToken: decoded.refreshToken ?? "",
                expiresAt: now + TimeInterval(decoded.expiresIn),
                refreshExpiresAt: now + TimeInterval(decoded.refreshTokenExpiresIn ?? 0),
                userName: ""
            ))
        }

        let decoded = (try? JSONDecoder().decode(FeishuOAuthErrorResponse.self, from: data))
        switch decoded?.error {
        case "authorization_pending":
            return .pending
        case "slow_down":
            return .slowDown
        case .some(let error):
            return .failed(decoded?.errorDescription ?? error)
        case .none:
            let detail = String(data: data, encoding: .utf8) ?? "HTTP \(http.statusCode)"
            return .failed(detail)
        }
    }

    private func fetchCurrentUserName(accessToken: String) async throws -> String {
        let request = try openAPIRequest(
            method: "GET",
            path: "/open-apis/authen/v1/user_info",
            token: accessToken,
            body: nil
        )
        let response = try await perform(request, as: FeishuUserInfoResponse.self)
        try response.validate()
        return response.data?.name?.trimmed ?? ""
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

private struct FeishuDeviceAuthorizationResponse: Decodable {
    var deviceCode: String
    var userCode: String
    var verificationURI: String
    var verificationURIComplete: String
    var expiresIn: Int
    var interval: Int

    enum CodingKeys: String, CodingKey {
        case deviceCode = "device_code"
        case userCode = "user_code"
        case verificationURI = "verification_uri"
        case verificationURIComplete = "verification_uri_complete"
        case expiresIn = "expires_in"
        case interval
    }
}

private struct FeishuOAuthTokenResponse: Decodable {
    var accessToken: String
    var refreshToken: String?
    var expiresIn: Int
    var refreshTokenExpiresIn: Int?

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresIn = "expires_in"
        case refreshTokenExpiresIn = "refresh_token_expires_in"
    }
}

private struct FeishuOAuthErrorResponse: Decodable {
    var error: String?
    var errorDescription: String?

    enum CodingKeys: String, CodingKey {
        case error
        case errorDescription = "error_description"
    }
}

private struct FeishuMessagesResponse: Decodable, FeishuAPIEnvelope {
    var code: Int
    var msg: String?
    var data: FeishuMessageListData?
}

private struct FeishuUserInfoResponse: Decodable, FeishuAPIEnvelope {
    var code: Int
    var msg: String?
    var data: FeishuUserInfoData?
}

private struct FeishuUserInfoData: Decodable {
    var name: String?
}

private struct FeishuChatInfoResponse: Decodable, FeishuAPIEnvelope {
    var code: Int
    var msg: String?
    var data: FeishuChatInfoData?
}

private struct BridgeWebhookResponse: Decodable {
    var ok: Bool?
    var detail: String?
    var error: String?
}

private struct FeishuImageUploadResponse: Decodable, FeishuAPIEnvelope {
    var code: Int
    var msg: String?
    var data: FeishuImageUploadData?
}

private struct FeishuImageUploadData: Decodable {
    var imageKey: String?
    enum CodingKeys: String, CodingKey {
        case imageKey = "image_key"
    }
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

private struct FeishuChatInfoData: Decodable {
    var name: String?
    var chatMode: String?
    var chatStatus: String?

    enum CodingKeys: String, CodingKey {
        case name
        case chatMode = "chat_mode"
        case chatStatus = "chat_status"
    }
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

    func senderLabel(settings: FeishuChatSettings) -> String {
        if sender?.senderType == "app", sender?.id == settings.appID, !settings.botName.trimmed.isEmpty {
            return settings.botName
        }
        if sender?.senderType == "user", !settings.userName.trimmed.isEmpty {
            return settings.userName
        }
        return FeishuMessageSenderMapper.label(senderType: sender?.senderType)
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
    var id: String?
    var senderType: String?

    enum CodingKeys: String, CodingKey {
        case id
        case senderType = "sender_type"
    }
}

private extension String {
    var urlPathEncoded: String {
        addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? self
    }

    var urlFormEncoded: String {
        var allowed = CharacterSet.urlQueryAllowed
        allowed.remove(charactersIn: "&+=?")
        return addingPercentEncoding(withAllowedCharacters: allowed) ?? self
    }
}

private extension Data {
    mutating func appendUTF8(_ string: String) {
        if let data = string.data(using: .utf8) {
            append(data)
        }
    }
}
