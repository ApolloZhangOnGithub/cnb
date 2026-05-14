import SwiftUI

struct FeishuChatView: View {
    @ObservedObject var viewModel: FeishuChatViewModel

    var body: some View {
        VStack(spacing: 0) {
            transcript
            composer
        }
        .navigationTitle("")
        .onAppear {
            viewModel.startAutoSync()
        }
    }

    private var transcript: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    if viewModel.didLoadInitialHistory {
                        FeishuHistoryLoaderRow(
                            hasMoreHistory: viewModel.hasMoreHistory,
                            isLoadingOlder: viewModel.isLoadingOlder
                        )
                        .onAppear {
                            Task { await viewModel.loadOlderMessages() }
                        }
                    }

                    ForEach(viewModel.messages) { message in
                        FeishuChatBubble(message: message)
                            .id(message.id)
                    }
                }
                .padding(.top, DetailChromeMetrics.contentTopPadding)
                .padding(.horizontal, 20)
                .padding(.bottom, 16)
            }
            .onChange(of: viewModel.scrollRequest?.id) { _, _ in
                handleScrollRequest(proxy)
            }
        }
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField(L10n.string("feishu.composer.placeholder"), text: $viewModel.draft, axis: .vertical)
                .textFieldStyle(.plain)
                .lineLimit(1...6)
                .padding(.horizontal, 12)
                .padding(.vertical, 9)
                .frame(minHeight: 38)
                .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .stroke(Color(nsColor: .separatorColor), lineWidth: 0.5)
                }

            ComposerSendButton(viewModel: viewModel)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .background(.thinMaterial)
        .overlay(alignment: .top) {
            Divider().opacity(0.55)
        }
    }

    private func handleScrollRequest(_ proxy: ScrollViewProxy) {
        guard let request = viewModel.scrollRequest else {
            return
        }
        let anchor: UnitPoint = request.anchor == .bottom ? .bottom : .top
        if request.animated {
            withAnimation(.easeOut(duration: 0.2)) {
                proxy.scrollTo(request.messageID, anchor: anchor)
            }
        } else {
            proxy.scrollTo(request.messageID, anchor: anchor)
        }
    }

}

private struct ComposerSendButton: View {
    @ObservedObject var viewModel: FeishuChatViewModel

    var body: some View {
        Button {
            Task { await viewModel.sendDraft() }
        } label: {
            Image(systemName: viewModel.isSending ? "hourglass" : "arrow.up")
                .font(.system(size: 15, weight: .semibold))
                .frame(width: 36, height: 36)
        }
        .keyboardShortcut(.return, modifiers: [.command])
        .modifier(ComposerSendButtonStyle())
        .help(L10n.string("feishu.action.send"))
        .disabled(!viewModel.canSend)
        .opacity(viewModel.canSend ? 1 : 0.45)
    }
}

private struct ComposerSendButtonStyle: ViewModifier {
    func body(content: Content) -> some View {
        if #available(macOS 26.0, *) {
            content
                .buttonStyle(.plain)
                .glassEffect(.regular.interactive(), in: Circle())
        } else {
            content
                .buttonStyle(.borderless)
        }
    }
}

private struct FeishuHistoryLoaderRow: View {
    let hasMoreHistory: Bool
    let isLoadingOlder: Bool

    var body: some View {
        HStack {
            Spacer()
            if isLoadingOlder {
                ProgressView()
                    .controlSize(.small)
                Text(L10n.string("feishu.history.loading"))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else if hasMoreHistory {
                Text(L10n.string("feishu.history.load_more"))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Text(L10n.string("feishu.history.no_more"))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .frame(minHeight: 28)
    }
}

private struct FeishuChatBubble: View {
    let message: FeishuChatMessage

    var body: some View {
        HStack(alignment: .bottom) {
            if message.role == .user {
                Spacer(minLength: 120)
            }

            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 4) {
                Text(message.text)
                    .font(.body)
                    .foregroundStyle(foreground)
                    .textSelection(.enabled)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 9)
                    .background(background, in: RoundedRectangle(cornerRadius: 18, style: .continuous))

                HStack(spacing: 5) {
                    if message.deliveryState == .sending {
                        ProgressView()
                            .controlSize(.mini)
                    }
                    Text(statusText)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: 560, alignment: message.role == .user ? .trailing : .leading)

            if message.role != .user {
                Spacer(minLength: 120)
            }
        }
    }

    private var background: Color {
        switch message.role {
        case .user:
            Color.accentColor
        case .assistant:
            Color(nsColor: .windowBackgroundColor)
        case .system:
            Color(nsColor: .controlBackgroundColor)
        }
    }

    private var foreground: Color {
        message.role == .user ? .white : .primary
    }

    private var statusText: String {
        switch message.deliveryState {
        case .sending:
            L10n.string("feishu.delivery.sending")
        case .sent:
            message.senderLabel.isEmpty ? L10n.string("feishu.delivery.sent") : message.senderLabel
        case .failed:
            L10n.string("feishu.delivery.failed")
        case .local:
            L10n.string("feishu.delivery.local")
        }
    }
}
