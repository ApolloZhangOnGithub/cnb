@preconcurrency import ActivityKit
import Foundation

enum CNBLiveActivityController {
    static func start(with state: CNBLiveState) throws -> String {
        if let existing = Activity<CNBActivityAttributes>.activities.first {
            Task {
                await update(with: state)
            }
            return existing.id
        }

        let content = ActivityContent(
            state: state.contentState,
            staleDate: Date().addingTimeInterval(30 * 60)
        )
        let activity = try Activity<CNBActivityAttributes>.request(
            attributes: state.attributes,
            content: content,
            pushType: nil
        )
        return activity.id
    }

    static func update(with state: CNBLiveState) async {
        guard let activity = Activity<CNBActivityAttributes>.activities.first else {
            return
        }
        let content = ActivityContent(
            state: state.contentState,
            staleDate: Date().addingTimeInterval(30 * 60)
        )
        await activity.update(content)
    }

    static func endAll(with state: CNBLiveState) async {
        let content = ActivityContent(
            state: state.contentState,
            staleDate: nil
        )
        for activity in Activity<CNBActivityAttributes>.activities {
            await activity.end(content, dismissalPolicy: .immediate)
        }
    }

    static func end(with state: CNBLiveState) async {
        guard let activity = Activity<CNBActivityAttributes>.activities.first else {
            return
        }
        let content = ActivityContent(
            state: state.contentState,
            staleDate: nil
        )
        await activity.end(content, dismissalPolicy: .immediate)
    }
}
