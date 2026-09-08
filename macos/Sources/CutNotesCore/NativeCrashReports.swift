import Darwin
import Foundation

public enum CutNotesNativeCrashReports {
    public static var directory: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/DiagnosticReports", isDirectory: true)
    }

    public static func parse(_ data: Data) -> CutNotesSupportReport? {
        guard data.count <= 2 * 1_024 * 1_024,
              let newline = data.firstIndex(of: 10),
              let header = try? JSONSerialization.jsonObject(with: data[..<newline]) as? [String: Any],
              header["bundleID"] as? String == "com.dustwave.cutnotes",
              let incidentID = header["incident_id"] as? String,
              let id = UUID(uuidString: incidentID),
              let body = try? JSONSerialization.jsonObject(with: data[data.index(after: newline)...]) as? [String: Any],
              body["procName"] as? String == "CutNotes",
              let exception = body["exception"] as? [String: Any],
              let type = exception["type"] as? String,
              CutNotesNativeCrashSummary.exceptions.contains(type)
        else { return nil }

        let signal = (exception["signal"] as? String).flatMap {
            CutNotesNativeCrashSummary.signals.contains($0) ? $0 : nil
        }
        var image: String?
        var imageOffset: Int?
        if let threads = body["threads"] as? [[String: Any]],
           let faulting = body["faultingThread"] as? Int,
           threads.indices.contains(faulting),
           let frames = threads[faulting]["frames"] as? [[String: Any]],
           let usedImages = body["usedImages"] as? [[String: Any]] {
            for frame in frames.prefix(12) {
                guard let index = frame["imageIndex"] as? Int,
                      usedImages.indices.contains(index),
                      let name = usedImages[index]["name"] as? String,
                      CutNotesNativeCrashSummary.images.contains(name),
                      let offset = frame["imageOffset"] as? Int,
                      (0...1_000_000_000).contains(offset)
                else { continue }
                image = name
                imageOffset = offset
                break
            }
        }
        let train = (body["osVersion"] as? [String: Any])?["train"] as? String ?? ""
        let osVersion = train.range(
            of: "^macOS [0-9]{1,3}(\\.[0-9]{1,3}){1,2}$",
            options: .regularExpression
        ) != nil ? String(train.dropFirst(6)) : "unknown"
        let architecture = body["cpuType"] as? String == "ARM-64" ? "arm64"
            : body["cpuType"] as? String == "X86-64" ? "x86_64" : "unknown"
        return CutNotesSupportReport(
            crash: .init(exception: type, signal: signal, image: image, imageOffset: imageOffset),
            application: .init(
                version: header["app_version"] as? String ?? "unknown",
                build: header["build_version"] as? String ?? "unknown",
                operatingSystem: osVersion,
                architecture: architecture
            ),
            id: id
        )
    }

    public static func recentReports(directory: URL, now: Date = Date()) throws -> [CutNotesSupportReport] {
        let directory = directory.standardizedFileURL
        guard directory.resolvingSymlinksInPath() == directory else { return [] }
        let files = try FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: [.contentModificationDateKey],
            options: [.skipsHiddenFiles]
        )
        .filter { $0.pathExtension == "ips" && $0.lastPathComponent.hasPrefix("CutNotes-") }
        .sorted { $0.lastPathComponent > $1.lastPathComponent }
        .prefix(20)

        return files.compactMap { url in
            let descriptor = url.path.withCString {
                Darwin.open($0, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK)
            }
            guard descriptor >= 0 else { return nil }
            let handle = FileHandle(fileDescriptor: descriptor, closeOnDealloc: true)
            defer { try? handle.close() }
            var status = stat()
            guard fstat(descriptor, &status) == 0,
                  (status.st_mode & S_IFMT) == S_IFREG,
                  (1...2 * 1_024 * 1_024).contains(status.st_size),
                  abs(now.timeIntervalSince1970 - Double(status.st_mtimespec.tv_sec)) < 14 * 24 * 3_600,
                  let data = try? handle.read(upToCount: 2 * 1_024 * 1_024 + 1)
            else { return nil }
            return parse(data)
        }
        .prefix(5)
        .map { $0 }
    }
}
