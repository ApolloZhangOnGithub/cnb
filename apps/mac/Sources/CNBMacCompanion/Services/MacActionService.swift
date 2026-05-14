import AppKit
import Foundation

enum MacActionService {
    static func openProjectFolder(_ project: CNBProjectSummary) {
        NSWorkspace.shared.open(URL(fileURLWithPath: project.path))
    }

    static func revealBoard(_ project: CNBProjectSummary) {
        guard let boardPath = project.boardPath else {
            return
        }
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: boardPath)])
    }

    static func openTerminal(atPath path: String) {
        let url = URL(fileURLWithPath: path)
        NSWorkspace.shared.open([url], withApplicationAt: terminalURL(), configuration: NSWorkspace.OpenConfiguration())
    }

    static func openCNBHome() {
        let url = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".cnb")
        NSWorkspace.shared.open(url)
    }

    private static func terminalURL() -> URL {
        URL(fileURLWithPath: "/System/Applications/Utilities/Terminal.app")
    }
}
