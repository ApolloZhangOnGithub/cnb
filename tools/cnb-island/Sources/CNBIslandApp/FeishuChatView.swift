import SwiftUI

struct FeishuChatView: View {
    @ObservedObject var viewModel: FeishuChatViewModel
    @FocusState private var composerFocused: Bool

    var body: some View {
        VStack(spacing: 8) {
            header
            transcript
            composer
        }
        .padding(.top, 8)
        .background(Color(.systemGroupedBackground))
        .onAppear {
            viewModel.startAutoSync()
            viewModel.reloadRuntimeSettings()
        }
        .onDisappear {
            viewModel.stopAutoSync()
        }
    }

    private var header: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text("feishu.chat.title")
                    .font(.headline)
                    .foregroundStyle(.primary)
                Text(viewModel.statusMessage)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            Spacer()
            Image(systemName: viewModel.settings.isReady ? "macbook.and.iphone" : "arrow.triangle.2.circlepath")
                .foregroundStyle(viewModel.settings.isReady ? .green : .secondary)
                .frame(width: 32, height: 32)
            Button {
                Task { await viewModel.refreshRecentMessages() }
            } label: {
                Image(systemName: viewModel.isRefreshing ? "arrow.triangle.2.circlepath" : "arrow.clockwise")
                    .frame(width: 32, height: 32)
            }
            .buttonStyle(.borderless)
            .disabled(viewModel.isRefreshing)
            .accessibilityLabel(Text("feishu.action.refresh"))
        }
        .padding(12)
        .cnbGlassPanel(cornerRadius: 24, tint: Color(.secondarySystemBackground).opacity(0.18))
        .padding(.horizontal, 12)
    }

    private var transcript: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(viewModel.messages) { message in
                        FeishuChatBubble(message: message)
                            .id(message.id)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 14)
            }
            .scrollDismissesKeyboard(.interactively)
            .background(Color(.systemGroupedBackground))
            .contentShape(Rectangle())
            .onTapGesture {
                composerFocused = false
            }
            .onChange(of: viewModel.messages.count) { _, _ in
                scrollToBottom(proxy)
            }
        }
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField(composerPlaceholder, text: $viewModel.draft, axis: .vertical)
                .textFieldStyle(.plain)
                .lineLimit(1...5)
                .focused($composerFocused)
                .disabled(!viewModel.settings.isReady || viewModel.isSending)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(textFieldBackground, in: RoundedRectangle(cornerRadius: 18))
                .opacity(viewModel.settings.isReady ? 1 : 0.58)
                .onSubmit {
                    guard viewModel.canSend else {
                        return
                    }
                    composerFocused = false
                    Task { await viewModel.sendDraft() }
                }

            Button {
                composerFocused = false
                Task { await viewModel.sendDraft() }
            } label: {
                Image(systemName: viewModel.isSending ? "hourglass" : "paperplane.fill")
                    .frame(width: 36, height: 36)
            }
            .cnbProminentSendButton()
            .disabled(!viewModel.canSend)
            .accessibilityLabel(Text("feishu.action.send"))
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .cnbGlassPanel(cornerRadius: 30, tint: Color.accentColor.opacity(0.08))
        .padding(.horizontal, 12)
        .padding(.bottom, 10)
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("feishu.action.keyboardDone") {
                    composerFocused = false
                }
            }
        }
    }

    private var composerPlaceholder: LocalizedStringKey {
        viewModel.settings.isReady ? "feishu.composer.placeholder" : "feishu.composer.waiting"
    }

    private var textFieldBackground: Color {
        viewModel.settings.isReady
            ? Color(.secondarySystemBackground)
            : Color(.tertiarySystemBackground)
    }

    private func scrollToBottom(_ proxy: ScrollViewProxy) {
        guard let id = viewModel.messages.last?.id else {
            return
        }
        withAnimation(.easeOut(duration: 0.2)) {
            proxy.scrollTo(id, anchor: .bottom)
        }
    }
}

private extension View {
    @ViewBuilder
    func cnbGlassPanel(cornerRadius: CGFloat, tint: Color) -> some View {
        if #available(iOS 26.0, *) {
            self
                .background {
                    RoundedRectangle(cornerRadius: cornerRadius)
                        .fill(.clear)
                        .glassEffect(.regular.tint(tint).interactive(), in: RoundedRectangle(cornerRadius: cornerRadius))
                }
        } else {
            self
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: cornerRadius))
        }
    }

    @ViewBuilder
    func cnbProminentSendButton() -> some View {
        if #available(iOS 26.0, *) {
            self
                .buttonStyle(.glassProminent)
        } else {
            self
                .buttonStyle(.borderedProminent)
                .clipShape(Circle())
        }
    }
}

private struct FeishuChatBubble: View {
    var message: FeishuChatMessage

    var body: some View {
        HStack(alignment: .bottom) {
            if message.role == .user {
                Spacer(minLength: 48)
            }

            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 4) {
                Text(message.text)
                    .font(.body)
                    .foregroundStyle(foreground)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                    .background(background, in: RoundedRectangle(cornerRadius: 8))
                    .textSelection(.enabled)

                HStack(spacing: 4) {
                    if message.deliveryState == .sending {
                        ProgressView()
                            .controlSize(.mini)
                    }
                    Text(statusText)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            if message.role != .user {
                Spacer(minLength: 48)
            }
        }
    }

    private var background: Color {
        switch message.role {
        case .user:
            Color.accentColor
        case .assistant:
            Color(.secondarySystemBackground)
        case .system:
            Color(.tertiarySystemBackground)
        }
    }

    private var foreground: Color {
        message.role == .user ? .white : .primary
    }

    private var statusText: LocalizedStringKey {
        switch message.deliveryState {
        case .sending:
            "feishu.delivery.sending"
        case .sent:
            message.senderLabel.isEmpty ? "feishu.delivery.sent" : LocalizedStringKey(message.senderLabel)
        case .failed:
            "feishu.delivery.failed"
        case .local:
            "feishu.delivery.local"
        }
    }
}
