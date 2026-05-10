import SwiftUI

@main
struct CNBMacCompanionApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var store = CNBStateStore()
    @StateObject private var feishuViewModel = FeishuChatViewModel()
    @StateObject private var feishuTUIViewModel = FeishuTUIViewModel()

    var body: some Scene {
        Window("CNB Companion", id: "main") {
            ContentView(
                store: store,
                feishuViewModel: feishuViewModel,
                feishuTUIViewModel: feishuTUIViewModel
            )
                .frame(minWidth: 880, minHeight: 560)
                .onAppear {
                    store.startAutoRefresh()
                }
        }
        .defaultSize(width: 980, height: 680)
        .commands {
            CommandMenu("CNB") {
                Button(L10n.string("action.open_cnb_home")) {
                    MacActionService.openCNBHome()
                }
                .keyboardShortcut("o", modifiers: [.command, .shift])

                Button(L10n.string("nav.feishu_tui")) {
                    store.selectedProjectID = CNBStateStore.feishuTUISelectionID
                    NSApp.activate(ignoringOtherApps: true)
                }
                .keyboardShortcut("t", modifiers: [.command, .shift])

                Button(L10n.string("nav.feishu_chat")) {
                    store.selectedProjectID = CNBStateStore.feishuSelectionID
                    NSApp.activate(ignoringOtherApps: true)
                }
                .keyboardShortcut("f", modifiers: [.command, .shift])

                Button(L10n.string("nav.settings")) {
                    store.selectedProjectID = CNBStateStore.settingsSelectionID
                    NSApp.activate(ignoringOtherApps: true)
                }
                .keyboardShortcut(",", modifiers: [.command])
            }
        }

        MenuBarExtra {
            MenuBarContentView(store: store)
        } label: {
            Label(menuBarTitle, systemImage: store.snapshot.status.systemImage)
                .symbolRenderingMode(.hierarchical)
        }
        .menuBarExtraStyle(.menu)
    }

    private var menuBarTitle: String {
        let snapshot = store.snapshot
        if snapshot.pendingActions > 0 {
            return "\(snapshot.pendingActions)"
        }
        if snapshot.activeTasks > 0 {
            return "\(snapshot.activeTasks)"
        }
        return "CNB"
    }
}
