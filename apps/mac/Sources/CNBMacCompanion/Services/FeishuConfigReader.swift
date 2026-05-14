import Foundation

enum FeishuConfigReader {
    static func loadRuntimeSettings() -> FeishuChatSettings? {
        if let json = loadJSONSettings() {
            return json
        }
        return loadTOMLSettings()
    }

    static func loadWatchSettings() -> FeishuWatchSettings {
        let url = cnbHome().appendingPathComponent("config.toml")
        guard let text = try? String(contentsOf: url) else {
            return FeishuWatchSettings(configURL: url)
        }
        let section = firstTOMLSection(named: ["feishu", "notification.feishu"], from: text)
        guard !section.isEmpty else {
            return FeishuWatchSettings(configURL: url)
        }
        return FeishuWatchSettings(
            configURL: url,
            host: firstString(in: section, keys: ["watch_host", "watch-host"], defaultValue: "127.0.0.1"),
            port: firstInt(in: section, keys: ["watch_port", "watch-port"], defaultValue: 8765),
            token: firstString(in: section, keys: ["watch_token", "watch-token"]),
            projectRoot: firstString(in: section, keys: ["project", "project_root", "project-root"])
        )
    }

    private static func loadJSONSettings() -> FeishuChatSettings? {
        let url = cnbHome().appendingPathComponent("feishu_chat.json")
        guard let data = try? Data(contentsOf: url) else {
            return nil
        }
        return try? JSONDecoder().decode(FeishuChatSettings.self, from: data)
    }

    private static func loadTOMLSettings() -> FeishuChatSettings? {
        let url = cnbHome().appendingPathComponent("config.toml")
        guard let text = try? String(contentsOf: url) else {
            return nil
        }
        let section = firstTOMLSection(named: ["feishu", "notification.feishu"], from: text)
        guard !section.isEmpty else {
            return nil
        }
        return FeishuChatSettings(
            appID: firstString(in: section, keys: ["app_id", "app-id"]),
            appSecret: firstString(in: section, keys: ["app_secret", "app-secret"]),
            chatID: firstString(in: section, keys: ["chat_id", "chat-id", "allowed_chat_ids", "chat_ids"]),
            webhookURL: firstString(in: section, keys: ["webhook_public_url", "webhook-public-url"]),
            verificationToken: firstString(in: section, keys: ["verification_token", "verification-token"])
        )
    }

    private static func cnbHome() -> URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".cnb")
    }

    private static func firstTOMLSection(named names: [String], from text: String) -> [String: String] {
        for name in names {
            let section = extractTOMLSection(named: name, from: text)
            if !section.isEmpty {
                return section
            }
        }
        return [:]
    }

    private static func extractTOMLSection(named name: String, from text: String) -> [String: String] {
        var active = false
        var values: [String: String] = [:]
        for rawLine in text.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            if line.hasPrefix("[") && line.hasSuffix("]") {
                active = line == "[\(name)]"
                continue
            }
            guard active, !line.isEmpty, !line.hasPrefix("#") else {
                continue
            }
            let parts = line.split(separator: "=", maxSplits: 1).map(String.init)
            guard parts.count == 2 else {
                continue
            }
            values[parts[0].trimmingCharacters(in: .whitespaces)] = parts[1].trimmingCharacters(in: .whitespaces)
        }
        return values
    }

    private static func firstString(in section: [String: String], keys: [String], defaultValue: String = "") -> String {
        for key in keys {
            guard let raw = section[key] else {
                continue
            }
            if let value = parseString(raw), !value.isEmpty {
                return value
            }
            if let value = parseFirstArrayString(raw), !value.isEmpty {
                return value
            }
        }
        return defaultValue
    }

    private static func firstInt(in section: [String: String], keys: [String], defaultValue: Int) -> Int {
        for key in keys {
            guard let raw = section[key] else {
                continue
            }
            let value = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            if let parsed = Int(value) {
                return parsed
            }
            if let string = parseString(value), let parsed = Int(string) {
                return parsed
            }
        }
        return defaultValue
    }

    private static func parseString(_ raw: String) -> String? {
        let value = raw.trimmingCharacters(in: .whitespaces)
        guard value.hasPrefix("\""), value.hasSuffix("\"") else {
            return nil
        }
        let inner = String(value.dropFirst().dropLast())
        return inner.replacingOccurrences(of: "\\\"", with: "\"")
    }

    private static func parseFirstArrayString(_ raw: String) -> String? {
        let value = raw.trimmingCharacters(in: .whitespaces)
        guard value.hasPrefix("[") else {
            return nil
        }
        let pattern = #""([^"]+)""#
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(in: value, range: NSRange(value.startIndex..., in: value)),
              let range = Range(match.range(at: 1), in: value) else {
            return nil
        }
        return String(value[range])
    }
}
