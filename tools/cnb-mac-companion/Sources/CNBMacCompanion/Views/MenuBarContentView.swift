import SwiftUI

struct MenuBarContentView: View {
    @ObservedObject var store: CNBStateStore
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: store.snapshot.status.systemImage)
                    .foregroundStyle(store.snapshot.status.tint)
                Text(store.snapshot.status.title)
                    .font(.headline)
            }

            Text(store.snapshot.detail)
                .font(.caption)
                .foregroundStyle(.secondary)

            Divider()

            MenuMetric(title: L10n.string("metric.pending"), value: store.snapshot.pendingActions)
            MenuMetric(title: L10n.string("metric.tasks"), value: store.snapshot.activeTasks)
            MenuMetric(title: L10n.string("metric.unread"), value: store.snapshot.unreadMessages)

            if !store.snapshot.topProjects.isEmpty {
                Divider()
                ForEach(store.snapshot.topProjects.prefix(4)) { project in
                    Button {
                        store.selectedProjectID = project.id
                        openMainWindow()
                    } label: {
                        Label(menuTitle(for: project), systemImage: project.status.systemImage)
                    }
                }
            }

            Divider()

            Button(L10n.string("action.open_companion")) {
                openMainWindow()
            }

            Button(L10n.string("nav.feishu_tui")) {
                store.selectedProjectID = CNBStateStore.feishuTUISelectionID
                openMainWindow()
            }

            Button(L10n.string("nav.feishu_chat")) {
                store.selectedProjectID = CNBStateStore.feishuSelectionID
                openMainWindow()
            }

            Button(L10n.string("action.open_cnb_home")) {
                MacActionService.openCNBHome()
            }

            Button(L10n.string("nav.settings")) {
                store.selectedProjectID = CNBStateStore.settingsSelectionID
                openMainWindow()
            }

            Divider()

            Button(L10n.string("action.quit_companion")) {
                NSApp.terminate(nil)
            }
            .keyboardShortcut("q")
        }
        .padding(4)
        .frame(width: 280, alignment: .leading)
        .onAppear {
            store.startAutoRefresh()
        }
    }

    private func openMainWindow() {
        openWindow(id: "main")
        NSApp.activate(ignoringOtherApps: true)
    }

    private func menuTitle(for project: CNBProjectSummary) -> String {
        let raw = "\(project.name): \(project.summaryLine)"
        if raw.count <= 30 {
            return raw
        }
        return String(raw.prefix(27)) + "..."
    }
}

private struct MenuMetric: View {
    let title: String
    let value: Int

    var body: some View {
        HStack {
            Text(title)
            Spacer()
            Text("\(value)")
                .monospacedDigit()
                .foregroundStyle(value > 0 ? .primary : .secondary)
        }
        .font(.caption)
    }
}
