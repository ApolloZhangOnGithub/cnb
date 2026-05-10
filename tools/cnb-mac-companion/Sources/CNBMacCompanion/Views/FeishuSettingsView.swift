import SwiftUI

struct FeishuSettingsView: View {
    @ObservedObject var viewModel: FeishuChatViewModel

    var body: some View {
        Form {
            Section {
                settingsRow(L10n.string("feishu.settings.app_id"), text: $viewModel.settings.appID)
                settingsRow(L10n.string("feishu.settings.app_secret"), text: $viewModel.settings.appSecret, secure: true)
                settingsRow(L10n.string("feishu.settings.chat_id"), text: $viewModel.settings.chatID)
                settingsRow(L10n.string("feishu.settings.reply_message_id"), text: $viewModel.settings.replyMessageID)
                settingsRow(L10n.string("feishu.settings.webhook_url"), text: $viewModel.settings.webhookURL)
                settingsRow(L10n.string("feishu.settings.verification_token"), text: $viewModel.settings.verificationToken, secure: true)
            } header: {
                Text(L10n.string("feishu.settings.title"))
            } footer: {
                Text(L10n.string("feishu.settings.hint"))
            }

            HStack {
                Button {
                    viewModel.reloadRuntimeSettings()
                } label: {
                    Label(L10n.string("feishu.action.reload_config"), systemImage: "arrow.down.doc")
                }

                Spacer()

                Button {
                    viewModel.saveSettings()
                } label: {
                    Label(L10n.string("feishu.action.save"), systemImage: "checkmark")
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .formStyle(.grouped)
        .padding(24)
        .navigationTitle(L10n.string("nav.settings"))
    }

    @ViewBuilder
    private func settingsRow(_ label: String, text: Binding<String>, secure: Bool = false) -> some View {
        LabeledContent(label) {
            if secure {
                SecureField(label, text: text)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 320)
            } else {
                TextField(label, text: text)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 320)
            }
        }
    }
}
