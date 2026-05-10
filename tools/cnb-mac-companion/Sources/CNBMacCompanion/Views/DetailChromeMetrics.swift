import SwiftUI

enum DetailChromeMetrics {
    static let floatingBarWidth: CGFloat = 420
    static let floatingBarHeight: CGFloat = 44
    static let floatingBarTopPadding: CGFloat = 6
    static let contentHorizontalPadding: CGFloat = 24
    static let contentBottomPadding: CGFloat = 24

    static var contentTopPadding: CGFloat {
        if #available(macOS 26.0, *) {
            return 108
        }
        return 24
    }
}
