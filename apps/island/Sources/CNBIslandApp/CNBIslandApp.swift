import SwiftUI

@main
struct CNBIslandApp: App {
    @StateObject private var viewModel = CNBLiveActivityViewModel()

    var body: some Scene {
        WindowGroup {
            ContentView(viewModel: viewModel)
        }
    }
}
