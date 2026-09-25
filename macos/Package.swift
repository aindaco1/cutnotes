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
        .package(path: "../shared/dust-wave-platform/desktop"),
        .package(path: "../shared/dust-wave-platform/native"),
        .package(url: "https://github.com/FluidInference/FluidAudio.git", exact: "0.15.6"),
        .package(url: "https://github.com/sparkle-project/Sparkle", exact: "2.9.6"),
    ],
    targets: [
        .target(name: "CutNotesCore", dependencies: [.product(name: "DustWaveDiagnostics", package: "desktop")]),
        .executableTarget(
            name: "CutNotesLocal",
            dependencies: [
                "CutNotesCore",
                .product(name: "DustWaveSpeech", package: "native"),
                .product(name: "DustWaveAppleIntelligence", package: "native"),
            ]
        ),
        .executableTarget(
            name: "CutNotesApp",
            dependencies: [
                "CutNotesCore",
                .product(name: "DustWaveUpdates", package: "desktop"),
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
        .testTarget(name: "CutNotesLocalTests", dependencies: ["CutNotesLocal"]),
        .testTarget(name: "CutNotesCoreTests", dependencies: ["CutNotesCore"]),
        .testTarget(name: "CutNotesAppTests", dependencies: ["CutNotesApp", "CutNotesCore"]),
    ]
)
