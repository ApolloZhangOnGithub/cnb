import Foundation

struct SQLiteCommand: Sendable {
    private let executable = URL(fileURLWithPath: "/usr/bin/sqlite3")

    func count(databasePath: String, sql: String) -> Int {
        let output = run(databasePath: databasePath, sql: sql)
        return Int(output.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0
    }

    private func run(databasePath: String, sql: String) -> String {
        let process = Process()
        let stdout = Pipe()
        let stderr = Pipe()

        process.executableURL = executable
        process.arguments = ["-readonly", databasePath, sql]
        process.standardOutput = stdout
        process.standardError = stderr

        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return ""
        }

        guard process.terminationStatus == 0 else {
            return ""
        }

        let data = stdout.fileHandleForReading.readDataToEndOfFile()
        return String(data: data, encoding: .utf8) ?? ""
    }
}
