import Foundation

enum CNBRuntimeFileLocator {
    static func data(named filename: String, overrideEnvironmentKey: String? = nil) throws -> Data {
        if let overrideEnvironmentKey,
           let override = ProcessInfo.processInfo.environment[overrideEnvironmentKey],
           !override.isEmpty {
            return try Data(contentsOf: URL(fileURLWithPath: override))
        }

        for url in candidateURLs(named: filename) {
            if let data = try? Data(contentsOf: url) {
                return data
            }
        }

        throw CocoaError(.fileReadNoSuchFile)
    }

    static func optionalData(named filename: String) -> Data? {
        for url in candidateURLs(named: filename) {
            if let data = try? Data(contentsOf: url) {
                return data
            }
        }
        return nil
    }

    static func optionalString(named filename: String) -> String? {
        guard let data = optionalData(named: filename) else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }

    private static func candidateURLs(named filename: String) -> [URL] {
        let home = URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)
        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
        let raw = [
            documents?.appendingPathComponent(filename),
            documents?.appendingPathComponent(".cnb").appendingPathComponent(filename),
            home.appendingPathComponent(".cnb").appendingPathComponent(filename),
            home.appendingPathComponent(filename)
        ]

        var seen = Set<String>()
        return raw.compactMap { url in
            guard let url else {
                return nil
            }
            let key = url.standardizedFileURL.path
            guard !seen.contains(key) else {
                return nil
            }
            seen.insert(key)
            return url
        }
    }
}
