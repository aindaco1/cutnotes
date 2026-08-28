import AppKit
import CutNotesCore
import Foundation
import Observation

@MainActor
@Observable
final class CutNotesStore {
    var workflow: AppWorkflow = .record
    var title = ""
    var context = ""
    var sourceURL: URL?
    var doctor: DoctorPayload?
    var progress: CLIProgressEvent?
    var result: CLIResultPayload?
    var failure: PresentedFailure?
    var isRunning = false
    var isRecording = false
    var notice: String?

    var outputRootPath: String { didSet { defaults.set(outputRootPath, forKey: Keys.outputRoot) } }
    var language: String { didSet { defaults.set(language, forKey: Keys.language) } }
    var transcriber: CutNotesTranscriber { didSet { defaults.set(transcriber.rawValue, forKey: Keys.transcriber) } }
    var formatter: CutNotesFormatter { didSet { defaults.set(formatter.rawValue, forKey: Keys.formatter) } }
    var microphoneIndex: Int? { didSet { defaults.set(microphoneIndex, forKey: Keys.microphone) } }
    var whisperModel: String { didSet { defaults.set(whisperModel, forKey: Keys.whisperModel) } }
    var codexModel: String { didSet { defaults.set(codexModel, forKey: Keys.codexModel) } }
    var transcriptOnly = false

    private let defaults: UserDefaults
    private let client = SubprocessCLIClient()

    private enum Keys {
        static let outputRoot = "outputRoot"
        static let language = "language"
        static let transcriber = "transcriber"
        static let formatter = "formatter"
        static let microphone = "microphoneIndex"
        static let microphonePreferenceVersion = "microphonePreferenceVersion"
        static let whisperModel = "whisperModel"
        static let codexModel = "codexModel"
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        outputRootPath = defaults.string(forKey: Keys.outputRoot)
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Desktop").path
        language = defaults.string(forKey: Keys.language) ?? "en"
        transcriber = CutNotesTranscriber(
            rawValue: defaults.string(forKey: Keys.transcriber) ?? "parakeet"
        ) ?? .parakeet
        let savedFormatter = CutNotesFormatter(
            rawValue: defaults.string(forKey: Keys.formatter) ?? "apple"
        ) ?? .apple
        formatter = savedFormatter == .none ? .apple : savedFormatter
        if defaults.integer(forKey: Keys.microphonePreferenceVersion) < 1 {
            microphoneIndex = nil
            defaults.removeObject(forKey: Keys.microphone)
            defaults.set(1, forKey: Keys.microphonePreferenceVersion)
        } else {
            microphoneIndex = defaults.object(forKey: Keys.microphone) as? Int
        }
        whisperModel = defaults.string(forKey: Keys.whisperModel) ?? ""
        codexModel = defaults.string(forKey: Keys.codexModel) ?? ""
        transcriptOnly = savedFormatter == .none
    }

    var selectedMicrophoneName: String {
        guard let microphoneIndex,
              let microphone = doctor?.microphones.first(where: { $0.index == microphoneIndex })
        else { return "System Default" }
        return microphone.name
    }

    var canRun: Bool {
        !isRunning && !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && (workflow == .record || sourceURL != nil)
    }

    func refreshDoctor() async {
        do {
            let execution = try await client.run(try builder().doctor())
            guard !execution.standardOutput.isEmpty else { return }
            doctor = try ContractDecoder.decode(DoctorPayload.self, from: execution.standardOutput)
            if let microphoneIndex,
               doctor?.microphones.contains(where: { $0.index == microphoneIndex }) != true {
                self.microphoneIndex = nil
            }
        } catch {
            failure = presented(error)
        }
    }

    func run() async {
        guard canRun else { return }
        failure = nil
        result = nil
        progress = nil
        notice = nil
        isRunning = true
        isRecording = workflow == .record
        do {
            let command: CLICommand
            switch workflow {
            case .record:
                command = try builder().record(options: options(), microphoneIndex: microphoneIndex)
            case .importMedia:
                guard let sourceURL else { return }
                command = try builder().importMedia(sourceURL, options: options())
            case .format:
                guard let sourceURL else { return }
                command = try builder().formatTranscript(
                    sourceURL,
                    title: title,
                    formatter: formatter == .none ? .apple : formatter,
                    codexModel: codexModel,
                    context: context
                )
            }
            let execution = try await client.run(command) { [weak self] event in
                await MainActor.run { self?.progress = event }
            }
            if execution.exitCode != 0 {
                throw decodeCLIError(execution.standardError, exitCode: execution.exitCode)
            }
            result = try ContractDecoder.decode(CLIResultPayload.self, from: execution.standardOutput)
            title = ""
            context = ""
            sourceURL = nil
        } catch {
            failure = presented(error)
        }
        isRecording = false
        isRunning = false
        await refreshDoctor()
    }

