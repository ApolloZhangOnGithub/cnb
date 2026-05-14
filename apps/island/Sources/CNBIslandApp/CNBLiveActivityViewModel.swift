import Foundation

@MainActor
final class CNBLiveActivityViewModel: ObservableObject {
    @Published private(set) var state: CNBLiveState = .fallback
    @Published var message: String?

    private let reader = CNBLiveStateReader()
    private var didAutostart = false

    func reload() {
        do {
            state = try reader.read()
            message = localized("message.loaded")
        } catch {
            state = .fallback
            message = localized("message.fallbackFormat", error.localizedDescription)
        }
    }

    func startActivity() async {
        do {
            let id = try CNBLiveActivityController.start(with: state)
            message = localized("message.activityStartedFormat", id)
            print("CNB Live Activity started: \(id)")
        } catch {
            message = localized("message.startFailedFormat", error.localizedDescription)
            print("CNB Live Activity start failed: \(error.localizedDescription)")
        }
    }

    func updateActivity() async {
        reload()
        await CNBLiveActivityController.update(with: state)
        message = localized("message.activityUpdated")
    }

    func endActivity() async {
        await CNBLiveActivityController.end(with: state)
        message = localized("message.activityEnded")
    }

    func autostartIfRequested() async {
        guard !didAutostart else {
            return
        }
        didAutostart = true

        let environment = ProcessInfo.processInfo.environment
        guard environment["CNB_AUTOSTART_ACTIVITY"] == "1" else {
            return
        }

        reload()

        if environment["CNB_RESET_ACTIVITY"] == "1" {
            await CNBLiveActivityController.endAll(with: state)
        }

        await startActivity()
    }

    private func localized(_ key: String) -> String {
        NSLocalizedString(key, comment: "")
    }

    private func localized(_ key: String, _ arguments: CVarArg...) -> String {
        let format = NSLocalizedString(key, comment: "")
        return String(format: format, locale: Locale.current, arguments: arguments)
    }
}
