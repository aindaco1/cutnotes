import AppKit
import SwiftUI

@main
struct CutNotesApp: App {
    @State private var store = CutNotesStore()
    @StateObject private var updates = AppUpdateController()

    var body: some Scene {
        WindowGroup {
            ContentView(store: store)
                .frame(minWidth: 720, minHeight: 620)
                .preferredColorScheme(.dark)
                .onAppear {
                    NSApp.setActivationPolicy(.regular)
                    NSApp.activate(ignoringOtherApps: true)
                }
        }
        .defaultSize(width: 820, height: 760)
        .windowResizability(.contentMinSize)
        .commands {
            CommandGroup(after: .appInfo) {
                Button("Check for Updates…") { updates.checkForUpdates() }
                    .disabled(!updates.canCheckForUpdates)
            }
            CommandGroup(after: .newItem) {
                Button("Install cutnotes Command…") {
                    Task { await store.installCommand() }
                }
                Divider()
                Button("Export Diagnostics…", action: store.exportDiagnostics)
            }
        }
    }
}
