import Foundation

struct CNBCommand: Sendable {
    var executableURL: URL
    var workingDirectoryURL: URL?
}

enum CNBCommandLocator {
    static func locate() -> CNBCommand? {
        if let override = ProcessInfo.processInfo.environment["CNB_CLI"],
           !override.trimmed.isEmpty {
            let url = URL(fileURLWithPath: NSString(string: override).expandingTildeInPath)
            if isExecutable(url) {
                return CNBCommand(executableURL: url, workingDirectoryURL: url.deletingLastPathComponent())
            }
        }

        for command in repoRelativeCandidates() {
            if isExecutable(command.executableURL) {
                return command
            }
        }

        for url in pathCandidates() where isExecutable(url) {
            return CNBCommand(executableURL: url, workingDirectoryURL: nil)
        }

        return nil
    }

    private static func repoRelativeCandidates() -> [CNBCommand] {
        var commands: [CNBCommand] = []
        let fileManager = FileManager.default
        let starts = [
            Bundle.main.bundleURL,
            URL(fileURLWithPath: fileManager.currentDirectoryPath, isDirectory: true),
            URL(fileURLWithPath: CommandLine.arguments.first ?? "", isDirectory: false)
        ]

        for start in starts {
            var current = start.hasDirectoryPath ? start : start.deletingLastPathComponent()
            for _ in 0..<8 {
                let executable = current.appendingPathComponent("bin/cnb")
                commands.append(
                    CNBCommand(
                        executableURL: executable,
                        workingDirectoryURL: executable.deletingLastPathComponent().deletingLastPathComponent()
                    )
                )
                let parent = current.deletingLastPathComponent()
                if parent.path == current.path {
                    break
                }
                current = parent
            }
        }

        return commands
    }

    private static func pathCandidates() -> [URL] {
        let environmentPath = ProcessInfo.processInfo.environment["PATH"] ?? ""
        let fallbackPath = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
        let rawPath = environmentPath.isEmpty ? fallbackPath : "\(environmentPath):\(fallbackPath)"
        return rawPath
            .split(separator: ":")
            .map { URL(fileURLWithPath: String($0)).appendingPathComponent("cnb") }
    }

    private static func isExecutable(_ url: URL) -> Bool {
        FileManager.default.isExecutableFile(atPath: url.path)
    }
}
