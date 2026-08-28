import Foundation

public enum CLICommandError: Error, Equatable, Sendable {
    case executableMustBeAbsolute
    case pathMustBeAbsolute
    case unsafeArgument
    case titleRequired
}

public enum CutNotesTranscriber: String, CaseIterable, Identifiable, Sendable {
    case parakeet
    case macwhisper

    public var id: String { rawValue }
}

public enum CutNotesFormatter: String, CaseIterable, Identifiable, Sendable {
    case apple
    case codex
    case none

    public var id: String { rawValue }
}

public struct PipelineOptions: Equatable, Sendable {
    public var title: String
    public var root: URL
    public var language: String
    public var transcriber: CutNotesTranscriber
    public var formatter: CutNotesFormatter
    public var whisperModel: String?
    public var codexModel: String?
    public var context: String?
    public var transcriptOnly: Bool

    public init(
        title: String,
        root: URL,
        language: String = "en",
        transcriber: CutNotesTranscriber = .parakeet,
        formatter: CutNotesFormatter = .apple,
        whisperModel: String? = nil,
        codexModel: String? = nil,
        context: String? = nil,
        transcriptOnly: Bool = false
    ) {
        self.title = title
        self.root = root
        self.language = language
        self.transcriber = transcriber
        self.formatter = formatter
        self.whisperModel = whisperModel
        self.codexModel = codexModel
        self.context = context
        self.transcriptOnly = transcriptOnly
    }
}

public struct CLICommand: Equatable, Sendable {
    public let executable: URL
    public let arguments: [String]
    public let label: String

    public init(executable: URL, arguments: [String], label: String) throws {
        guard executable.isFileURL, executable.path.hasPrefix("/") else {
            throw CLICommandError.executableMustBeAbsolute
        }
        guard arguments.count <= 128,
              arguments.allSatisfy({ !$0.isEmpty && $0.count <= 8_192 && !$0.contains("\0") })
        else { throw CLICommandError.unsafeArgument }
        self.executable = executable
        self.arguments = arguments
        self.label = label
    }
}

public struct CLICommandBuilder: Sendable {
    public let executable: URL
    public let progressDescriptor: Int32
    public let controlDescriptor: Int32

    public init(
        executable: URL,
        progressDescriptor: Int32 = 3,
        controlDescriptor: Int32 = 4
    ) throws {
        guard executable.isFileURL, executable.path.hasPrefix("/") else {
            throw CLICommandError.executableMustBeAbsolute
        }
        guard (3...63).contains(progressDescriptor),
              (3...63).contains(controlDescriptor),
              progressDescriptor != controlDescriptor
        else { throw CLICommandError.unsafeArgument }
        self.executable = executable
        self.progressDescriptor = progressDescriptor
        self.controlDescriptor = controlDescriptor
    }

    public func doctor() throws -> CLICommand {
        try CLICommand(executable: executable, arguments: ["doctor", "--json"], label: "doctor")
    }

    public func modelStatus() throws -> CLICommand {
        try CLICommand(
            executable: executable,
            arguments: ["model", "status", "--json"],
            label: "model status"
        )
    }

    public func downloadModel() throws -> CLICommand {
        try CLICommand(
            executable: executable,
            arguments: [
                "model", "download", "--accept-license", "--json",
                "--progress-fd", String(progressDescriptor),
            ],
            label: "model download"
        )
    }

    public func importModel(from source: URL) throws -> CLICommand {
        try CLICommand(
            executable: executable,
            arguments: ["model", "import", try absolute(source), "--json"],
            label: "model import"
        )
    }

    public func record(options: PipelineOptions, microphoneIndex: Int?) throws -> CLICommand {
        var arguments = ["record", try title(options.title)]
        if let microphoneIndex {
            arguments += ["--device-index", String(microphoneIndex)]
        }
        arguments += try pipelineArguments(options)
        arguments += ["--control-fd", String(controlDescriptor)]
        return try CLICommand(executable: executable, arguments: arguments, label: "record")
    }

    public func importMedia(_ media: URL, options: PipelineOptions) throws -> CLICommand {
        var arguments = ["import", try absolute(media), "--title", try title(options.title)]
        arguments += try pipelineArguments(options)
        return try CLICommand(executable: executable, arguments: arguments, label: "import")
    }

    public func formatTranscript(
        _ transcript: URL,
        title: String,
        formatter: CutNotesFormatter,
        codexModel: String?,
        context: String?
    ) throws -> CLICommand {
        guard formatter != .none else { throw CLICommandError.unsafeArgument }
        var arguments = [
            "format", try absolute(transcript), "--title", try self.title(title),
            "--formatter", formatter.rawValue,
        ]
        append("--codex-model", codexModel, to: &arguments)
        append("--context", context, to: &arguments)
        arguments += machineArguments
        return try CLICommand(executable: executable, arguments: arguments, label: "format")
    }

    private var machineArguments: [String] {
        ["--json", "--progress-fd", String(progressDescriptor)]
    }

    private func pipelineArguments(_ options: PipelineOptions) throws -> [String] {
        var arguments = [
            "--root", try absolute(options.root),
            "--language", clean(options.language),
            "--transcriber", options.transcriber.rawValue,
            "--formatter", options.formatter.rawValue,
        ]
        append("--whisper-model", options.whisperModel, to: &arguments)
        append("--codex-model", options.codexModel, to: &arguments)
        append("--context", options.context, to: &arguments)
        if options.transcriptOnly || options.formatter == .none {
            arguments.append("--transcript-only")
        }
        arguments += machineArguments
        return arguments
    }

    private func title(_ value: String) throws -> String {
        let cleaned = clean(value)
        guard !cleaned.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw CLICommandError.titleRequired
        }
        return cleaned
    }

    private func absolute(_ url: URL) throws -> String {
        guard url.isFileURL, url.path.hasPrefix("/") else {
            throw CLICommandError.pathMustBeAbsolute
        }
        return url.standardizedFileURL.path
    }

    private func clean(_ value: String) -> String {
        String(value.prefix(8_192)).replacingOccurrences(of: "\0", with: "")
    }

    private func append(_ name: String, _ value: String?, to arguments: inout [String]) {
        guard let value else { return }
        let cleaned = clean(value).trimmingCharacters(in: .whitespacesAndNewlines)
        if !cleaned.isEmpty { arguments += [name, cleaned] }
    }
}
