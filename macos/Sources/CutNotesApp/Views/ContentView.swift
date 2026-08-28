import AppKit
import CutNotesCore
import SwiftUI

struct ContentView: View {
    @Bindable var store: CutNotesStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                SetupStatusView(
                    doctor: store.doctor,
                    isRunning: store.isRunning,
                    download: { Task { await store.downloadModel() } },
                    importModel: chooseModelFolder
                )
                workflowPicker
                mainForm
                advancedOptions
                statusArea
                actionArea
            }
            .frame(maxWidth: CutNotesBrand.contentWidth, alignment: .leading)
            .padding(.horizontal, 28)
            .padding(.vertical, 18)
            .frame(maxWidth: .infinity)
        }
        .background(CutNotesBrand.ink)
        .foregroundStyle(CutNotesBrand.paper)
        .tint(CutNotesBrand.paper)
        .preferredColorScheme(.dark)
        .task { await store.refreshDoctor() }
        .onChange(of: store.workflow) { _, workflow in
            if workflow == .format && store.formatter == .none {
                store.formatter = .apple
            }
        }
        .alert(item: $store.failure) { failure in
            Alert(
                title: Text(failure.title),
                message: Text(failureMessage(failure)),
                dismissButton: .default(Text("OK"))
            )
        }
    }

    private var workflowPicker: some View {
        HStack {
            Spacer(minLength: 0)
            Picker("", selection: $store.workflow) {
                ForEach(AppWorkflow.allCases) { workflow in
                    Text(workflow.rawValue).tag(workflow)
                }
            }
            .labelsHidden()
            .pickerStyle(.segmented)
            .frame(width: 360)
            .accessibilityLabel("Mode")
            .disabled(store.isRunning)
            Spacer(minLength: 0)
        }
    }

    private var mainForm: some View {
        GroupBox {
            Form {
                TextField("Project or cut name", text: $store.title)
                    .textFieldStyle(.roundedBorder)
                if store.workflow != .record {
                    LabeledContent(store.workflow == .format ? "Transcript" : "Audio or video") {
                        HStack {
                            Text(store.sourceURL?.lastPathComponent ?? "None selected")
                                .foregroundStyle(store.sourceURL == nil ? .secondary : .primary)
                                .lineLimit(1)
                            Button("Choose…", action: chooseSource)
                                .disabled(store.isRunning)
                        }
                    }
                }
                if store.workflow == .record {
                    Picker("Microphone", selection: $store.microphoneIndex) {
                        Text("System Default").tag(Int?.none)
                        ForEach(store.doctor?.microphones ?? []) { microphone in
                            Text(microphone.name).tag(Optional(microphone.index))
                        }
                    }
                    Text("Use headphones. Start each note with the cut timecode. CutNotes warns at 3 hours 45 minutes and stops at 4 hours.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                if store.workflow != .format {
                    LabeledContent("Save projects to") {
                        HStack {
                            Text(store.outputRootPath).lineLimit(1).truncationMode(.middle)
                            Button("Choose…", action: chooseOutputFolder)
                                .disabled(store.isRunning)
                        }
                    }
                }
            }
            .formStyle(.grouped)
        }
    }

    private var advancedOptions: some View {
        GroupBox("Advanced Options") {
            Form {
                if store.workflow != .format {
                    Picker("Transcription", selection: $store.transcriber) {
                        Text("Parakeet v3 — local (recommended)").tag(CutNotesTranscriber.parakeet)
                        Text("MacWhisper — optional").tag(CutNotesTranscriber.macwhisper)
                    }
                    TextField("Language", text: $store.language)
                    if store.transcriber == .macwhisper {
                        TextField("MacWhisper model override", text: $store.whisperModel)
                    }
                }
                Picker("Formatting", selection: $store.formatter) {
                    Text("Apple on-device (recommended)").tag(CutNotesFormatter.apple)
                    Text("Codex CLI — optional").tag(CutNotesFormatter.codex)
                }
                .disabled(store.workflow != .format && store.transcriptOnly)
                if store.formatter == .codex {
                    TextField("Codex model override", text: $store.codexModel)
                }
                TextField("Names or editorial context", text: $store.context, axis: .vertical)
                    .lineLimit(2...5)
                if store.workflow != .format {
                    Toggle("Transcript only", isOn: $store.transcriptOnly)
                }
                if store.transcriber == .parakeet && !["en", "auto"].contains(store.language.lowercased()) {
                    Text("English is fully supported in CutNotes 1.0. Other Parakeet languages are experimental transcription.")
                        .font(.caption)
                        .foregroundStyle(CutNotesBrand.dust)
                }
            }
            .formStyle(.grouped)
            .disabled(store.isRunning)
        }
    }

    @ViewBuilder
    private var statusArea: some View {
        if let progress = store.progress {
            VStack(alignment: .leading, spacing: 7) {
                HStack {
                    Text(progress.message ?? progress.stage.capitalized)
                    Spacer()
                    if let fraction = progress.fraction {
                        Text(fraction, format: .percent.precision(.fractionLength(0)))
                            .monospacedDigit()
                            .foregroundStyle(.secondary)
                    }
                }
                if let fraction = progress.fraction {
                    ProgressView(value: fraction)
                        .tint(progress.kind == "warning" ? CutNotesBrand.dust : CutNotesBrand.sage)
                } else if store.isRunning {
                    ProgressView()
                }
            }
            .padding(12)
            .background(.quaternary.opacity(0.45), in: RoundedRectangle(cornerRadius: 10))
        }
        if let notice = store.notice {
            Label(notice, systemImage: "checkmark.circle.fill")
                .foregroundStyle(CutNotesBrand.sage)
        }
        if store.result != nil {
            HStack {
                Label("Notes are ready", systemImage: "checkmark.circle.fill")
                    .font(.headline)
                    .foregroundStyle(CutNotesBrand.sage)
                Spacer()
                Button("Reveal Folder", action: store.revealFolder)
                Button("Open Notes", action: store.openNotes)
                    .buttonStyle(.borderedProminent)
                    .tint(CutNotesBrand.dust)
            }
        }
    }

    private var actionArea: some View {
        HStack {
            if store.isRunning {
                Button("Cancel", role: .destructive, action: store.cancel)
            }
            Spacer()
            if store.isRecording {
                Button("Finish Recording", action: store.finishRecording)
                    .buttonStyle(.borderedProminent)
                    .tint(CutNotesBrand.dust)
            } else {
                Button(store.workflow.actionTitle) {
                    Task { await store.run() }
                }
                .buttonStyle(.borderedProminent)
                .tint(CutNotesBrand.dust)
                .disabled(!store.canRun)
                .keyboardShortcut(.defaultAction)
            }
        }
    }

    private func chooseSource() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = store.workflow == .format ? [.plainText] : [.audiovisualContent, .audio]
        if panel.runModal() == .OK { store.sourceURL = panel.url }
    }

    private func chooseOutputFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url { store.outputRootPath = url.path }
    }

    private func chooseModelFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        if panel.runModal() == .OK, let url = panel.url {
            Task { await store.importModel(from: url) }
        }
    }

    private func failureMessage(_ failure: PresentedFailure) -> String {
        var parts = [failure.message, failure.recovery]
        if failure.audioPreserved { parts.append("Captured audio was preserved.") }
        if failure.transcriptPreserved { parts.append("The transcript was preserved.") }
        return parts.joined(separator: "\n\n")
    }
}
