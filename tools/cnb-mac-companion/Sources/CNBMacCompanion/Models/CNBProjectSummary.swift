import Foundation

struct CNBProjectSummary: Identifiable, Hashable {
    let id: String
    let name: String
    let path: String
    let boardPath: String?
    let projectExists: Bool
    let pendingActions: Int
    let activeTasks: Int
    let queuedTasks: Int
    let unreadMessages: Int
    let sessions: Int
    let blockedSessions: Int
    let lastActive: Date?

    var taskTotal: Int {
        activeTasks + queuedTasks
    }

    var hasActivity: Bool {
        pendingActions > 0 || taskTotal > 0 || unreadMessages > 0 || sessions > 0 || blockedSessions > 0
    }

    var status: CNBStatus {
        guard boardPath != nil else {
            return .missingBoard
        }
        if blockedSessions > 0 {
            return .blocked
        }
        if pendingActions > 0 || unreadMessages > 0 {
            return .attention
        }
        if taskTotal > 0 || sessions > 0 {
            return .working
        }
        return .idle
    }

    var summaryLine: String {
        if boardPath == nil {
            return L10n.string("project.reason.no_board")
        }
        return L10n.format("project.summary", pendingActions, taskTotal, unreadMessages)
    }

    var statusReason: String {
        if boardPath == nil {
            return L10n.string("project.reason.no_board")
        }
        if blockedSessions > 0 {
            return L10n.format("project.reason.blocked", blockedSessions)
        }
        if pendingActions > 0 {
            return L10n.format("project.reason.pending", pendingActions)
        }
        if unreadMessages > 0 {
            return L10n.format("project.reason.unread", unreadMessages)
        }
        if taskTotal > 0 {
            return L10n.format("project.reason.tasks", taskTotal)
        }
        if sessions > 0 {
            return L10n.format("project.reason.sessions", sessions)
        }
        return L10n.string("project.reason.idle")
    }

    var score: Int {
        let boardPenalty = boardPath == nil ? -10_000 : 0
        return boardPenalty + blockedSessions * 1_000 + pendingActions * 100 + unreadMessages * 10 + taskTotal + sessions
    }
}
