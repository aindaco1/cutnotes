import SwiftUI

struct SupportReportReviewView: View {
    let review: SupportReportReviewStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Review Support Reports")
                .font(.title2)
            Text("Sending publishes exactly the information below to CutNotes’ GitHub repository through Dust Wave’s report service. Similar reports are grouped into one issue. Source media, transcripts, project names, editorial context, file paths, device names, raw logs, and crash stacks are excluded.")
            if !review.enabled {
                Text("Sending is unavailable in this development build. The exact report remains visible and copyable below.")
                    .foregroundStyle(.secondary)
            }
            ScrollView {
                Text(review.preview)
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
            }
            .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 10))
            .accessibilityLabel("Exact support report information to be sent")
            if let message = review.message {
                Text(message).font(.callout)
            }
            ForEach(review.issueNumbers, id: \.self) { number in
                Link(
                    "View issue #\(number)",
                    destination: URL(string: "https://github.com/aindaco1/cutnotes/issues/\(number)")!
                )
            }
            HStack {
                Button("Close") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                    .disabled(review.isBusy)
                Spacer()
                if review.isBusy { ProgressView().controlSize(.small) }
                Button("Send Reviewed Reports") {
                    Task { await review.sendReviewedReports() }
                }
                .disabled(!review.enabled || review.isBusy || review.reports.isEmpty)
            }
        }
        .padding(24)
        .frame(width: 700, height: 580)
        .task { await review.load() }
        .interactiveDismissDisabled(review.isBusy)
    }
}
