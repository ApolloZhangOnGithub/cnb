import Foundation

struct CNBAdminTodoDocument: Hashable, Sendable {
    var title: String
    var sections: [CNBAdminTodoSection]
    var loadedAt: Date

    static var empty: CNBAdminTodoDocument {
        CNBAdminTodoDocument(title: "ADMIN_TO_DO", sections: [], loadedAt: Date())
    }

    var actionableSections: [CNBAdminTodoSection] {
        sections.filter(\.isActionable)
    }

    var primaryAction: CNBAdminTodoSection? {
        actionableSections.first
    }

    var currentReleaseSummary: String {
        sections
            .first { $0.heading.localizedCaseInsensitiveContains("release") }
            .flatMap(\.firstReadableLine)
            ?? "等待 Mac 同步发布状态。"
    }
}

struct CNBAdminTodoSection: Identifiable, Hashable, Sendable {
    var id: String
    var heading: String
    var paragraphs: [String]
    var bullets: [String]
    var codeBlocks: [String]

    var isActionable: Bool {
        let combined = ([heading] + paragraphs + bullets).joined(separator: "\n").lowercased()
        return combined.contains("remaining blocker")
            || combined.contains("next maintainer action")
            || combined.contains("optional maintainer action")
            || combined.contains("blocker")
            || combined.contains("action:")
            || combined.contains("action：")
            || combined.contains("enable")
            || combined.contains("dist-tag")
    }

    var firstReadableLine: String? {
        paragraphs.first { !$0.isEmpty } ?? bullets.first { !$0.isEmpty }
    }

    var summary: String {
        firstReadableLine ?? "打开后查看具体步骤。"
    }
}

@MainActor
final class CNBAdminTodoViewModel: ObservableObject {
    @Published private(set) var document: CNBAdminTodoDocument = .empty
    @Published private(set) var statusMessage = "等待 Mac 同步 ADMIN_TO_DO"
    @Published private(set) var isLoaded = false

    var hasActionableItems: Bool {
        !document.actionableSections.isEmpty
    }

    var primaryAction: CNBAdminTodoSection? {
        document.primaryAction
    }

    func reload() {
        guard let markdown = CNBRuntimeFileLocator.optionalString(named: "ADMIN_TO_DO.md"),
              !markdown.trimmed.isEmpty else {
            document = .empty
            statusMessage = "ADMIN_TO_DO 未同步到手机"
            isLoaded = false
            return
        }

        document = CNBAdminTodoParser.parse(markdown)
        isLoaded = true
        statusMessage = hasActionableItems ? "有维护待办需要处理" : "没有维护待办"
    }
}

private enum CNBAdminTodoParser {
    static func parse(_ markdown: String) -> CNBAdminTodoDocument {
        var title = "ADMIN_TO_DO"
        var sections: [CNBAdminTodoSection] = []
        var current = SectionBuilder(heading: "概览")
        var codeBuffer: [String] = []
        var isInCodeBlock = false

        for rawLine in markdown.components(separatedBy: .newlines) {
            let line = rawLine.trimmingCharacters(in: .whitespaces)

            if line.hasPrefix("```") {
                if isInCodeBlock {
                    current.codeBlocks.append(codeBuffer.joined(separator: "\n"))
                    codeBuffer.removeAll()
                }
                isInCodeBlock.toggle()
                continue
            }

            if isInCodeBlock {
                codeBuffer.append(rawLine)
                continue
            }

            if line.hasPrefix("# ") {
                title = strippedHeading(line)
                continue
            }

            if line.hasPrefix("## ") {
                appendIfNeeded(current, to: &sections)
                current = SectionBuilder(heading: strippedHeading(line))
                continue
            }

            guard !line.isEmpty else {
                continue
            }

            if line.hasPrefix("- ") {
                current.bullets.append(String(line.dropFirst(2)).trimmed)
            } else {
                current.paragraphs.append(line)
            }
        }

        if isInCodeBlock, !codeBuffer.isEmpty {
            current.codeBlocks.append(codeBuffer.joined(separator: "\n"))
        }
        appendIfNeeded(current, to: &sections)

        return CNBAdminTodoDocument(title: title, sections: sections, loadedAt: Date())
    }

    private static func strippedHeading(_ line: String) -> String {
        String(line.drop(while: { $0 == "#" || $0 == " " })).trimmed
    }

    private static func appendIfNeeded(_ builder: SectionBuilder, to sections: inout [CNBAdminTodoSection]) {
        guard builder.hasContent else {
            return
        }
        sections.append(builder.section)
    }

    private struct SectionBuilder {
        var heading: String
        var paragraphs: [String] = []
        var bullets: [String] = []
        var codeBlocks: [String] = []

        var hasContent: Bool {
            !paragraphs.isEmpty || !bullets.isEmpty || !codeBlocks.isEmpty
        }

        var section: CNBAdminTodoSection {
            CNBAdminTodoSection(
                id: heading,
                heading: heading,
                paragraphs: paragraphs,
                bullets: bullets,
                codeBlocks: codeBlocks
            )
        }
    }
}
