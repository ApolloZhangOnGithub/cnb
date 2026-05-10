import Foundation

@MainActor
final class CNBStateStore: ObservableObject {
    nonisolated static let overviewSelectionID = "__cnb_overview__"
    nonisolated static let feishuSelectionID = "__cnb_feishu_chat__"
    nonisolated static let feishuTUISelectionID = "__cnb_feishu_tui__"
    nonisolated static let settingsSelectionID = "__cnb_settings__"

    @Published private(set) var snapshot: CNBSnapshot = .empty
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?
    @Published var selectedProjectID: String = CNBStateStore.feishuSelectionID

    private let reader = CNBStateReader()
    private var autoRefreshTimer: Timer?

    deinit {
        autoRefreshTimer?.invalidate()
    }

    var selectedProject: CNBProjectSummary? {
        guard selectedProjectID != Self.overviewSelectionID,
              selectedProjectID != Self.feishuSelectionID,
              selectedProjectID != Self.feishuTUISelectionID,
              selectedProjectID != Self.settingsSelectionID else {
            return nil
        }
        return snapshot.projects.first { $0.id == selectedProjectID }
    }

    var isOverviewSelected: Bool {
        selectedProjectID == Self.overviewSelectionID
    }

    var isFeishuSelected: Bool {
        selectedProjectID == Self.feishuSelectionID
    }

    var isFeishuTUISelected: Bool {
        selectedProjectID == Self.feishuTUISelectionID
    }

    var isSettingsSelected: Bool {
        selectedProjectID == Self.settingsSelectionID
    }

    func startAutoRefresh(interval: TimeInterval = 5) {
        guard autoRefreshTimer == nil else {
            return
        }
        refresh()
        autoRefreshTimer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.refresh()
            }
        }
    }

    func refresh() {
        guard !isLoading else {
            return
        }

        isLoading = true
        errorMessage = nil

        let reader = self.reader
        Task {
            let result: Result<CNBSnapshot, Error> = await Task.detached(priority: .userInitiated) {
                do {
                    return .success(try reader.read())
                } catch {
                    return .failure(error)
                }
            }.value

            switch result {
            case .success(let snapshot):
                self.snapshot = snapshot
                if selectedProjectID != Self.overviewSelectionID,
                   selectedProjectID != Self.feishuSelectionID,
                   selectedProjectID != Self.feishuTUISelectionID,
                   selectedProjectID != Self.settingsSelectionID,
                   !snapshot.projects.contains(where: { $0.id == selectedProjectID }) {
                    self.selectedProjectID = Self.overviewSelectionID
                }
            case .failure(let error):
                self.errorMessage = error.localizedDescription
            }

            self.isLoading = false
        }
    }
}
