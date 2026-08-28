import AppKit
import CutNotesCore
import Foundation

enum DiagnosticsService {
    struct Payload: Encodable {
        struct Provider: Encodable {
            let available: Bool
            let version: String?
        }

        let schemaVersion = "cutnotes.diagnostics.v1"
        let generatedAt: String
        let appVersion: String
        let osVersion: String
        let architecture: String
        let coreHealthy: Bool?
        let defaultWorkflowReady: Bool?
        let microphoneCount: Int?
        let modelState: String?
        let appleFormatterState: String?
        let ffmpeg: Provider?
        let macwhisper: Provider?
        let codex: Provider?

        enum CodingKeys: String, CodingKey {
            case schemaVersion = "schema_version"
            case generatedAt = "generated_at"
            case appVersion = "app_version"
            case osVersion = "os_version"
            case architecture
            case coreHealthy = "core_healthy"
            case defaultWorkflowReady = "default_workflow_ready"
            case microphoneCount = "microphone_count"
            case modelState = "model_state"
            case appleFormatterState = "apple_formatter_state"
            case ffmpeg, macwhisper, codex
        }
    }

    @MainActor
    static func export(doctor: DoctorPayload?) throws -> URL? {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "CutNotes-Diagnostics.json"
        panel.allowedContentTypes = [.json]
        guard panel.runModal() == .OK, let url = panel.url else { return nil }
        let formatter = ISO8601DateFormatter()
        let payload = Payload(
            generatedAt: formatter.string(from: Date()),
            appVersion: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown",
            osVersion: ProcessInfo.processInfo.operatingSystemVersionString,
            architecture: ProcessInfo.processInfo.environment["PROCESSOR_ARCHITECTURE"] ?? "arm64",
            coreHealthy: doctor?.healthy,
            defaultWorkflowReady: doctor?.defaultWorkflowReady,
            microphoneCount: doctor?.microphones.count,
            modelState: doctor?.parakeet.state,
            appleFormatterState: doctor?.appleFormatter.state,
            ffmpeg: doctor.map {
                .init(available: $0.ffmpeg.path != nil, version: $0.ffmpeg.version)
            },
            macwhisper: doctor.map {
                .init(available: $0.macwhisper.path != nil, version: $0.macwhisper.version)
            },
            codex: doctor.map {
                .init(available: $0.codex.path != nil, version: $0.codex.version)
            }
        )
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        try encoder.encode(payload).write(to: url, options: .atomic)
        return url
    }
}
