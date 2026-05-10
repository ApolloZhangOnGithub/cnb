import SwiftUI

enum CNBStatus: String, Codable, CaseIterable {
    case quiet
    case idle
    case working
    case attention
    case blocked
    case updating
    case missingBoard

    var title: String {
        switch self {
        case .quiet:
            return L10n.string("status.quiet")
        case .idle:
            return L10n.string("status.idle")
        case .working:
            return L10n.string("status.working")
        case .attention:
            return L10n.string("status.attention")
        case .blocked:
            return L10n.string("status.blocked")
        case .updating:
            return L10n.string("status.updating")
        case .missingBoard:
            return L10n.string("status.no_board")
        }
    }

    var systemImage: String {
        switch self {
        case .quiet:
            return "checkmark.circle.fill"
        case .idle:
            return "pause.circle.fill"
        case .working:
            return "bolt.fill"
        case .attention:
            return "exclamationmark.triangle.fill"
        case .blocked:
            return "hand.raised.fill"
        case .updating:
            return "arrow.triangle.2.circlepath"
        case .missingBoard:
            return "folder.badge.questionmark"
        }
    }

    var tint: Color {
        switch self {
        case .quiet:
            return .green
        case .idle:
            return .secondary
        case .working:
            return .blue
        case .attention:
            return .orange
        case .blocked:
            return .red
        case .updating:
            return .purple
        case .missingBoard:
            return .gray
        }
    }
}
