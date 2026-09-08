import CutNotesCore
import Foundation
import Observation

@MainActor
protocol SupportReportTracking: AnyObject {
    func submittedCrashIDs() -> Set<String>
    func markCrashSubmitted(_ id: String)
}

@MainActor
final class DefaultsSupportReportTracker: SupportReportTracking {
    private let defaults: UserDefaults
    private let key = "submittedSupportCrashIDs"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func submittedCrashIDs() -> Set<String> {
        Set(defaults.stringArray(forKey: key) ?? [])
    }

    func markCrashSubmitted(_ id: String) {
        var ids = defaults.stringArray(forKey: key) ?? []
        ids.removeAll { $0 == id }
        ids.append(id)
        defaults.set(Array(ids.suffix(100)), forKey: key)
    }
}

@MainActor
@Observable
final class SupportReportReviewStore {
    private(set) var reports: [CutNotesSupportReport] = []
    private(set) var isBusy = false
    private(set) var message: String?
    private(set) var issueNumbers: [Int] = []
    let enabled: Bool

    private let currentState: @MainActor () -> CutNotesSupportReport
    private let submitter: any CutNotesSupportSubmitting
    private let crashes: @Sendable () async throws -> [CutNotesSupportReport]
    private let tracker: any SupportReportTracking

    init(
        currentState: @escaping @MainActor () -> CutNotesSupportReport,
        submitter: any CutNotesSupportSubmitting,
        crashes: @escaping @Sendable () async throws -> [CutNotesSupportReport] = SupportReportReviewStore.nativeCrashes,
        tracker: any SupportReportTracking = DefaultsSupportReportTracker()
    ) {
        self.currentState = currentState
        self.submitter = submitter
        self.crashes = crashes
        self.tracker = tracker
        enabled = submitter.enabled
    }

    var preview: String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return (try? encoder.encode(reports)).map { String(decoding: $0, as: UTF8.self) } ?? "[]"
    }

    func load() async {
        guard !isBusy else { return }
        isBusy = true
        defer { isBusy = false }
        do {
            let submitted = tracker.submittedCrashIDs()
            let recent = try await crashes()
            let unique = recent.filter { $0.isValid && !submitted.contains($0.id) }
                .reduce(into: [CutNotesSupportReport]()) { result, report in
                    if !result.contains(where: { $0.id == report.id }) { result.append(report) }
                }
            reports = [currentState()] + Array(unique.prefix(5))
            message = unique.isEmpty
                ? "The current app state is ready to review. No unsent recent CutNotes crashes were found."
                : "The current app state and \(unique.prefix(5).count) recent crash report(s) are ready to review."
        } catch {
            reports = [currentState()]
            message = "Recent crash reports could not be read. The current app state is still available, and all local data was preserved."
        }
    }

    func sendReviewedReports() async {
        guard enabled, !isBusy, !reports.isEmpty else { return }
        isBusy = true
        defer { isBusy = false }
        let reviewed = reports
        var sent = 0
        for report in reviewed {
            do {
                let number = try await submitter.submit(report)
                if report.kind == "native_crash" { tracker.markCrashSubmitted(report.id) }
                reports.removeAll { $0.id == report.id }
                if !issueNumbers.contains(number) { issueNumbers.append(number) }
                sent += 1
            } catch {
                let retry = error as? CutNotesSupportSubmissionError == .rateLimited
                    ? "Wait a few minutes" : "Check your connection"
                message = "Sent \(sent) of \(reviewed.count) reports. Remaining reports and all project data were preserved on this Mac. \(retry) and try Send again."
                return
            }
        }
        message = "Sent \(sent) report(s). Matching reports are grouped in the same GitHub issue. No project content was sent."
    }

    nonisolated static func nativeCrashes() async throws -> [CutNotesSupportReport] {
        try await Task.detached(priority: .utility) {
            let directory = CutNotesNativeCrashReports.directory
            guard FileManager.default.fileExists(atPath: directory.path) else { return [] }
            return try CutNotesNativeCrashReports.recentReports(directory: directory)
        }.value
    }
}
