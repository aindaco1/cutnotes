import Foundation
import Testing
@testable import CutNotesCore

@Test func commandBuilderUsesVersionedMachineChannels() throws {
    let builder = try CLICommandBuilder(executable: URL(fileURLWithPath: "/Applications/CutNotes.app/cli"))
    let options = PipelineOptions(
        title: "Demo Cut",
        root: URL(fileURLWithPath: "/tmp/Output"),
        context: "Mia is the lead"
    )
    let command = try builder.record(options: options, microphoneIndex: 2)
    #expect(command.arguments.first == "record")
    #expect(command.arguments.contains("--json"))
    #expect(command.arguments.contains("--progress-fd"))
    #expect(command.arguments.contains("--control-fd"))
    #expect(command.arguments.contains("parakeet"))
    #expect(command.arguments.contains("apple"))
}

@Test func commandBuilderKeepsTranscriptOnlyExplicit() throws {
    let builder = try CLICommandBuilder(executable: URL(fileURLWithPath: "/tmp/cutnotes"))
    let options = PipelineOptions(
        title: "Private Review",
        root: URL(fileURLWithPath: "/tmp"),
        formatter: .none,
        transcriptOnly: true
    )
    let command = try builder.importMedia(URL(fileURLWithPath: "/tmp/source.wav"), options: options)
    #expect(command.arguments.contains("--transcript-only"))
    #expect(command.arguments.contains("none"))
}

@Test func commandBuilderLeavesMicrophoneSelectionToSystemByDefault() throws {
    let builder = try CLICommandBuilder(executable: URL(fileURLWithPath: "/tmp/cutnotes"))
    let options = PipelineOptions(title: "Default Input", root: URL(fileURLWithPath: "/tmp"))
    let command = try builder.record(options: options, microphoneIndex: nil)
    #expect(!command.arguments.contains("--device-index"))
}

@Test func progressContractRejectsUnknownSchema() throws {
    let data = Data(#"{"schema_version":"future","sequence":0,"kind":"stage","stage":"recording"}"#.utf8)
    #expect(throws: ContractError.self) {
        try ContractDecoder.decode(CLIProgressEvent.self, from: data)
    }
}

@Test func resultContractAcceptsAbsolutePaths() throws {
    let data = Data(#"{"schema_version":"cutnotes.result.v1","status":"complete","command":"format","providers":{"transcriber":null,"formatter":"apple"},"paths":{"session_dir":null,"audio":null,"transcript":"/tmp/transcript.txt","markdown":"/tmp/notes.md"}}"#.utf8)
    let result = try ContractDecoder.decode(CLIResultPayload.self, from: data)
    #expect(result.paths.markdown == "/tmp/notes.md")
}

@Test func incompleteFormattingDecodesAsFailureWithPreservedArtifacts() throws {
    let data = Data(#"{"schema_version":"cutnotes.error.v1","code":"formatter_incomplete","message":"Formatting is incomplete.","recovery":"Retry using the preserved transcript.","exit_code":6,"preserved":{"audio":true,"transcript":true}}"#.utf8)
    let failure = try ContractDecoder.decode(CLIErrorPayload.self, from: data)
    #expect(failure.code == "formatter_incomplete")
    #expect(failure.preserved.audio)
    #expect(failure.preserved.transcript)
    #expect(CutNotesSupportState.failureCodes.contains(failure.code))
}

@Test func doctorContractDecodesCoreOwnedNativeLanguageNames() throws {
    let data = Data(#"{"schema_version":"cutnotes.doctor.v1","healthy":true,"default_workflow_ready":true,"cutnotes":"1.0.0","architecture":"arm64","ffmpeg":{"path":"/tmp/ffmpeg","version":"8.1.1"},"ffprobe":{"path":"/tmp/ffprobe","version":"8.1.1"},"local_engine":{"path":"/tmp/CutNotesLocal","version":"1.0.0","apple":{"state":"ready","reason":null}},"parakeet":{"id":"parakeet-tdt-0.6b-v3","state":"ready","detail":null,"path":"/tmp/model","bytes":1,"source":"test","revision":"test","license":"CC-BY-4.0","license_url":"https://example.com","languages":[{"code":"fr","name":"Français"},{"code":"uk","name":"Українська"}]},"apple_formatter":{"state":"ready","reason":null},"macwhisper":{"path":null,"version":null,"optional":true,"models":[]},"codex":{"path":null,"version":null,"optional":true,"models":null},"microphones":[]}"#.utf8)
    let doctor = try ContractDecoder.decode(DoctorPayload.self, from: data)
    #expect(doctor.parakeet.languages?.map(\.name) == ["Français", "Українська"])
}

@Test func doctorContractAcceptsDetectedMacWhisperWithoutProbingIt() throws {
    let data = Data(#"{"path":"/Applications/MacWhisper.app/Contents/MacOS/mw","version":null,"optional":true,"models":[]}"#.utf8)
    let provider = try JSONDecoder().decode(DoctorPayload.OptionalTool.self, from: data)
    #expect(provider.path != nil)
    #expect(provider.version == nil)
    #expect(provider.models == [])
}

@Test func appleStatusAcceptsLegacyAndMacOS27ModelDetails() throws {
    let legacy = try JSONDecoder().decode(DoctorPayload.AppleStatus.self,
        from: Data(#"{"state":"ready","reason":null}"#.utf8))
    #expect(legacy.state == "ready")
    #expect(legacy.model == nil)

    let current = try JSONDecoder().decode(DoctorPayload.AppleStatus.self,
        from: Data(#"{"state":"ready","model":{"name":"AFM 3 Core","context_size":4096,"capabilities":["guided_generation","tool_calling"]}}"#.utf8))
    #expect(current.model?.contextSize == 4096)
    #expect(current.model?.capabilities.contains("reasoning") == false)
    #expect(current.model?.name == "AFM 3 Core")
    #expect(try JSONDecoder().decode(DoctorPayload.AppleStatus.self,
        from: JSONEncoder().encode(current)) == current)
    // Shared by the native status producer and app decoder; older payloads
    // must keep their shape instead of adding a guessed model identity.
    let legacyJSON = try JSONSerialization.jsonObject(with: JSONEncoder().encode(legacy)) as? [String: Any]
    #expect(legacyJSON?["model"] == nil)
}

@Test func formatCommandNeverAddsRecordingControlChannel() throws {
    let builder = try CLICommandBuilder(executable: URL(fileURLWithPath: "/tmp/cutnotes"))
    let command = try builder.formatTranscript(
        URL(fileURLWithPath: "/tmp/transcript.txt"),
        title: "Demo",
        formatter: .apple,
        codexModel: "",
        context: ""
    )
    #expect(command.arguments.contains("--progress-fd"))
    #expect(!command.arguments.contains("--control-fd"))
}

@Test func commandBuilderRejectsRelativeRoots() throws {
    let builder = try CLICommandBuilder(executable: URL(fileURLWithPath: "/tmp/cutnotes"))
    let options = PipelineOptions(
        title: "Demo",
        root: URL(string: "relative-output")!
    )
    #expect(throws: CLICommandError.self) {
        try builder.record(options: options, microphoneIndex: 0)
    }
}
