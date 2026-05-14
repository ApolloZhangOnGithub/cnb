import Foundation

enum Formatters {
    static let relativeDate: RelativeDateTimeFormatter = {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter
    }()

    static let time: DateFormatter = {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        formatter.dateStyle = .none
        return formatter
    }()

    static func relative(_ date: Date?) -> String {
        guard let date else {
            return L10n.string("time.never")
        }
        return relativeDate.localizedString(for: date, relativeTo: Date())
    }
}
