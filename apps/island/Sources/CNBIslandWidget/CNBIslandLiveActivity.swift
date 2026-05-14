import ActivityKit
import SwiftUI
import WidgetKit

struct CNBIslandLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: CNBActivityAttributes.self) { context in
            lockScreenView(context: context)
                .activityBackgroundTint(backgroundTint(for: context.state.status))
                .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    VStack(alignment: .leading) {
                        Text("CNB")
                            .font(.caption.bold())
                        Text(context.attributes.supervisorName)
                            .font(.caption2)
                    }
                    .foregroundStyle(.white)
                }

                DynamicIslandExpandedRegion(.center) {
                    VStack(alignment: .leading) {
                        Text(context.state.title)
                            .font(.headline)
                            .lineLimit(1)
                        Text(context.state.localizedDetail)
                            .font(.caption)
                            .lineLimit(2)
                    }
                    .foregroundStyle(.white)
                }

                DynamicIslandExpandedRegion(.trailing) {
                    expandedMetric(for: context.state)
                }
            } compactLeading: {
                Text("CNB")
                    .font(.caption.bold())
                    .foregroundStyle(.white)
            } compactTrailing: {
                compactMetric(for: context.state)
            } minimal: {
                Image(systemName: symbolName(for: context.state.status))
                    .foregroundStyle(.white)
            }
            .keylineTint(backgroundTint(for: context.state.status))
        }
    }

    private func lockScreenView(context: ActivityViewContext<CNBActivityAttributes>) -> some View {
        HStack(spacing: 12) {
            Image(systemName: symbolName(for: context.state.status))
                .font(.title3.bold())
                .foregroundStyle(.white)

            VStack(alignment: .leading, spacing: 2) {
                Text(context.state.title)
                    .font(.headline)
                    .foregroundStyle(.white)
                    .lineLimit(1)
                Text(context.state.localizedDetail)
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.78))
                    .lineLimit(2)
            }

            Spacer()

            if let metric = primaryMetric(for: context.state) {
                VStack(alignment: .trailing, spacing: 2) {
                    Text("\(metric.value)")
                        .font(.title3.monospacedDigit().bold())
                        .foregroundStyle(.white)
                    Text(metric.label)
                        .font(.caption2)
                        .foregroundStyle(.white.opacity(0.78))
                }
            }
        }
        .padding()
    }

    private func symbolName(for status: CNBActivityStatus) -> String {
        switch status {
        case .quiet:
            return "checkmark.circle.fill"
        case .working:
            return "bolt.fill"
        case .attention:
            return "exclamationmark.triangle.fill"
        case .blocked:
            return "hand.raised.fill"
        case .shuttingDown:
            return "moon.fill"
        case .updating:
            return "arrow.triangle.2.circlepath"
        }
    }

    private func backgroundTint(for status: CNBActivityStatus) -> Color {
        switch status {
        case .quiet:
            return .green.opacity(0.86)
        case .working:
            return .blue.opacity(0.86)
        case .attention:
            return .orange.opacity(0.9)
        case .blocked:
            return .red.opacity(0.88)
        case .shuttingDown:
            return .indigo.opacity(0.86)
        case .updating:
            return .purple.opacity(0.86)
        }
    }

    @ViewBuilder
    private func expandedMetric(for state: CNBActivityAttributes.ContentState) -> some View {
        if let metric = primaryMetric(for: state) {
            VStack(alignment: .trailing) {
                Text("\(metric.value)")
                    .font(.title3.monospacedDigit().bold())
                Text(metric.label)
                    .font(.caption2)
            }
            .foregroundStyle(.white)
        } else {
            Image(systemName: symbolName(for: state.status))
                .font(.title3.bold())
                .foregroundStyle(.white)
        }
    }

    @ViewBuilder
    private func compactMetric(for state: CNBActivityAttributes.ContentState) -> some View {
        if let metric = primaryMetric(for: state) {
            Text("\(metric.value)")
                .font(.caption.monospacedDigit().bold())
                .foregroundStyle(.white)
        } else {
            Image(systemName: symbolName(for: state.status))
                .font(.caption.bold())
                .foregroundStyle(.white)
        }
    }

    private func primaryMetric(for state: CNBActivityAttributes.ContentState) -> ActivityMetric? {
        if state.pendingActions > 0 {
            return ActivityMetric(value: state.pendingActions, label: "label.pending")
        }
        if state.activeTasks > 0 {
            return ActivityMetric(value: state.activeTasks, label: "metric.tasks")
        }
        return nil
    }
}

private struct ActivityMetric {
    var value: Int
    var label: LocalizedStringKey
}

#if DEBUG
private let previewAttributes = CNBActivityAttributes(
    supervisorName: "terminal-supervisor",
    machineName: "Kezhen-MacBook"
)

private let previewWorkingState = CNBActivityAttributes.ContentState(
    title: "silicon_vally_battle active",
    detail: "2 tasks",
    status: .working,
    activeProjects: 7,
    pendingActions: 0,
    activeTasks: 2,
    unreadMessages: 1294,
    updatedAt: Date(timeIntervalSinceReferenceDate: 799286400)
)

private let previewAttentionState = CNBActivityAttributes.ContentState(
    title: "Needs user action",
    detail: "1 pending approval, 3 active tasks, 18 unread",
    status: .attention,
    activeProjects: 4,
    pendingActions: 1,
    activeTasks: 3,
    unreadMessages: 18,
    updatedAt: Date(timeIntervalSinceReferenceDate: 799286700)
)

#Preview("CNB Lock Screen", as: .content, using: previewAttributes) {
    CNBIslandLiveActivity()
} contentStates: {
    previewWorkingState
    previewAttentionState
}

#Preview("CNB Island Compact", as: .dynamicIsland(.compact), using: previewAttributes) {
    CNBIslandLiveActivity()
} contentStates: {
    previewWorkingState
    previewAttentionState
}

#Preview("CNB Island Expanded", as: .dynamicIsland(.expanded), using: previewAttributes) {
    CNBIslandLiveActivity()
} contentStates: {
    previewWorkingState
    previewAttentionState
}

#Preview("CNB Island Minimal", as: .dynamicIsland(.minimal), using: previewAttributes) {
    CNBIslandLiveActivity()
} contentStates: {
    previewWorkingState
    previewAttentionState
}
#endif
