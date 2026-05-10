import Foundation

public struct CNBLiveState: Codable, Hashable, Sendable {
    public var supervisorName: String
    public var machineName: String
    public var title: String
    public var detail: String
    public var status: CNBActivityStatus
    public var activeProjects: Int
    public var pendingActions: Int
    public var activeTasks: Int
    public var unreadMessages: Int
    public var updatedAt: Date

    public init(
        supervisorName: String,
        machineName: String,
        title: String,
        detail: String,
        status: CNBActivityStatus,
        activeProjects: Int,
        pendingActions: Int,
        activeTasks: Int,
        unreadMessages: Int,
        updatedAt: Date
    ) {
        self.supervisorName = supervisorName
        self.machineName = machineName
        self.title = title
        self.detail = detail
        self.status = status
        self.activeProjects = activeProjects
        self.pendingActions = pendingActions
        self.activeTasks = activeTasks
        self.unreadMessages = unreadMessages
        self.updatedAt = updatedAt
    }

    public var attributes: CNBActivityAttributes {
        CNBActivityAttributes(supervisorName: supervisorName, machineName: machineName)
    }

    public var contentState: CNBActivityAttributes.ContentState {
        CNBActivityAttributes.ContentState(
            title: title,
            detail: detail,
            status: status,
            activeProjects: activeProjects,
            pendingActions: pendingActions,
            activeTasks: activeTasks,
            unreadMessages: unreadMessages,
            updatedAt: updatedAt
        )
    }

    public var localizedDetail: String {
        CNBLocalizedStrings.countSummary(
            pending: pendingActions,
            tasks: activeTasks,
            unread: unreadMessages
        )
    }

    public static var fallback: CNBLiveState {
        CNBLiveState(
            supervisorName: "terminal-supervisor",
            machineName: "Mac",
            title: CNBLocalizedStrings.quietTitle,
            detail: CNBLocalizedStrings.quietDetail,
            status: .quiet,
            activeProjects: 0,
            pendingActions: 0,
            activeTasks: 0,
            unreadMessages: 0,
            updatedAt: Date()
        )
    }
}

public extension CNBActivityAttributes.ContentState {
    var localizedDetail: String {
        CNBLocalizedStrings.countSummary(
            pending: pendingActions,
            tasks: activeTasks,
            unread: unreadMessages
        )
    }
}

private enum CNBLocalizedStrings {
    static var quietTitle: String {
        NSLocalizedString("state.quietTitle", comment: "Fallback title when no cnb project needs attention")
    }

    static var quietDetail: String {
        NSLocalizedString("state.quietDetail", comment: "Fallback detail when no cnb project needs attention")
    }

    static func countSummary(pending: Int, tasks: Int, unread: Int) -> String {
        _ = unread
        var parts: [String] = []
        if pending > 0 {
            let format = NSLocalizedString(
                "summary.pendingFormat",
                comment: "Summary format for pending actions"
            )
            parts.append(String.localizedStringWithFormat(format, pending))
        }
        if tasks > 0 {
            let format = NSLocalizedString(
                "summary.tasksFormat",
                comment: "Summary format for active tasks"
            )
            parts.append(String.localizedStringWithFormat(format, tasks))
        }
        return parts.isEmpty ? quietDetail : parts.joined(separator: NSLocalizedString("summary.separator", comment: "Separator between non-zero state counters"))
    }
}
