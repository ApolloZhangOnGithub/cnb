import SwiftUI

struct SidebarView: View {
    @ObservedObject var store: CNBStateStore

    var body: some View {
        List(selection: projectSelection) {
            Section(L10n.string("section.projects")) {
                ForEach(store.snapshot.projects) { project in
                    ProjectSidebarRow(project: project)
                        .tag(project.id)
                }
            }
        }
        .listStyle(.sidebar)
        .navigationTitle(L10n.string("section.projects"))
    }

    private var projectSelection: Binding<String?> {
        Binding {
            store.selectedProjectID
        } set: { value in
            guard let value else {
                return
            }
            store.selectedProjectID = value
        }
    }
}

private struct ProjectSidebarRow: View {
    let project: CNBProjectSummary

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: project.status.systemImage)
                .foregroundStyle(project.status.tint)
                .frame(width: 16)

            VStack(alignment: .leading, spacing: 2) {
                Text(project.name)
                    .lineLimit(1)

                Text(project.summaryLine)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .help(project.path)
    }
}
