import AppKit
import SwiftUI

struct ContentView: View {
    @ObservedObject var store: CNBStateStore
    @ObservedObject var feishuViewModel: FeishuChatViewModel
    @ObservedObject var feishuTUIViewModel: FeishuTUIViewModel
    @StateObject private var adminTodoViewModel = CNBAdminTodoViewModel()
    @State private var columnVisibility: NavigationSplitViewVisibility = .all

    var body: some View {
        NavigationSplitView(columnVisibility: $columnVisibility) {
            SidebarView(store: store)
        } detail: {
            ZStack(alignment: .top) {
                DetailView(
                    store: store,
                    feishuViewModel: feishuViewModel,
                    feishuTUIViewModel: feishuTUIViewModel,
                    adminTodoViewModel: adminTodoViewModel
                )
                .liquidGlassContentPlane()

                if #available(macOS 26.0, *) {
                    ScrollForwardingGlassHost {
                        FloatingFeatureGlassBar(store: store)
                    }
                    .frame(width: DetailChromeMetrics.floatingBarWidth, height: DetailChromeMetrics.floatingBarHeight)
                    .padding(.top, DetailChromeMetrics.floatingBarTopPadding)
                    .zIndex(10)
                }
            }
        }
        .navigationSplitViewStyle(.balanced)
        .onAppear {
            columnVisibility = .all
            adminTodoViewModel.reload()
        }
        .liquidGlassToolbarBackground()
        .toolbar {
            ToolbarItem(placement: .principal) {
                if #available(macOS 26.0, *) {
                    EmptyView()
                } else {
                    LegacyFeatureSegmentedPicker(store: store)
                }
            }

            ToolbarItem(placement: .primaryAction) {
                SettingsToolbarButton(store: store)
            }
        }
        .background(WindowGlassConfigurator().frame(width: 0, height: 0))
    }
}

private struct FeatureTab: Identifiable {
    let id: String
    let title: String
    let systemImage: String

    static var all: [FeatureTab] {
        [
            FeatureTab(id: CNBStateStore.overviewSelectionID, title: L10n.string("nav.overview"), systemImage: "gauge.with.dots.needle.50percent"),
            FeatureTab(id: CNBStateStore.feishuTUISelectionID, title: L10n.string("nav.feishu_tui"), systemImage: "terminal"),
            FeatureTab(id: CNBStateStore.feishuSelectionID, title: L10n.string("nav.feishu_chat"), systemImage: "bubble.left.and.bubble.right")
        ]
    }
}

@available(macOS 26.0, *)
private struct FloatingFeatureGlassBar: View {
    @ObservedObject var store: CNBStateStore
    @Namespace private var glassNamespace

    var body: some View {
        GlassEffectContainer(spacing: 8) {
            HStack(spacing: 0) {
                ForEach(FeatureTab.all) { tab in
                    tabButton(tab)
                }
            }
            .padding(4)
            .glassEffect(.regular, in: Capsule())
        }
        .fixedSize()
        .help(L10n.string("nav.feature_switcher"))
    }

    private func tabButton(_ tab: FeatureTab) -> some View {
        Button {
            select(tab)
        } label: {
            ZStack {
                if store.selectedProjectID == tab.id {
                    Capsule()
                        .glassEffect(.regular.interactive(), in: Capsule())
                        .glassEffectID("feature-selection", in: glassNamespace)
                        .glassEffectTransition(.matchedGeometry)
                }

                Label(tab.title, systemImage: tab.systemImage)
                    .labelStyle(.titleAndIcon)
                    .font(.caption.weight(store.selectedProjectID == tab.id ? .semibold : .medium))
                    .foregroundStyle(store.selectedProjectID == tab.id ? Color.primary : Color.secondary)
                    .lineLimit(1)
            }
            .frame(width: 134, height: 32)
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(tab.title)
    }

    private func select(_ tab: FeatureTab) {
        withAnimation(.spring(response: 0.22, dampingFraction: 0.84)) {
            store.selectedProjectID = tab.id
        }
    }
}

private struct LegacyFeatureSegmentedPicker: View {
    @ObservedObject var store: CNBStateStore

    var body: some View {
        Picker("", selection: $store.selectedProjectID) {
            ForEach(FeatureTab.all) { tab in
                Text(tab.title)
                    .tag(tab.id)
            }
        }
        .pickerStyle(.segmented)
        .labelsHidden()
        .controlSize(.small)
        .frame(width: 420)
        .help(L10n.string("nav.feature_switcher"))
    }
}

private struct SettingsToolbarButton: View {
    @ObservedObject var store: CNBStateStore

    var body: some View {
        if #available(macOS 26.0, *) {
            Button {
                store.selectedProjectID = CNBStateStore.settingsSelectionID
            } label: {
                Image(systemName: "gearshape")
            }
            .buttonStyle(.plain)
            .padding(8)
            .glassEffect(.regular.interactive(), in: Circle())
            .controlSize(.small)
            .help(L10n.string("nav.settings"))
        } else {
            Button {
                store.selectedProjectID = CNBStateStore.settingsSelectionID
            } label: {
                Image(systemName: "gearshape")
            }
            .help(L10n.string("nav.settings"))
        }
    }
}

private struct WindowGlassConfigurator: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let view = NSView(frame: .zero)
        DispatchQueue.main.async {
            configure(view.window)
        }
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        DispatchQueue.main.async {
            configure(nsView.window)
        }
    }

    private func configure(_ window: NSWindow?) {
        guard let window else {
            return
        }
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.styleMask.insert(.fullSizeContentView)
        window.toolbarStyle = .unifiedCompact
    }
}

private extension View {
    @ViewBuilder
    func liquidGlassToolbarBackground() -> some View {
        if #available(macOS 15.0, *) {
            toolbarBackgroundVisibility(.hidden, for: .windowToolbar)
        } else {
            self
        }
    }

    @ViewBuilder
    func liquidGlassContentPlane() -> some View {
        if #available(macOS 26.0, *) {
            ignoresSafeArea(.container, edges: .top)
                .backgroundExtensionEffect()
        } else {
            self
        }
    }
}
