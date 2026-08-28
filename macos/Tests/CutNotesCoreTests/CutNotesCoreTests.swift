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
