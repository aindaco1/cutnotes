import CutNotesCore
import SwiftUI

struct SetupStatusView: View {
    let doctor: DoctorPayload?
    let isRunning: Bool
    let download: () -> Void
    let importModel: () -> Void

    var body: some View {
        GroupBox {
            HStack(spacing: 18) {
                status(
                    "Local transcription",
                    detail: modelDetail,
                    ready: doctor?.parakeet.state == "ready"
                )
                Divider().frame(height: 30)
                status(
                    "On-device formatting",
                    detail: appleDetail,
                    ready: doctor?.appleFormatter.state == "ready"
                )
                Spacer()
                if let doctor, doctor.parakeet.state != "ready" {
                    Menu("Set Up Model") {
                        Button("Accept CC BY 4.0 & Download…", action: download)
                            .disabled(isRunning)
                        Button("Import Downloaded Model…", action: importModel)
                            .disabled(isRunning)
                        Link("Review Parakeet License", destination: URL(string: doctor.parakeet.licenseURL)!)
                    }
                }
            }
        }
    }

    private var modelDetail: String {
        guard let doctor else { return "Checking…" }
        return doctor.parakeet.state == "ready" ? "Parakeet v3 ready" : "Model setup required"
    }

    private var appleDetail: String {
        guard let doctor else { return "Checking…" }
        return doctor.appleFormatter.state == "ready"
            ? "Apple Intelligence ready"
            : "Unavailable — Codex remains optional"
    }

    @ViewBuilder
    private func status(_ title: String, detail: String, ready: Bool) -> some View {
        HStack(spacing: 8) {
            Image(systemName: ready ? "checkmark.circle.fill" : "exclamationmark.circle")
                .foregroundStyle(ready ? CutNotesBrand.sage : CutNotesBrand.dust)
            VStack(alignment: .leading, spacing: 1) {
                Text(title).font(.subheadline.weight(.medium))
                Text(detail).font(.caption).foregroundStyle(.secondary)
            }
        }
    }
}
