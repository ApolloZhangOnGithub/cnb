import ActivityKit
import Foundation

public enum CNBActivityStatus: String, Codable, Hashable, Sendable {
    case quiet
    case working
    case attention
    case blocked
    case shuttingDown
    case updating
}

public struct CNBActivityAttributes: ActivityAttributes, Sendable {
    public struct ContentState: Codable, Hashable, Sendable {
        public var title: String
        public var detail: String
        public var status: CNBActivityStatus
        public var activeProjects: Int
        public var pendingActions: Int
        public var activeTasks: Int
        public var unreadMessages: Int
        public var updatedAt: Date

        public init(
            title: String,
            detail: String,
            status: CNBActivityStatus,
            activeProjects: Int,
            pendingActions: Int,
            activeTasks: Int,
            unreadMessages: Int,
            updatedAt: Date
        ) {
            self.title = title
            self.detail = detail
            self.status = status
            self.activeProjects = activeProjects
            self.pendingActions = pendingActions
            self.activeTasks = activeTasks
            self.unreadMessages = unreadMessages
            self.updatedAt = updatedAt
        }
    }

    public var supervisorName: String
    public var machineName: String

    public init(supervisorName: String, machineName: String) {
        self.supervisorName = supervisorName
        self.machineName = machineName
    }
}
