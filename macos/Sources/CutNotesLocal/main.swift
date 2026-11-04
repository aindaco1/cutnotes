import Foundation
import CutNotesCore
import DustWaveSpeech

private let version = "1.1.1"

private enum LocalEngineError: Error, CustomStringConvertible {
    case invalidArguments(String)
    case unsupportedArchitecture
    case unsafeInput(String)

    var description: String {
        switch self {
        case .invalidArguments(let message): message
        case .unsupportedArchitecture: "CutNotes local processing requires Apple Silicon."
        case .unsafeInput(let message): message
        }
    }
}

private struct StatusPayload: Encodable {
    let schemaVersion = "cutnotes.local.status.v1"
    let version: String
    let architecture: String
    let apple: DoctorPayload.AppleStatus

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case version
        case architecture
        case apple
    }
}

private struct TranscriptPayload: Encodable {
    let schemaVersion = "cutnotes.local.transcript.v1"
    let text: String
    let durationSeconds: Double
    let confidence: Float

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case text
        case durationSeconds = "duration_seconds"
        case confidence
    }
}

// Optional companion to transcript-v1. These are recording offsets, never CUT
// timecodes. The core owns their validation, retention and any repair decisions.
struct TranscriptEvidencePayload: Codable {
    struct Token: Codable {
        let text: String
        let start: Double
        let end: Double
        let confidence: Float
    }

    struct Word: Codable {
        let text: String
        let start: Double
        let end: Double
    }

    let schemaVersion: String
    let text: String
    let durationSeconds: Double
    let tokens: [Token]
    let words: [Word]

    init(_ transcript: ParakeetTranscriptResult) {
        schemaVersion = "cutnotes.local.transcript-evidence.v1"
        text = transcript.text
        durationSeconds = transcript.durationSeconds
        tokens = transcript.tokens.map {
            Token(text: $0.text, start: $0.startsAtSeconds,
                  end: $0.endsAtSeconds, confidence: $0.confidence)
        }
        words = transcript.words.map {
            Word(text: $0.text, start: $0.startsAtSeconds, end: $0.endsAtSeconds)
        }
    }

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case durationSeconds = "duration_seconds"
        case text, tokens, words
    }
}

private struct Options {
    let command: String
    let values: [String: String]

    static func parse(_ arguments: [String]) throws -> Options {
        guard let command = arguments.first,
              ["status", "transcribe"].contains(command)
        else {
            throw LocalEngineError.invalidArguments(
                "Expected status or transcribe."
            )
        }
        var values: [String: String] = [:]
        var index = 1
        while index < arguments.count {
            let name = arguments[index]
            guard name.hasPrefix("--"), values[name] == nil else {
                throw LocalEngineError.invalidArguments("Invalid or repeated option: \(name)")
            }
            index += 1
            guard index < arguments.count, !arguments[index].hasPrefix("--") else {
                if name == "--json" {
                    values[name] = "true"
                    continue
                }
                throw LocalEngineError.invalidArguments("\(name) requires a value")
            }
            values[name] = arguments[index]
            index += 1
        }
        return Options(command: command, values: values)
    }

    func require(_ name: String) throws -> String {
        guard let value = values[name], !value.isEmpty else {
            throw LocalEngineError.invalidArguments("Missing required option: \(name)")
        }
        return value
    }
}

private func requireRegularFile(_ url: URL, label: String) throws {
    let values = try url.resourceValues(
        forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey]
    )
    guard values.isRegularFile == true,
          values.isSymbolicLink != true,
          (values.fileSize ?? 0) > 0
    else {
        throw LocalEngineError.unsafeInput("\(label) must be a non-empty regular file.")
    }
}

private func requireDirectory(_ url: URL, label: String) throws {
    let values = try url.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey])
    guard values.isDirectory == true, values.isSymbolicLink != true else {
        throw LocalEngineError.unsafeInput("\(label) must be a directory, not a symbolic link.")
    }
}

private func writeJSON<T: Encodable>(_ value: T, to url: URL? = nil) throws {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    let data = try encoder.encode(value)
    if let url {
        try data.write(to: url, options: .atomic)
    } else {
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data("\n".utf8))
    }
}

@main
private enum CutNotesLocal {
    static func main() async {
        do {
            #if !arch(arm64)
            throw LocalEngineError.unsupportedArchitecture
            #endif
            let options = try Options.parse(Array(CommandLine.arguments.dropFirst()))
            switch options.command {
            case "status":
                try writeJSON(
                    StatusPayload(
                        version: version,
                        architecture: "arm64",
                        apple: DoctorPayload.AppleStatus(state: "unavailable", reason: "replaced_by_gemma")
                    )
                )
            case "transcribe":
                let audio = URL(fileURLWithPath: try options.require("--audio"))
                let model = URL(fileURLWithPath: try options.require("--model"))
                let output = URL(fileURLWithPath: try options.require("--output"))
                try requireRegularFile(audio, label: "Audio")
                try requireDirectory(model, label: "Parakeet model")
                LocalSpeechOfflinePolicy.enforce()
                try ParakeetModelVerifier.validateV3(at: model)
                let transcriber = ParakeetTranscriber(model: .v3)
                try await transcriber.prepare(modelDirectory: model)
                let transcript = try await transcriber.transcribe(audio)
                await transcriber.release()
                try writeJSON(
                    TranscriptPayload(
                        text: transcript.text,
                        durationSeconds: transcript.durationSeconds,
                        confidence: transcript.confidence
                    ),
                    to: output
                )
                if let evidencePath = options.values["--evidence-output"] {
                    do {
                        try writeJSON(TranscriptEvidencePayload(transcript),
                                      to: URL(fileURLWithPath: evidencePath))
                    } catch {
                        FileHandle.standardError.write(Data("CutNotesLocal: Could not save optional word timing data: \(error)\n".utf8))
                    }
                }
            default:
                throw LocalEngineError.invalidArguments("Unsupported command")
            }
        } catch {
            let message = "CutNotesLocal: \(error)\n"
            FileHandle.standardError.write(Data(message.utf8))
            Foundation.exit(1)
        }
    }
}
