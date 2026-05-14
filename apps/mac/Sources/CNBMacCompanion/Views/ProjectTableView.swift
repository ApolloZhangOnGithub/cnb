import SwiftUI

struct ProjectTableView: View {
    let title: String
    let projects: [CNBProjectSummary]
    let onSelect: (CNBProjectSummary) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.headline)

            if projects.isEmpty {
                ContentUnavailableView(
                    L10n.string("empty.no_boards.title"),
                    systemImage: "folder.badge.questionmark",
                    description: Text(L10n.string("empty.no_boards.description"))
                )
                .frame(maxWidth: .infinity, minHeight: 180)
            } else {
                VStack(spacing: 0) {
                    ProjectTableHeader()
                    Divider()
                    ForEach(projects) { project in
                        Button {
                            onSelect(project)
                        } label: {
                            ProjectListRow(project: project)
                        }
                        .buttonStyle(.plain)
                        .contentShape(Rectangle())

                        if project.id != projects.last?.id {
                            Divider()
                                .padding(.leading, 42)
                        }
                    }
                }
                .padding(14)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
        }
    }
}

private struct ProjectTableHeader: View {
    var body: some View {
        HStack(spacing: 12) {
            Text(L10n.string("column.project"))
                .frame(maxWidth: .infinity, alignment: .leading)
            Text(L10n.string("column.status"))
                .frame(width: 156, alignment: .leading)
            Text(L10n.string("column.pending"))
                .frame(width: 64, alignment: .leading)
            Text(L10n.string("column.tasks"))
                .frame(width: 56, alignment: .leading)
            Text(L10n.string("column.unread"))
                .frame(width: 56, alignment: .leading)
            Text(L10n.string("column.sessions"))
                .frame(width: 64, alignment: .leading)
            Text(L10n.string("column.last_active"))
                .frame(width: 86, alignment: .leading)
            Image(systemName: "chevron.right")
                .opacity(0)
                .frame(width: 16)
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .padding(.bottom, 8)
    }
}

private struct ProjectListRow: View {
    let project: CNBProjectSummary

    var body: some View {
        HStack(spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: project.status.systemImage)
                    .foregroundStyle(project.status.tint)
                    .frame(width: 22)

                VStack(alignment: .leading, spacing: 2) {
                    Text(project.name)
                        .font(.body.weight(.medium))
                        .lineLimit(1)
                    Text(project.path)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Text(project.statusReason)
                .font(.caption)
                .foregroundStyle(project.status == .attention || project.status == .blocked ? project.status.tint : Color.secondary)
                .lineLimit(2)
                .frame(width: 156, alignment: .leading)

            CountText(value: project.pendingActions)
            CountText(value: project.taskTotal)
            CountText(value: project.unreadMessages)
            CountText(value: project.sessions)

            Text(Formatters.relative(project.lastActive))
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .frame(width: 86, alignment: .leading)

            Image(systemName: "chevron.right")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.tertiary)
                .frame(width: 16)
        }
        .padding(.vertical, 10)
    }
}

private struct CountText: View {
    let value: Int

    var body: some View {
        Text("\(value)")
            .font(.body.monospacedDigit())
            .foregroundStyle(value > 0 ? .primary : .secondary)
            .frame(width: 56, alignment: .leading)
    }
}
