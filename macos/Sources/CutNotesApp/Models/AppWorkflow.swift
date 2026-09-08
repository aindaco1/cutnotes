import Foundation

enum AppWorkflow: String, CaseIterable, Identifiable {
    case record = "Record"
    case importMedia = "Import"
    case format = "Format"

    var id: String { rawValue }

    var supportValue: String {
        switch self {
        case .record: "record"
        case .importMedia: "import"
        case .format: "format"
        }
    }

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
    let code: String
    let message: String
    let recovery: String
    let audioPreserved: Bool
    let transcriptPreserved: Bool
}
