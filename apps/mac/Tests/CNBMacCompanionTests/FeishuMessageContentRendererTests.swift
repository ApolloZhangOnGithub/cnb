import XCTest
@testable import CNBMacCompanion

final class FeishuMessageContentRendererTests: XCTestCase {
    func testAppSenderRendersAsCLIOnAssistantSide() {
        XCTAssertEqual(FeishuMessageSenderMapper.label(senderType: "app"), "CLI")
        XCTAssertEqual(FeishuMessageSenderMapper.role(msgType: "text", senderType: "app"), .assistant)
    }

    func testUserSenderRendersOnUserSide() {
        XCTAssertEqual(FeishuMessageSenderMapper.label(senderType: "user"), "User")
        XCTAssertEqual(FeishuMessageSenderMapper.role(msgType: "text", senderType: "user"), .user)
    }

    func testPostMessageRendersTitleTextMentionAndLink() {
        let payload: [String: Any] = [
            "zh_cn": [
                "title": "部署提醒",
                "content": [
                    [
                        ["tag": "text", "text": "请处理 "],
                        ["tag": "at", "user_name": "Kezhen"],
                        ["tag": "text", "text": " "],
                        ["tag": "a", "text": "查看", "href": "https://example.com/build"],
                    ],
                ],
            ],
        ]

        let rendered = FeishuMessageContentRenderer.render(msgType: "post", payload: payload)

        XCTAssertTrue(rendered.contains("部署提醒"))
        XCTAssertTrue(
            rendered.contains("请处理 @Kezhen 查看 (https://example.com/build)"),
            rendered
        )
    }

    func testMediaMessagesRenderReadablePlaceholders() {
        XCTAssertEqual(
            FeishuMessageContentRenderer.render(msgType: "image", payload: ["image_key": "img_123"]),
            "[Image: img_123]"
        )
        XCTAssertEqual(
            FeishuMessageContentRenderer.render(msgType: "file", payload: ["file_name": "report.pdf"]),
            "[File: report.pdf]"
        )
    }
}
