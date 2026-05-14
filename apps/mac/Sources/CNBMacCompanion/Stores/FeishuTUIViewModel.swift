import AppKit
import Darwin
import Foundation

@MainActor
final class FeishuTUIViewModel: ObservableObject {
    @Published private(set) var url: URL?
    @Published private(set) var isLoading = false
    @Published private(set) var statusText = L10n.string("feishu.tui.status.idle")
    @Published private(set) var errorMessage: String?

    private var serverProcess: Process?
    private var launchTask: Task<Void, Never>?
    private let portSearchCount = 10

    deinit {
        launchTask?.cancel()
        if serverProcess?.isRunning == true {
            serverProcess?.terminate()
        }
    }

    var canOpenInBrowser: Bool {
        url != nil
    }

    func startIfNeeded() {
        guard url == nil, !isLoading else {
            return
        }
        reload()
    }

    func reload() {
        launchTask?.cancel()
        stopOwnedServer()

        url = nil
        isLoading = true
        errorMessage = nil
        statusText = L10n.string("feishu.tui.status.starting")

        launchTask = Task { [weak self] in
            await self?.launch()
        }
    }

    func openInBrowser() {
        guard let url else {
            return
        }
        NSWorkspace.shared.open(url)
    }

    private func launch() async {
        let settings = FeishuConfigReader.loadWatchSettings()
        let configuredURL = settings.localURL(embedded: true)

        statusText = L10n.format("feishu.tui.status.checking_port", settings.port)
        if await probe(configuredURL) == .ready {
            markReady(url: configuredURL)
            return
        }

        guard let command = CNBCommandLocator.locate() else {
            markFailed(L10n.string("feishu.tui.error.cnb_not_found"))
            return
        }

        var lastError = L10n.string("feishu.tui.error.launch_failed")
        let lastPort = settings.port + portSearchCount - 1
        var busyPorts = 0
        var launchedServer = false
        for port in settings.port...lastPort {
            if Task.isCancelled {
                return
            }

            let candidateURL = settings.localURL(port: port, embedded: true)
            statusText = L10n.format("feishu.tui.status.checking_port", port)
            if await probe(candidateURL) == .ready {
                markReady(url: candidateURL)
                return
            }
            if !isPortAvailable(host: settings.bindHost, port: port) {
                busyPorts += 1
                statusText = L10n.format("feishu.tui.status.port_busy", port)
                lastError = L10n.format("feishu.tui.error.port_unavailable", port)
                continue
            }

            do {
                statusText = L10n.format("feishu.tui.status.starting_port", port)
                let process = try runWatchServer(command: command, settings: settings, port: port)
                launchedServer = true
                if await waitUntilReady(candidateURL, process: process) {
                    serverProcess = process
                    markReady(url: candidateURL)
                    return
                }
                if process.isRunning {
                    process.terminate()
                }
                lastError = L10n.format("feishu.tui.error.server_not_ready", port)
            } catch {
                lastError = error.localizedDescription
            }
        }

        if busyPorts == portSearchCount && !launchedServer {
            markFailed(L10n.format("feishu.tui.error.no_available_ports", settings.port, lastPort))
        } else {
            markFailed(lastError)
        }
    }

    private func runWatchServer(command: CNBCommand, settings: FeishuWatchSettings, port: Int) throws -> Process {
        let process = Process()
        process.executableURL = command.executableURL
        process.arguments = [
            "feishu",
            "--config",
            settings.configURL.path,
            "watch-serve",
            "--host",
            settings.bindHost,
            "--port",
            String(port)
        ]
        if !settings.projectRoot.trimmed.isEmpty {
            process.currentDirectoryURL = URL(fileURLWithPath: NSString(string: settings.projectRoot).expandingTildeInPath)
        } else {
            process.currentDirectoryURL = command.workingDirectoryURL
        }

        var environment = ProcessInfo.processInfo.environment
        if !settings.projectRoot.trimmed.isEmpty {
            environment["CNB_PROJECT"] = NSString(string: settings.projectRoot).expandingTildeInPath
        }
        process.environment = environment
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        try process.run()
        return process
    }

    private func waitUntilReady(_ url: URL, process: Process) async -> Bool {
        for _ in 0..<8 {
            if Task.isCancelled {
                return false
            }
            if await probe(url) == .ready {
                return true
            }
            if !process.isRunning {
                return false
            }
            try? await Task.sleep(nanoseconds: 200_000_000)
        }
        return false
    }

    private func probe(_ url: URL) async -> ProbeResult {
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.timeoutInterval = 1
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                return .offline
            }
            guard http.statusCode == 200 else {
                return .serverMismatch
            }
            return String(data: data, encoding: .utf8)?.contains("CNB TUI") == true ? .ready : .serverMismatch
        } catch {
            return .offline
        }
    }

    private func isPortAvailable(host: String, port: Int) -> Bool {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else {
            return false
        }
        defer { close(fd) }

        var reuse: Int32 = 1
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &reuse, socklen_t(MemoryLayout<Int32>.size))

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = in_port_t(port).bigEndian
        let bindHost = host == "::" ? "0.0.0.0" : host
        if inet_pton(AF_INET, bindHost, &address.sin_addr) != 1 {
            inet_pton(AF_INET, "127.0.0.1", &address.sin_addr)
        }

        return withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                bind(fd, sockaddrPointer, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0
            }
        }
    }

    private func markReady(url: URL) {
        self.url = url
        isLoading = false
        errorMessage = nil
        statusText = L10n.format("feishu.tui.status.ready", "\(url.host ?? "127.0.0.1"):\(url.port ?? 0)")
    }

    private func markFailed(_ detail: String) {
        isLoading = false
        url = nil
        errorMessage = detail
        statusText = L10n.format("feishu.tui.status.failed", detail)
    }

    private func stopOwnedServer() {
        if serverProcess?.isRunning == true {
            serverProcess?.terminate()
        }
        serverProcess = nil
    }
}

private enum ProbeResult: Sendable {
    case ready
    case serverMismatch
    case offline
}
