import AppKit
import SwiftUI

struct ScrollForwardingGlassHost<Content: View>: NSViewRepresentable {
    private let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    func makeNSView(context: Context) -> ScrollForwardingHostingView<Content> {
        let view = ScrollForwardingHostingView(rootView: content)
        view.translatesAutoresizingMaskIntoConstraints = false
        return view
    }

    func updateNSView(_ nsView: ScrollForwardingHostingView<Content>, context: Context) {
        nsView.rootView = content
    }
}

final class ScrollForwardingHostingView<Content: View>: NSHostingView<Content> {
    override func scrollWheel(with event: NSEvent) {
        if forwardScrollWheel(event) {
            return
        }
        super.scrollWheel(with: event)
    }

    private func forwardScrollWheel(_ event: NSEvent) -> Bool {
        guard let contentView = window?.contentView,
              let scrollView = scrollView(at: event.locationInWindow, in: contentView) else {
            return false
        }
        scrollView.scrollWheel(with: event)
        return true
    }

    private func scrollView(at windowPoint: NSPoint, in view: NSView) -> NSScrollView? {
        guard view !== self,
              !isDescendant(view, of: self),
              !view.isHidden,
              view.alphaValue > 0 else {
            return nil
        }

        let localPoint = view.convert(windowPoint, from: nil)
        guard view.bounds.insetBy(dx: -1, dy: -1).contains(localPoint) else {
            return nil
        }

        for subview in view.subviews.reversed() {
            if let scrollView = scrollView(at: windowPoint, in: subview) {
                return scrollView
            }
        }

        return view as? NSScrollView
    }

    private func isDescendant(_ view: NSView, of ancestor: NSView) -> Bool {
        var candidate = view.superview
        while let current = candidate {
            if current === ancestor {
                return true
            }
            candidate = current.superview
        }
        return false
    }
}
