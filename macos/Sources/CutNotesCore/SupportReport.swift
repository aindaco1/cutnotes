import Foundation

public struct SupportApplicationInfo: Codable, Equatable, Sendable {
    public let version: String
    public let build: String
    public let operatingSystem: String
    public let architecture: String

    public init(version: String, build: String, operatingSystem: String, architecture: String) {
        self.version = Self.numericVersion(version)
        self.build = Self.numericVersion(build)
        self.operatingSystem = Self.numericVersion(operatingSystem)
        self.architecture = ["arm64", "x86_64"].contains(architecture) ? architecture : "unknown"
    }

    public var isValid: Bool {
        [version, build, operatingSystem].allSatisfy { $0 == "unknown" || Self.numericVersion($0) == $0 }
            && ["arm64", "x86_64", "unknown"].contains(architecture)
    }

    private static func numericVersion(_ value: String) -> String {
        value.range(of: "^[0-9]{1,8}(\\.[0-9]{1,8}){0,3}$", options: .regularExpression) != nil
            ? value : "unknown"
    }
}

/// A deliberately small public projection of app state. It cannot represent
/// project names, editorial context, file paths, transcripts, or provider text.
public struct CutNotesSupportState: Codable, Equatable, Sendable {
    public static let workflows: Set<String> = ["record", "import", "format"]
    public static let languages: Set<String> = [
        "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "hr", "hu",
        "it", "lt", "lv", "mt", "nl", "pl", "pt", "ro", "ru", "sk", "sl", "sv", "uk",
    ]
    public static let transcribers: Set<String> = ["parakeet", "macwhisper"]
    public static let formatters: Set<String> = ["apple", "codex"]
    public static let progressStages: Set<String> = [
        "recording", "recording-paused", "validating", "transcribing", "formatting", "model-download",
    ]
    public static let failureCodes: Set<String> = [
        "apple_context_window", "apple_formatting_failed", "apple_formatting_invalid_result", "apple_guardrail",
        "apple_model_unavailable", "audio_not_captured", "audio_preparation_failed", "audio_track_missing",
        "cancelled", "codex_formatting_failed", "codex_formatting_invalid_result", "cutnotes_failed",
        "dependency_missing", "ffprobe_missing", "formatter_contract_failed", "formatter_empty_response",
        "formatter_invalid_response", "formatter_timecode_contract_failed", "interactive_terminal_required",
        "local_engine_missing", "macwhisper_failed", "macwhisper_start_failed", "media_empty",
        "media_not_regular", "media_probe_failed", "media_too_long", "microphone_not_found",
        "microphone_unavailable", "model_checksum_mismatch", "model_disk_space", "model_download_failed",
        "model_download_untrusted", "model_incomplete", "model_license_not_accepted", "model_missing",
        "model_not_found", "model_size_mismatch", "model_unsafe_file", "parakeet_failed",
        "parakeet_invalid_result", "recording_control_invalid", "recording_control_missing",
        "recording_finalize_failed", "recording_not_started", "setup_unhealthy", "title_missing",
        "transcript_empty", "transcript_encoding", "transcript_not_regular", "unknown",
    ]

    public let workflow: String
    public let isRunning: Bool
    public let isRecording: Bool
    public let isPaused: Bool
    public let hasSource: Bool
    public let transcriptOnly: Bool
    public let language: String
    public let transcriber: String
    public let formatter: String
    public let usesSystemDefaultMicrophone: Bool
    public let microphoneCount: Int?
    public let coreHealthy: Bool?
    public let defaultWorkflowReady: Bool?
    public let parakeetReady: Bool?
    public let appleFormatterReady: Bool?
    public let ffmpegAvailable: Bool?
    public let macwhisperAvailable: Bool?
    public let codexAvailable: Bool?
    public let progressStage: String?
    public let failureCode: String?

    public init(
        workflow: String,
        isRunning: Bool,
        isRecording: Bool,
        isPaused: Bool,
        hasSource: Bool,
        transcriptOnly: Bool,
        language: String,
        transcriber: String,
        formatter: String,
        usesSystemDefaultMicrophone: Bool,
        microphoneCount: Int?,
        coreHealthy: Bool?,
        defaultWorkflowReady: Bool?,
        parakeetReady: Bool?,
        appleFormatterReady: Bool?,
        ffmpegAvailable: Bool?,
        macwhisperAvailable: Bool?,
        codexAvailable: Bool?,
        progressStage: String?,
        failureCode: String?
    ) {
        self.workflow = workflow
        self.isRunning = isRunning
        self.isRecording = isRecording
        self.isPaused = isPaused
        self.hasSource = hasSource
        self.transcriptOnly = transcriptOnly
        self.language = language
        self.transcriber = transcriber
        self.formatter = formatter
        self.usesSystemDefaultMicrophone = usesSystemDefaultMicrophone
        self.microphoneCount = microphoneCount
        self.coreHealthy = coreHealthy
        self.defaultWorkflowReady = defaultWorkflowReady
        self.parakeetReady = parakeetReady
        self.appleFormatterReady = appleFormatterReady
        self.ffmpegAvailable = ffmpegAvailable
        self.macwhisperAvailable = macwhisperAvailable
        self.codexAvailable = codexAvailable
        self.progressStage = progressStage
        self.failureCode = failureCode
    }

    public var isValid: Bool {
        Self.workflows.contains(workflow)
            && Self.languages.contains(language)
            && Self.transcribers.contains(transcriber)
            && Self.formatters.contains(formatter)
            && (microphoneCount.map { (0...128).contains($0) } ?? true)
            && (progressStage.map(Self.progressStages.contains) ?? true)
            && (failureCode.map(Self.failureCodes.contains) ?? true)
            && (!isPaused || isRecording)
            && (!isRecording || isRunning)
    }
}

