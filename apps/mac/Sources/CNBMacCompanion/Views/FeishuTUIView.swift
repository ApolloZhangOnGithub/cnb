import SwiftUI
import WebKit

struct FeishuTUIView: View {
    @ObservedObject var viewModel: FeishuTUIViewModel

    var body: some View {
        content
        .navigationTitle("")
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                Button {
                    viewModel.reload()
                } label: {
                    Image(systemName: viewModel.isLoading ? "hourglass" : "arrow.clockwise")
                }
                .help(L10n.string("feishu.tui.action.reload"))
                .disabled(viewModel.isLoading)

                Button {
                    viewModel.openInBrowser()
                } label: {
                    Image(systemName: "globe")
                }
                .help(L10n.string("feishu.tui.action.open_browser"))
                .disabled(!viewModel.canOpenInBrowser)
            }
        }
        .onAppear {
            viewModel.startIfNeeded()
        }
    }

    @ViewBuilder
    private var content: some View {
        if let url = viewModel.url {
            FeishuTUIWebView(url: url)
                .id(url)
        } else {
            VStack(spacing: 12) {
                if viewModel.isLoading {
                    ProgressView()
                        .controlSize(.regular)
                    Text(L10n.string("feishu.tui.loading.title"))
                        .font(.headline)
                    Text(viewModel.statusText)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                if let errorMessage = viewModel.errorMessage {
                    Text(errorMessage)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .textSelection(.enabled)
                        .frame(maxWidth: 520)
                    Button(L10n.string("feishu.tui.action.reload")) {
                        viewModel.reload()
                    }
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

private struct FeishuTUIWebView: NSViewRepresentable {
    let url: URL

    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        let preferences = WKWebpagePreferences()
        preferences.allowsContentJavaScript = true
        configuration.defaultWebpagePreferences = preferences

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.load(request(for: url))
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        guard webView.url != url else {
            return
        }
        webView.load(request(for: url))
    }

    private func request(for url: URL) -> URLRequest {
        URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 15)
    }
}
