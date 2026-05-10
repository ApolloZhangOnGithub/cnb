import Foundation

enum FeishuMessageSenderMapper {
    static func label(senderType: String?) -> String {
        switch senderType {
        case "app":
            "CLI"
        case "user":
            "User"
        case .some(let value):
            value
        case .none:
            "Feishu"
        }
    }

    static func role(msgType: String, senderType: String?) -> FeishuChatRole {
        if msgType == "system" {
            return .system
        }
        return senderType == "app" ? .assistant : .user
    }
}

enum FeishuMessageContentRenderer {
    static func render(msgType: String, payload: [String: Any]) -> String {
        switch msgType {
        case "text":
            return stringValue(in: payload, keys: ["text", "content"])
        case "post":
            return renderPost(payload)
        case "image":
            return marker("Image", value: stringValue(in: payload, keys: ["image_key", "key"]))
        case "file":
            return marker("File", value: stringValue(in: payload, keys: ["file_name", "name", "file_key", "key"]))
        case "audio":
            return marker("Audio", value: stringValue(in: payload, keys: ["file_key", "key"]))
        case "video", "media":
            return marker("Video", value: stringValue(in: payload, keys: ["file_name", "name", "file_key", "key"]))
        case "sticker":
            return marker("Sticker", value: stringValue(in: payload, keys: ["file_key", "key"]))
        case "interactive":
            return renderInteractive(payload)
        case "share_chat":
            return marker("Shared chat", value: stringValue(in: payload, keys: ["chat_name", "chat_id"]))
        case "share_user":
            return marker("Shared user", value: stringValue(in: payload, keys: ["user_name", "user_id"]))
        default:
            return renderGeneric(payload)
        }
    }

    private static func renderPost(_ payload: [String: Any]) -> String {
        let post = (payload["zh_cn"] as? [String: Any])
            ?? (payload["en_us"] as? [String: Any])
            ?? payload.values.compactMap { $0 as? [String: Any] }.first
            ?? payload
        var lines: [String] = []
        let title = stringValue(in: post, keys: ["title"])
        if !title.isEmpty {
            lines.append(title)
        }
        if let rows = post["content"] as? [Any] {
            for row in rows {
                let line = renderPostRow(row).trimmed
                if !line.isEmpty {
                    lines.append(line)
                }
            }
        }
        if lines.isEmpty {
            lines.append(renderGeneric(post))
        }
        return lines.joined(separator: "\n")
    }

    private static func renderPostRow(_ row: Any) -> String {
        guard let elements = row as? [Any] else {
            return renderGeneric(row)
        }
        return elements.map(renderPostElement).joined()
    }

    private static func renderPostElement(_ element: Any) -> String {
        guard let item = element as? [String: Any] else {
            return renderGeneric(element)
        }
        switch item["tag"] as? String {
        case "text":
            return rawString(in: item, keys: ["text", "un_escape_text"])
        case "a":
            let text = stringValue(in: item, keys: ["text", "href"])
            let href = stringValue(in: item, keys: ["href", "url"])
            guard !href.isEmpty, href != text else {
                return text
            }
            return "\(text) (\(href))"
        case "at":
            let name = stringValue(in: item, keys: ["user_name", "name", "user_id"])
            return name.isEmpty ? "@user" : "@\(name)"
        case "img", "image":
            return marker("Image", value: stringValue(in: item, keys: ["image_key", "key"]))
        case "media", "video":
            return marker("Video", value: stringValue(in: item, keys: ["file_name", "file_key", "key"]))
        case "audio":
            return marker("Audio", value: stringValue(in: item, keys: ["file_key", "key"]))
        case "file":
            return marker("File", value: stringValue(in: item, keys: ["file_name", "file_key", "key"]))
        case "emotion":
            return marker("Sticker", value: stringValue(in: item, keys: ["emoji_type", "key"]))
        case "code_block":
            let language = stringValue(in: item, keys: ["language"])
            let text = stringValue(in: item, keys: ["text"])
            let fence = language.isEmpty ? "```" : "```\(language)"
            return "\n\(fence)\n\(text)\n```"
        default:
            return renderGeneric(item)
        }
    }

    private static func renderInteractive(_ payload: [String: Any]) -> String {
        let title = stringValue(in: payload, keys: ["title", "header", "name"])
        let generic = renderGeneric(payload)
        if title.isEmpty {
            return marker("Card", value: generic)
        }
        if generic.isEmpty || generic == title {
            return marker("Card", value: title)
        }
        return "[Card]\n\(title)\n\(generic)"
    }

    private static func renderGeneric(_ value: Any) -> String {
        if let text = value as? String {
            return text
        }
        if let number = value as? NSNumber {
            return number.stringValue
        }
        if let array = value as? [Any] {
            return compactUnique(array.map(renderGeneric)).joined(separator: "\n")
        }
        if let dict = value as? [String: Any] {
            let preferredKeys = [
                "title", "text", "content", "file_name", "name", "url", "href",
                "image_key", "file_key", "user_name", "user_id", "chat_name", "chat_id",
            ]
            var pieces = preferredKeys.compactMap { key -> String? in
                guard let raw = dict[key] else {
                    return nil
                }
                let rendered = renderGeneric(raw).trimmed
                return rendered.isEmpty ? nil : rendered
            }
            if pieces.isEmpty {
                pieces = dict.keys.sorted().compactMap { key -> String? in
                    guard let raw = dict[key] else {
                        return nil
                    }
                    let rendered = renderGeneric(raw).trimmed
                    return rendered.isEmpty ? nil : rendered
                }
            }
            return compactUnique(pieces).joined(separator: "\n")
        }
        return ""
    }

    private static func stringValue(in payload: [String: Any], keys: [String]) -> String {
        for key in keys {
            guard let value = payload[key] else {
                continue
            }
            let rendered = renderGeneric(value).trimmed
            if !rendered.isEmpty {
                return rendered
            }
        }
        return ""
    }

    private static func rawString(in payload: [String: Any], keys: [String]) -> String {
        for key in keys {
            if let value = payload[key] as? String {
                return value
            }
        }
        return stringValue(in: payload, keys: keys)
    }

    private static func marker(_ label: String, value: String) -> String {
        let detail = value.trimmed
        return detail.isEmpty ? "[\(label)]" : "[\(label): \(detail)]"
    }

    private static func compactUnique(_ values: [String]) -> [String] {
        var seen = Set<String>()
        var result: [String] = []
        for value in values.map(\.trimmed) where !value.isEmpty {
            if seen.insert(value).inserted {
                result.append(value)
            }
        }
        return result
    }
}