public struct CutNotesNativeCrashSummary: Codable, Equatable, Sendable {
    public static let exceptions: Set<String> = [
        "EXC_BAD_ACCESS", "EXC_BAD_INSTRUCTION", "EXC_ARITHMETIC", "EXC_EMULATION", "EXC_SOFTWARE",
        "EXC_BREAKPOINT", "EXC_CRASH", "EXC_RESOURCE", "EXC_GUARD",
    ]
    public static let signals: Set<String> = [
        "SIGKILL", "SIGTERM", "SIGABRT", "SIGSEGV", "SIGBUS", "SIGILL", "SIGTRAP", "SIGPIPE", "SIGINT", "SIGFPE",
    ]
    public static let images: Set<String> = [
        "CutNotes", "SwiftUI", "SwiftUICore", "AppKit", "libswiftCore.dylib", "libsystem_kernel.dylib",
    ]

    public let exception: String
    public let signal: String?
    public let image: String?
    public let imageOffset: Int?

    public init(exception: String, signal: String?, image: String?, imageOffset: Int?) {
        self.exception = exception
        self.signal = signal
        self.image = image
        self.imageOffset = imageOffset
    }

    public var isValid: Bool {
        Self.exceptions.contains(exception)
            && (signal.map(Self.signals.contains) ?? true)
            && (image.map(Self.images.contains) ?? true)
            && (imageOffset.map { (0...1_000_000_000).contains($0) } ?? true)
    }
}

public struct CutNotesSupportReport: Codable, Equatable, Sendable, Identifiable {
    public static let schema = "cutnotes-issue-report-v1"

    public let schemaVersion: String
    public let id: String
    public let application: SupportApplicationInfo
    public let kind: String
    public let state: CutNotesSupportState?
    public let crash: CutNotesNativeCrashSummary?

    public init(state: CutNotesSupportState, application: SupportApplicationInfo, id: UUID = UUID()) {
        schemaVersion = Self.schema
        self.id = id.uuidString.lowercased()
        self.application = application
        kind = "current_state"
        self.state = state
        crash = nil
    }

    public init(crash: CutNotesNativeCrashSummary, application: SupportApplicationInfo, id: UUID) {
        schemaVersion = Self.schema
        self.id = id.uuidString.lowercased()
        self.application = application
        kind = "native_crash"
        state = nil
        self.crash = crash
    }

    public var isValid: Bool {
        schemaVersion == Self.schema
            && UUID(uuidString: id)?.uuidString.lowercased() == id
            && application.isValid
            && ["current_state", "native_crash"].contains(kind)
            && (kind == "current_state" ? state?.isValid == true && crash == nil : crash?.isValid == true && state == nil)
    }
}

public enum CutNotesSupportSubmissionError: Error, Equatable, Sendable {
    case disabled
    case invalidPayload
    case unavailable
    case rateLimited
    case rejected
}

public protocol CutNotesSupportSubmitting: Sendable {
    var enabled: Bool { get }
    func submit(_ report: CutNotesSupportReport) async throws -> Int
}

public struct CutNotesSupportSubmissionClient: CutNotesSupportSubmitting {
    public static let endpoint = URL(string: "https://crash.dustwave.xyz/v1/cutnotes/reports")!
    public let enabled: Bool
    private let transport: @Sendable (URLRequest) async throws -> (Data, HTTPURLResponse)

    public init(
        enabled: Bool,
        transport: @escaping @Sendable (URLRequest) async throws -> (Data, HTTPURLResponse) = Self.send
    ) {
        self.enabled = enabled
        self.transport = transport
    }

    public func submit(_ report: CutNotesSupportReport) async throws -> Int {
        guard enabled else { throw CutNotesSupportSubmissionError.disabled }
        let data = try JSONEncoder().encode(report)
        guard report.isValid, data.count <= 8_192 else { throw CutNotesSupportSubmissionError.invalidPayload }
        var request = URLRequest(url: Self.endpoint, timeoutInterval: 15)
        request.httpMethod = "POST"
        request.httpBody = data
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("CutNotes-Support/1", forHTTPHeaderField: "User-Agent")
        let response: (Data, HTTPURLResponse)
        do { response = try await transport(request) }
        catch { throw CutNotesSupportSubmissionError.unavailable }
        if response.1.statusCode == 429 { throw CutNotesSupportSubmissionError.rateLimited }
        guard response.1.statusCode == 200, response.0.count <= 4_096,
              let receipt = try? JSONDecoder().decode(Receipt.self, from: response.0),
              receipt.ok, receipt.reportId == report.id,
              ["created", "updated", "aggregated", "duplicate"].contains(receipt.action),
              receipt.issueNumber > 0
        else { throw CutNotesSupportSubmissionError.rejected }
        return receipt.issueNumber
    }

    private struct Receipt: Decodable {
        let ok: Bool
        let reportId: String
        let action: String
        let issueNumber: Int
    }

    public static func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.httpCookieStorage = nil
        configuration.urlCredentialStorage = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.timeoutIntervalForRequest = 15
        configuration.timeoutIntervalForResource = 15
        let session = URLSession(configuration: configuration, delegate: RejectSupportRedirects(), delegateQueue: nil)
        defer { session.invalidateAndCancel() }
        let (bytes, response) = try await session.bytes(for: request)
        guard let response = response as? HTTPURLResponse else { throw CutNotesSupportSubmissionError.unavailable }
        var data = Data()
        for try await byte in bytes {
            guard data.count < 4_096 else { throw CutNotesSupportSubmissionError.rejected }
            data.append(byte)
        }
        return (data, response)
    }
}

private final class RejectSupportRedirects: NSObject, URLSessionTaskDelegate, Sendable {
    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        completionHandler(nil)
    }
}