    func finishRecording() {
        Task {
            do { try await client.finishRecording() }
            catch { await MainActor.run { failure = presented(error) } }
        }
    }

    func cancel() {
        Task {
            do { try await client.cancelCurrentCommand() }
            catch { await MainActor.run { failure = presented(error) } }
        }
    }

    func downloadModel() async {
        failure = nil
        isRunning = true
        do {
            let execution = try await client.run(try builder().downloadModel()) { [weak self] event in
                await MainActor.run { self?.progress = event }
            }
            if execution.exitCode != 0 {
                throw decodeCLIError(execution.standardError, exitCode: execution.exitCode)
            }
            _ = try ContractDecoder.decode(ModelPayload.self, from: execution.standardOutput)
            notice = "Parakeet v3 is installed and verified."
        } catch {
            failure = presented(error)
        }
        isRunning = false
        await refreshDoctor()
    }

    func importModel(from url: URL) async {
        failure = nil
        isRunning = true
        do {
            let execution = try await client.run(try builder().importModel(from: url))
            if execution.exitCode != 0 {
                throw decodeCLIError(execution.standardError, exitCode: execution.exitCode)
            }
            _ = try ContractDecoder.decode(ModelPayload.self, from: execution.standardOutput)
            notice = "Parakeet v3 is installed and verified."
        } catch {
            failure = presented(error)
        }
        isRunning = false
        await refreshDoctor()
    }

    func installCommand() async {
        do {
            try await CommandInstaller.install()
            notice = "Installed /usr/local/bin/cutnotes."
        } catch {
            failure = presented(error)
        }
    }

    func exportDiagnostics() {
        do {
            if let url = try DiagnosticsService.export(doctor: doctor) {
                notice = "Saved privacy-safe diagnostics to \(url.lastPathComponent)."
            }
        } catch {
            failure = presented(error)
        }
    }

    func openNotes() {
        guard let path = result?.paths.markdown ?? result?.paths.transcript else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }

    func revealFolder() {
        guard let result else { return }
        let path = result.paths.sessionDirectory ?? result.paths.markdown ?? result.paths.transcript
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
    }

    private func options() throws -> PipelineOptions {
        let root = URL(fileURLWithPath: outputRootPath).standardizedFileURL
        guard root.path.hasPrefix("/") else {
            throw CLICommandError.pathMustBeAbsolute
        }
        return PipelineOptions(
            title: title,
            root: root,
            language: language,
            transcriber: transcriber,
            formatter: formatter,
            whisperModel: whisperModel,
            codexModel: codexModel,
            context: context,
            transcriptOnly: transcriptOnly
        )
    }

    private func builder() throws -> CLICommandBuilder {
        try CLICommandBuilder(executable: cliExecutable())
    }

    private func cliExecutable() -> URL {
        if let override = ProcessInfo.processInfo.environment["CUTNOTES_APP_CLI"] {
            return URL(fileURLWithPath: override)
        }
        return Bundle.main.bundleURL
            .appendingPathComponent("Contents/Resources/CLI/bin/cutnotes")
    }

    private func decodeCLIError(_ data: Data, exitCode: Int32) -> Error {
        let lines = data.split(separator: 0x0A).reversed()
        for line in lines {
            if let payload = try? ContractDecoder.decode(
                CLIErrorPayload.self,
                from: Data(line),
                maximumBytes: 16 * 1_024
            ) {
                return payload
            }
        }
        return NSError(
            domain: "CutNotes.CLI",
            code: Int(exitCode),
            userInfo: [NSLocalizedDescriptionKey: "CutNotes stopped before completing the workflow."]
        )
    }

    private func presented(_ error: Error) -> PresentedFailure {
        if let payload = error as? CLIErrorPayload {
            return PresentedFailure(
                title: payload.code == "cancelled" ? "Cancelled" : "CutNotes could not finish",
                message: payload.message,
                recovery: payload.recovery,
                audioPreserved: payload.preserved.audio,
                transcriptPreserved: payload.preserved.transcript
            )
        }
        let message = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        return PresentedFailure(
            title: "CutNotes could not finish",
            message: message,
            recovery: "Review the setup, then try again. Existing source files were not changed.",
            audioPreserved: false,
            transcriptPreserved: false
        )
    }
}
