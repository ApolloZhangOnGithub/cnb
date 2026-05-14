import Foundation

struct AppBuildInfo {
    static let shared = AppBuildInfo()

    let version: String
    let build: String
    let date: String
    let git: String

    var displayVersion: String { version }

    var buildDetail: String {
        if git == "unknown" && date.isEmpty {
            return "#\(build)"
        }
        return "#\(build) (\(git), \(date))"
    }

    private init() {
        let bundle = Bundle.main
        version = bundle.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "dev"
        build = bundle.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "0"

        var metaDate = ""
        var metaGit = "unknown"
        if let metaURL = bundle.bundleURL.deletingLastPathComponent().appendingPathComponent("build_meta.json") as URL?,
           let data = try? Data(contentsOf: metaURL),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: String] {
            metaDate = json["date"] ?? ""
            metaGit = json["git"] ?? "unknown"
        }
        date = metaDate
        git = metaGit
    }
}
