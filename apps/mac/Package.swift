// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "CNBMacCompanion",
    defaultLocalization: "zh-Hans",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "CNBMacCompanion", targets: ["CNBMacCompanion"])
    ],
    targets: [
        .executableTarget(
            name: "CNBMacCompanion",
            path: "Sources/CNBMacCompanion",
            resources: [
                .process("Resources")
            ]
        ),
        .testTarget(
            name: "CNBMacCompanionTests",
            dependencies: ["CNBMacCompanion"],
            path: "Tests/CNBMacCompanionTests"
        )
    ]
)
