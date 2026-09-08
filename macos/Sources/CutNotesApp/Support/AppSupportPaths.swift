import CutNotesCore
import Foundation

enum AppSupportPaths {
    static func supportSubmissionEnabled(bundle: Bundle = .main) -> Bool {
        #if DEBUG
        return false
        #else
        return bundle.bundleIdentifier == "com.dustwave.cutnotes"
            && bundle.object(forInfoDictionaryKey: "CutNotesSupportReportsEnabled") as? Bool == true
        #endif
    }

    static func applicationInfo(
        bundle: Bundle = .main,
        processInfo: ProcessInfo = .processInfo
    ) -> SupportApplicationInfo {
        #if arch(arm64)
        let architecture = "arm64"
        #elseif arch(x86_64)
        let architecture = "x86_64"
        #else
        let architecture = "unknown"
        #endif
        let os = processInfo.operatingSystemVersion
        return SupportApplicationInfo(
            version: bundle.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown",
            build: bundle.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown",
            operatingSystem: "\(os.majorVersion).\(os.minorVersion).\(os.patchVersion)",
            architecture: architecture
        )
    }
}
