import Foundation

enum CommandInstallerError: Error, LocalizedError {
    case appNotInApplications
    case authorizationFailed(String)
    case verificationFailed

    var errorDescription: String? {
        switch self {
        case .appNotInApplications:
            "Move CutNotes.app to Applications before installing the terminal command."
        case .authorizationFailed(let detail):
            "The terminal command was not installed. \(detail)"
        case .verificationFailed:
            "The administrator command completed, but /usr/local/bin/cutnotes was not installed."
        }
    }
}

enum CommandInstaller {
    static let appPath = "/Applications/CutNotes.app"
    static let commandPath = "/usr/local/bin/cutnotes"
    static let targetPath = "/Applications/CutNotes.app/Contents/Resources/CLI/bin/cutnotes"

    static func install(bundleURL: URL = .init(fileURLWithPath: Bundle.main.bundlePath)) async throws {
        guard bundleURL.standardizedFileURL.path == appPath else {
            throw CommandInstallerError.appNotInApplications
        }
        let fixedCommand = """
        /bin/mkdir -p /usr/local/bin && /bin/ln -sfn \
        '/Applications/CutNotes.app/Contents/Resources/CLI/bin/cutnotes' \
        '/usr/local/bin/cutnotes'
        """.replacingOccurrences(of: "\n", with: " ")
        let script = "do shell script \"\(appleScriptEscaped(fixedCommand))\" with administrator privileges"
        let process = Process()
        let errorPipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        process.arguments = ["-e", script]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = errorPipe
        try process.run()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            let detail = String(
                data: errorPipe.fileHandleForReading.readDataToEndOfFile(),
                encoding: .utf8
            )?.trimmingCharacters(in: .whitespacesAndNewlines) ?? "Authorization was cancelled."
            throw CommandInstallerError.authorizationFailed(String(detail.prefix(300)))
        }
        guard FileManager.default.fileExists(atPath: commandPath),
              (try? FileManager.default.destinationOfSymbolicLink(atPath: commandPath)) == targetPath
        else {
            throw CommandInstallerError.verificationFailed
        }
    }

    private static func appleScriptEscaped(_ value: String) -> String {
        value.replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
    }
}
