import Combine
import Sparkle

@MainActor
final class AppUpdateController: NSObject, ObservableObject {
    @Published private(set) var canCheckForUpdates = false

    private let controller: SPUStandardUpdaterController
    private var hasCheckedThisLaunch = false

    override init() {
        controller = SPUStandardUpdaterController(
            startingUpdater: true,
            updaterDelegate: nil,
            userDriverDelegate: nil
        )
        super.init()
        canCheckForUpdates = controller.updater.canCheckForUpdates
        if controller.updater.automaticallyChecksForUpdates {
            checkInBackgroundOnce()
        }
    }

    func checkInBackgroundOnce() {
        guard !hasCheckedThisLaunch else { return }
        hasCheckedThisLaunch = true
        controller.updater.checkForUpdatesInBackground()
    }

    func checkForUpdates() {
        controller.checkForUpdates(nil)
    }
}
