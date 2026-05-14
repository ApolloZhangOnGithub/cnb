import SwiftUI

struct DetailView: View {
    @ObservedObject var store: CNBStateStore
    @ObservedObject var feishuViewModel: FeishuChatViewModel
    @ObservedObject var feishuTUIViewModel: FeishuTUIViewModel
    @ObservedObject var adminTodoViewModel: CNBAdminTodoViewModel

    var body: some View {
        Group {
            if store.isSettingsSelected {
                FeishuSettingsView(viewModel: feishuViewModel)
            } else if store.isFeishuTUISelected {
                FeishuTUIView(viewModel: feishuTUIViewModel)
            } else if store.isFeishuSelected {
                FeishuChatView(viewModel: feishuViewModel)
            } else if let project = store.selectedProject {
                ProjectDetailView(project: project)
            } else {
                OverviewView(
                    store: store,
                    feishuViewModel: feishuViewModel,
                    adminTodoViewModel: adminTodoViewModel
                )
            }
        }
    }
}
