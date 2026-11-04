import CutNotesCore
import SwiftUI

struct SetupStatusView: View {
    let doctor: DoctorPayload?
    let isRunning: Bool
    let download: (CutNotesModelKind) -> Void
    let importModel: (CutNotesModelKind) -> Void

    var body: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 12) {
                modelRow("Local transcription", name: "Parakeet v3", model: doctor?.parakeet, kind: .transcription)
                Divider()
                modelRow("On-device formatting", name: "Gemma 4 12B", model: doctor?.gemmaFormatter, kind: .formatting)
            }
        }
    }

    @ViewBuilder
    private func modelRow(_ title: String, name: String, model: DoctorPayload.Model?, kind: CutNotesModelKind) -> some View {
        let ready = model?.state == "ready"
        HStack(spacing: 8) {
            Image(systemName: ready ? "checkmark.circle.fill" : "arrow.down.circle")
                .foregroundStyle(ready ? CutNotesBrand.sage : CutNotesBrand.dust)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.subheadline.weight(.medium))
                Text(ready ? "\(name) ready — works offline" : model?.detail ?? "Checking…")
                    .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                if let model, !ready {
                    Text("One-time download: \(ByteCountFormatter.string(fromByteCount: model.bytes, countStyle: .decimal))")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            Spacer(minLength: 12)
            if let model, !ready, model.state != "unavailable" {
                Menu(model.state == "partial" ? "Resume Download" : "Set Up \(name)") {
                    Button("Accept \(model.license) & Download…") { download(kind) }
                    Button("Import Downloaded Model…") { importModel(kind) }
                    if let licenseURL = URL(string: model.licenseURL) {
                        Link("Review Model License", destination: licenseURL)
                    }
                }.disabled(isRunning)
            }
        }
    }
}
