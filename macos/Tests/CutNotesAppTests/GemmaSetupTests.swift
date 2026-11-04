import Foundation
import Testing
@testable import CutNotesApp

@MainActor @Test func applePreferencesMigrateToGemmaAndExplicitCodexSurvives() throws {
    let name = "CutNotes.GemmaMigration." + UUID().uuidString
    let defaults = try #require(UserDefaults(suiteName: name))
    defer { defaults.removePersistentDomain(forName: name) }
    defaults.set("apple", forKey: "formatter")
    #expect(CutNotesStore(defaults: defaults).formatter == .gemma)
    defaults.set("codex", forKey: "formatter")
    #expect(CutNotesStore(defaults: defaults).formatter == .codex)
    defaults.set("none", forKey: "formatter")
    let transcriptOnly = CutNotesStore(defaults: defaults)
    #expect(transcriptOnly.formatter == .gemma)
    #expect(transcriptOnly.transcriptOnly)
}
