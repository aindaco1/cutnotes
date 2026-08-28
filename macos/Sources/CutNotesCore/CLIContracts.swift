import Foundation

public enum ContractError: Error, Equatable, Sendable {
    case empty
    case exceedsLimit(Int)
    case unsupportedSchema(expected: String, actual: String?)
    case invalidValue(String)
}

public enum ContractDecoder {
    public static func decode<Value: Decodable>(
        _ type: Value.Type,
        from data: Data,
        maximumBytes: Int = 4 * 1_024 * 1_024
    ) throws -> Value {
        guard !data.isEmpty else { throw ContractError.empty }
        guard data.count <= maximumBytes else { throw ContractError.exceedsLimit(maximumBytes) }
        return try JSONDecoder().decode(type, from: data)
    }
}

public struct CLIProgressEvent: Codable, Equatable, Sendable {
    public static let schema = "cutnotes.progress.v1"

    public let schemaVersion: String
    public let sequence: Int
    public let kind: String
    public let stage: String
    public let fraction: Double?
    public let message: String?

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case sequence, kind, stage, fraction, message
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try container.decode(String.self, forKey: .schemaVersion)
        guard schemaVersion == Self.schema else {
            throw ContractError.unsupportedSchema(expected: Self.schema, actual: schemaVersion)
        }
        sequence = try container.decode(Int.self, forKey: .sequence)
        kind = try container.decode(String.self, forKey: .kind)
        stage = try container.decode(String.self, forKey: .stage)
        fraction = try container.decodeIfPresent(Double.self, forKey: .fraction)
        message = try container.decodeIfPresent(String.self, forKey: .message)
        guard sequence >= 0,
              ["stage", "progress", "warning"].contains(kind),
              !stage.isEmpty, stage.count <= 64,
              fraction.map({ $0.isFinite && (0...1).contains($0) }) ?? true,
              message.map({ !$0.isEmpty && $0.count <= 240 }) ?? true
        else { throw ContractError.invalidValue("progress") }
    }
}

public struct CLIErrorPayload: Codable, Equatable, Error, Sendable {
    public static let schema = "cutnotes.error.v1"

    public struct Preserved: Codable, Equatable, Sendable {
        public let audio: Bool
        public let transcript: Bool
    }

    public let schemaVersion: String
    public let code: String
    public let message: String
    public let recovery: String
    public let exitCode: Int32
    public let preserved: Preserved

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case code, message, recovery
        case exitCode = "exit_code"
        case preserved
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try container.decode(String.self, forKey: .schemaVersion)
        guard schemaVersion == Self.schema else {
            throw ContractError.unsupportedSchema(expected: Self.schema, actual: schemaVersion)
        }
        code = try container.decode(String.self, forKey: .code)
        message = try container.decode(String.self, forKey: .message)
        recovery = try container.decode(String.self, forKey: .recovery)
        exitCode = try container.decode(Int32.self, forKey: .exitCode)
        preserved = try container.decode(Preserved.self, forKey: .preserved)
        guard !code.isEmpty, code.count <= 64,
              !message.isEmpty, message.count <= 2_000,
              !recovery.isEmpty, recovery.count <= 1_000,
              exitCode > 0
        else { throw ContractError.invalidValue("error") }
    }
}

public struct CLIResultPayload: Codable, Equatable, Sendable {
    public static let schema = "cutnotes.result.v1"

    public struct Providers: Codable, Equatable, Sendable {
        public let transcriber: String?
        public let formatter: String?
    }

    public struct Paths: Codable, Equatable, Sendable {
        public let sessionDirectory: String?
        public let audio: String?
        public let transcript: String
        public let markdown: String?

        enum CodingKeys: String, CodingKey {
            case sessionDirectory = "session_dir"
            case audio, transcript, markdown
        }
    }

    public let schemaVersion: String
    public let status: String
    public let command: String
    public let providers: Providers
    public let paths: Paths

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case status, command, providers, paths
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try container.decode(String.self, forKey: .schemaVersion)
        guard schemaVersion == Self.schema else {
            throw ContractError.unsupportedSchema(expected: Self.schema, actual: schemaVersion)
        }
        status = try container.decode(String.self, forKey: .status)
        command = try container.decode(String.self, forKey: .command)
        providers = try container.decode(Providers.self, forKey: .providers)
        paths = try container.decode(Paths.self, forKey: .paths)
        let allPaths = [paths.sessionDirectory, paths.audio, paths.transcript, paths.markdown]
            .compactMap { $0 }
        guard status == "complete",
              ["record", "import", "format"].contains(command),
              allPaths.allSatisfy({ $0.hasPrefix("/") && !$0.contains("\0") })
        else { throw ContractError.invalidValue("result") }
    }
}

public struct DoctorPayload: Codable, Equatable, Sendable {
    public struct Language: Codable, Equatable, Identifiable, Sendable {
        public let code: String
        public let name: String
        public var id: String { code }

        public init(code: String, name: String) {
            self.code = code
            self.name = name
        }

        public init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            code = try container.decode(String.self, forKey: .code)
            name = try container.decode(String.self, forKey: .name)
            guard code.count == 2,
                  code.allSatisfy({ $0.isASCII && $0.isLowercase }),
                  !name.isEmpty, name.count <= 64
            else { throw ContractError.invalidValue("language") }
        }
    }

    public struct Tool: Codable, Equatable, Sendable {
        public let path: String?
        public let version: String?
    }

    public struct AppleStatus: Codable, Equatable, Sendable {
        public let state: String
        public let reason: String?
    }

    public struct LocalEngine: Codable, Equatable, Sendable {
        public let path: String?
        public let version: String?
        public let apple: AppleStatus
    }

    public struct Model: Codable, Equatable, Sendable {
        public let id: String
        public let state: String
        public let detail: String?
        public let path: String
        public let bytes: Int64
        public let source: String
        public let revision: String
        public let license: String
        public let licenseURL: String
        public let languages: [Language]?

        enum CodingKeys: String, CodingKey {
            case id, state, detail, path, bytes, source, revision, license, languages
            case licenseURL = "license_url"
        }
    }

    public struct OptionalTool: Codable, Equatable, Sendable {
        public let path: String?
        public let version: String?
        public let optional: Bool
        public let models: [String]?
    }

    public struct Microphone: Codable, Equatable, Identifiable, Sendable {
        public let index: Int
        public let name: String
        public var id: Int { index }
    }

    public let schemaVersion: String
    public let healthy: Bool
    public let defaultWorkflowReady: Bool
    public let cutnotes: String
    public let architecture: String
    public let ffmpeg: Tool
    public let ffprobe: Tool
    public let localEngine: LocalEngine
    public let parakeet: Model
    public let appleFormatter: AppleStatus
    public let macwhisper: OptionalTool
    public let codex: OptionalTool
    public let microphones: [Microphone]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case healthy
        case defaultWorkflowReady = "default_workflow_ready"
        case cutnotes, architecture, ffmpeg, ffprobe
        case localEngine = "local_engine"
        case parakeet
        case appleFormatter = "apple_formatter"
        case macwhisper, codex, microphones
    }
}

public struct ModelPayload: Codable, Equatable, Sendable {
    public let schemaVersion: String
    public let id: String
    public let state: String
    public let detail: String?
    public let path: String
    public let bytes: Int64
    public let source: String
    public let revision: String
    public let license: String
    public let licenseURL: String

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case id, state, detail, path, bytes, source, revision, license
        case licenseURL = "license_url"
    }
}
