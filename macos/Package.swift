// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "CutNotes",
    platforms: [.macOS(.v15)],
    products: [
        .library(name: "CutNotesCore", targets: ["CutNotesCore"]),
        .executable(name: "CutNotes", targets: ["CutNotesApp"]),
        .executable(name: "CutNotesLocal", targets: ["CutNotesLocal"]),
    ],
    dependencies: [
        .package(url: "https://github.com/aindaco1/record.git", exact: "1.2.2"),
        .package(url: "https://github.com/sparkle-project/Sparkle", exact: "2.9.6"),
    ],
    targets: [
        .target(name: "CutNotesCore"),
        .executableTarget(
            name: "CutNotesLocal",
            dependencies: [
                .product(name: "RecordCore", package: "record"),
                .product(name: "RecordSpeech", package: "record"),
            ]
        ),
        .executableTarget(
            name: "CutNotesApp",
            dependencies: [
                "CutNotesCore",
                .product(name: "Sparkle", package: "Sparkle"),
            ],
            exclude: ["Info.plist", "CutNotes.entitlements"],
            resources: [.process("Resources")],
            linkerSettings: [
                .unsafeFlags([
                    "-Xlinker", "-rpath",
                    "-Xlinker", "@executable_path/../Frameworks",
                ])
            ]
        ),
        .testTarget(name: "CutNotesCoreTests", dependencies: ["CutNotesCore"]),
    ]
)
