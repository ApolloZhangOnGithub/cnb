import Foundation

struct CNBSnapshot {
    let supervisorName: String
    let machineName: String
    let generatedAt: Date
    let projects: [CNBProjectSummary]
    let staleRegistryEntries: Int

    static let empty = CNBSnapshot(
        supervisorName: "terminal-supervisor",
        machineName: Host.current().localizedName ?? "Mac",
        generatedAt: Date(),
        projects: [],
        staleRegistryEntries: 0
    )

    var activeProjects: [CNBProjectSummary] {
        projects.filter(\.hasActivity)
    }

    var boardProjects: [CNBProjectSummary] {
        projects.filter { $0.boardPath != nil }
    }

    var missingBoardProjects: [CNBProjectSummary] {
        projects.filter { $0.boardPath == nil }
    }

    var topProjects: [CNBProjectSummary] {
        activeProjects.sorted { lhs, rhs in
            if lhs.score == rhs.score {
                return lhs.name.localizedCaseInsensitiveCompare(rhs.name) == .orderedAscending
            }
            return lhs.score > rhs.score
        }
    }

    var attentionProjects: [CNBProjectSummary] {
        projects.filter { project in
            project.status == .attention ||
                project.status == .blocked ||
                project.pendingActions > 0 ||
                project.unreadMessages > 0 ||
                project.blockedSessions > 0
        }
    }

    var pendingActions: Int {
        projects.reduce(0) { $0 + $1.pendingActions }
    }

    var activeTasks: Int {
        projects.reduce(0) { $0 + $1.taskTotal }
    }

    var unreadMessages: Int {
        projects.reduce(0) { $0 + $1.unreadMessages }
    }

    var sessions: Int {
        projects.reduce(0) { $0 + $1.sessions }
    }

    var blockedSessions: Int {
        projects.reduce(0) { $0 + $1.blockedSessions }
    }

    var status: CNBStatus {
        if blockedSessions > 0 {
            return .blocked
        }
        if pendingActions > 0 || unreadMessages > 0 {
            return .attention
        }
        if activeTasks > 0 || sessions > 0 {
            return .working
        }
        return .quiet
    }

    var title: String {
        if let top = topProjects.first {
            if status == .attention || status == .blocked {
                return L10n.format("snapshot.title.attention", top.name)
            }
            return L10n.format("snapshot.title.active", top.name)
        }
        return L10n.string("snapshot.title.quiet")
    }

    var detail: String {
        if projects.isEmpty {
            return L10n.string("snapshot.detail.empty")
        }
        return L10n.format("snapshot.detail", pendingActions, activeTasks, unreadMessages)
    }
}
