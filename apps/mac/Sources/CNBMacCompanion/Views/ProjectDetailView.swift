import SwiftUI

struct ProjectDetailView: View {
    let project: CNBProjectSummary

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack(alignment: .top, spacing: 14) {
                    Image(systemName: project.status.systemImage)
                        .font(.system(size: 30, weight: .semibold))
                        .foregroundStyle(project.status.tint)
                        .frame(width: 40)

                    VStack(alignment: .leading, spacing: 4) {
                        Text(project.name)
                            .font(.title2.bold())
                            .lineLimit(1)
                        Text(project.path)
                            .font(.callout)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                            .truncationMode(.middle)
                        Text(project.summaryLine)
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                    }

                    Spacer()
                }

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 130, maximum: 180), spacing: 12, alignment: .top)], spacing: 12) {
                    DetailMetric(title: L10n.string("metric.pending"), value: project.pendingActions, systemImage: "person.crop.circle.badge.exclamationmark")
                    DetailMetric(title: L10n.string("metric.active"), value: project.activeTasks, systemImage: "bolt")
                    DetailMetric(title: L10n.string("metric.queued"), value: project.queuedTasks, systemImage: "tray")
                    DetailMetric(title: L10n.string("metric.unread"), value: project.unreadMessages, systemImage: "tray.full")
                    DetailMetric(title: L10n.string("metric.sessions"), value: project.sessions, systemImage: "terminal")
                    DetailMetric(title: L10n.string("metric.blocked"), value: project.blockedSessions, systemImage: "hand.raised")
                }

                VStack(alignment: .leading, spacing: 10) {
                    Text(L10n.string("section.actions"))
                        .font(.headline)

                    HStack(spacing: 10) {
                        Button {
                            MacActionService.openTerminal(atPath: project.path)
                        } label: {
                            Label(L10n.string("action.open_terminal"), systemImage: "terminal")
                        }

                        Button {
                            MacActionService.openProjectFolder(project)
                        } label: {
                            Label(L10n.string("action.open_folder"), systemImage: "folder")
                        }

                        if project.boardPath != nil {
                            Button {
                                MacActionService.revealBoard(project)
                            } label: {
                                Label(L10n.string("action.reveal_board"), systemImage: "tablecells")
                            }
                        }

                    }
                }
                .padding(14)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))

                VStack(alignment: .leading, spacing: 8) {
                    Text(L10n.string("section.suggested_commands"))
                        .font(.headline)
                    CommandLine(text: "cnb board view")
                    CommandLine(text: "cnb pending")
                    CommandLine(text: "cnb ps")
                }
                .padding(14)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
            .padding(.top, DetailChromeMetrics.contentTopPadding)
            .padding(.horizontal, DetailChromeMetrics.contentHorizontalPadding)
            .padding(.bottom, DetailChromeMetrics.contentBottomPadding)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .navigationTitle("")
    }
}

private struct DetailMetric: View {
    let title: String
    let value: Int
    let systemImage: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Image(systemName: systemImage)
                .foregroundStyle(.secondary)
            Text("\(value)")
                .font(.system(.title2, design: .rounded).weight(.semibold))
                .monospacedDigit()
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(14)
        .frame(minHeight: 104, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct CommandLine: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.system(.body, design: .monospaced))
            .textSelection(.enabled)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(8)
            .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
    }
}
