import CutNotesCore
import Foundation
import Testing
@testable import CutNotesApp

@Suite("Support report review and consent")
struct SupportReportReviewTests {
    @Test("opening review never sends and partial failure preserves unsent reports")
    @MainActor
    func reviewRetry() async throws {
        let current = report(kind: "current")
        let crash = report(kind: "crash")
        let submitter = ReviewSubmitter()
        let tracker = ReviewTracker()
        let review = SupportReportReviewStore(
            currentState: { current },
            submitter: submitter,
            crashes: { [crash] },
            tracker: tracker
        )

        await review.load()
        #expect(review.reports.count == 2)
        #expect(await submitter.calls == 0)
        #expect(review.preview.contains("current_state"))
        #expect(review.preview.contains("native_crash"))

        await review.sendReviewedReports()
        #expect(await submitter.calls == 2)
        #expect(review.reports.count == 1)
        #expect(review.message?.contains("preserved on this Mac") == true)
        #expect(tracker.submittedCrashIDs().isEmpty)

        await review.sendReviewedReports()
        #expect(review.reports.isEmpty)
        #expect(review.issueNumbers == [42])
        #expect(tracker.submittedCrashIDs() == [crash.id])
        #expect(!AppSupportPaths.supportSubmissionEnabled())
    }

    private func report(kind: String) -> CutNotesSupportReport {
        let app = SupportApplicationInfo(
            version: "1.0.2", build: "3", operatingSystem: "26.0.0", architecture: "arm64"
        )
        if kind == "crash" {
            return CutNotesSupportReport(
                crash: .init(exception: "EXC_BREAKPOINT", signal: "SIGTRAP", image: "CutNotes", imageOffset: 10),
                application: app,
                id: UUID()
            )
        }
        return CutNotesSupportReport(
            state: .init(
                workflow: "record", isRunning: false, isRecording: false, isPaused: false,
                hasSource: false, transcriptOnly: false, language: "en", transcriber: "parakeet",
                formatter: "apple", usesSystemDefaultMicrophone: true, microphoneCount: 1,
                coreHealthy: true, defaultWorkflowReady: true, parakeetReady: true,
                appleFormatterReady: true, ffmpegAvailable: true, macwhisperAvailable: false,
                codexAvailable: false, progressStage: nil, failureCode: nil
            ),
            application: app,
            id: UUID()
        )
    }
}

private actor ReviewSubmitter: CutNotesSupportSubmitting {
    nonisolated let enabled = true
    private(set) var calls = 0

    func submit(_ report: CutNotesSupportReport) throws -> Int {
        calls += 1
        if calls == 2 { throw CutNotesSupportSubmissionError.rateLimited }
        return 42
    }
}

@MainActor
private final class ReviewTracker: SupportReportTracking {
    private var ids: Set<String> = []
    func submittedCrashIDs() -> Set<String> { ids }
    func markCrashSubmitted(_ id: String) { ids.insert(id) }
}
