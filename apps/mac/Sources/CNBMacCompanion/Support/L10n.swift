import Foundation
import SwiftUI

enum L10n {
    private static let bundle: Bundle = {
        let language = ProcessInfo.processInfo.environment["CNB_COMPANION_LANGUAGE"]
            ?? UserDefaults.standard.string(forKey: "CNBCompanionLanguage")
            ?? "zh-Hans"

        if let path = Bundle.module.path(forResource: language, ofType: "lproj"),
           let localizedBundle = Bundle(path: path) {
            return localizedBundle
        }

        return Bundle.module
    }()

    static func string(_ key: String.LocalizationValue) -> String {
        String(localized: key, bundle: bundle)
    }

    static func format(_ key: String.LocalizationValue, _ arguments: CVarArg...) -> String {
        String(format: string(key), locale: Locale.current, arguments: arguments)
    }

    static func key(_ key: String) -> LocalizedStringKey {
        LocalizedStringKey(key)
    }
}
