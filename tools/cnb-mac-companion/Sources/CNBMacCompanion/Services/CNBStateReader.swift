import Foundation

struct CNBStateReader: Sendable {
    private let sqlite = SQLiteCommand()

    func read() throws -> CNBSnapshot {
        let fileManager = FileManager.default
        let home = fileManager.homeDirectoryForCurrentUser
        let registryURL = home.appendingPathComponent(".cnb/projects.json")
        let registry = try readRegistry(from: registryURL)

        var summaries: [CNBProjectSummary] = []
        var staleEntries = 0
        var seenPaths = Set<String>()

        for entry in registry.projects {
            let projectURL = URL(fileURLWithPath: NSString(string: entry.path).expandingTildeInPath)
            let normalizedPath = projectURL.path

            guard !seenPaths.contains(normalizedPath) else {
                continue
            }
            seenPaths.insert(normalizedPath)

            guard fileManager.fileExists(atPath: normalizedPath) else {
                staleEntries += 1
                continue
            }

            summaries.append(
                inspectProject(
                    entry: entry,
                    projectURL: projectURL,
                    boardURL: boardURL(for: projectURL, fileManager: fileManager)
                )
            )
        }

        return CNBSnapshot(
            supervisorName: ProcessInfo.processInfo.environment["CNB_SUPERVISOR"] ?? "terminal-supervisor",
            machineName: Host.current().localizedName ?? Host.current().name ?? "Mac",
            generatedAt: Date(),
            projects: summaries.sorted { lhs, rhs in
                if lhs.hasActivity != rhs.hasActivity {
                    return lhs.hasActivity && !rhs.hasActivity
                }
                if lhs.score != rhs.score {
                    return lhs.score > rhs.score
                }
                return lhs.name.localizedCaseInsensitiveCompare(rhs.name) == .orderedAscending
            },
            staleRegistryEntries: staleEntries
        )
    }

    private func readRegistry(from url: URL) throws -> ProjectRegistry {
        let data = try Data(contentsOf: url)
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(ProjectRegistry.self, from: data)
    }

    private func boardURL(for projectURL: URL, fileManager: FileManager) -> URL? {
        let candidates = [
            projectURL.appendingPathComponent(".cnb/board.db"),
            projectURL.appendingPathComponent(".claudes/board.db")
        ]

        return candidates.first { fileManager.fileExists(atPath: $0.path) }
    }

    private func inspectProject(
        entry: RegisteredProject,
        projectURL: URL,
        boardURL: URL?
    ) -> CNBProjectSummary {
        guard let boardURL else {
            return CNBProjectSummary(
                id: projectURL.path,
                name: projectName(from: entry, projectURL: projectURL),
                path: projectURL.path,
                boardPath: nil,
                projectExists: true,
                pendingActions: 0,
                activeTasks: 0,
                queuedTasks: 0,
                unreadMessages: 0,
                sessions: 0,
                blockedSessions: 0,
                lastActive: entry.lastActive
            )
        }

        let boardPath = boardURL.path
        let pendingActions = sqlite.count(
            databasePath: boardPath,
            sql: "SELECT COUNT(*) FROM pending_actions WHERE status IN ('pending', 'reminded');"
        )
        let activeTasks = sqlite.count(
            databasePath: boardPath,
            sql: "SELECT COUNT(*) FROM tasks WHERE status = 'active';"
        )
        let queuedTasks = sqlite.count(
            databasePath: boardPath,
            sql: "SELECT COUNT(*) FROM tasks WHERE status = 'pending';"
        )
        let unreadMessages = sqlite.count(
            databasePath: boardPath,
            sql: "SELECT COUNT(*) FROM inbox WHERE read = 0;"
        )
        let sessions = sqlite.count(
            databasePath: boardPath,
            sql: "SELECT COUNT(*) FROM sessions WHERE name NOT IN ('all', 'dispatcher');"
        )
        let blockedSessions = sqlite.count(
            databasePath: boardPath,
            sql: "SELECT COUNT(*) FROM sessions WHERE status IN ('blocked', 'waiting', 'stalled');"
        )

        return CNBProjectSummary(
            id: projectURL.path,
            name: projectName(from: entry, projectURL: projectURL),
            path: projectURL.path,
            boardPath: boardPath,
            projectExists: true,
            pendingActions: pendingActions,
            activeTasks: activeTasks,
            queuedTasks: queuedTasks,
            unreadMessages: unreadMessages,
            sessions: sessions,
            blockedSessions: blockedSessions,
            lastActive: entry.lastActive
        )
    }

    private func projectName(from entry: RegisteredProject, projectURL: URL) -> String {
        if let name = entry.name, !name.isEmpty {
            return name
        }
        return projectURL.lastPathComponent
    }
}
