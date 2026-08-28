import Foundation

enum AppWorkflow: String, CaseIterable, Identifiable {
    case record = "Record"
    case importMedia = "Import"
    case format = "Format"

    var id: String { rawValue }

    var actionTitle: String {
        switch self {
        case .record: "Start Recording"
        case .importMedia: "Process Media"
        case .format: "Format Transcript"
        }
    }
}

struct PresentedFailure: Equatable, Identifiable {
    let id = UUID()
    let title: String
    let message: String
    let recovery: String
    let audioPreserved: Bool
    let transcriptPreserved: Bool
}
