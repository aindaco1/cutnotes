import Darwin
import Foundation

public enum SubprocessError: Error, Equatable, Sendable {
    case commandAlreadyRunning
    case pipeCreation(Int32)
    case spawnFailed(Int32)
    case readFailed(Int32)
    case writeFailed(Int32)
    case outputExceededLimit(stream: String, maximumBytes: Int)
    case progressLineExceededLimit
    case tooManyProgressEvents
    case invalidProgress
    case waitFailed(Int32)
}

public struct CLIExecution: Equatable, Sendable {
    public let exitCode: Int32
    public let standardOutput: Data
    public let standardError: Data

    public init(exitCode: Int32, standardOutput: Data, standardError: Data) {
        self.exitCode = exitCode
        self.standardOutput = standardOutput
        self.standardError = standardError
    }
}

public actor SubprocessCLIClient {
    public static let maximumStandardOutputBytes = 4 * 1_024 * 1_024
    public static let maximumStandardErrorBytes = 256 * 1_024
    public static let maximumProgressLineBytes = 8 * 1_024
    public static let maximumProgressEvents = 20_000

    private var currentPID: pid_t?
    private var currentControlDescriptor: Int32?

    public init() {}

    public func run(
        _ command: CLICommand,
        onProgress: @escaping @Sendable (CLIProgressEvent) async -> Void = { _ in }
    ) async throws -> CLIExecution {
        guard currentPID == nil else { throw SubprocessError.commandAlreadyRunning }
        let stdoutPipe = try POSIXPipe()
        let stderrPipe = try POSIXPipe()
        let progressPipe = try POSIXPipe()
        let controlPipe = try POSIXPipe()
        var actions: posix_spawn_file_actions_t? = nil
        var attributes: posix_spawnattr_t? = nil
        posix_spawn_file_actions_init(&actions)
        posix_spawnattr_init(&attributes)
        defer {
            posix_spawn_file_actions_destroy(&actions)
            posix_spawnattr_destroy(&attributes)
        }
        posix_spawn_file_actions_addopen(&actions, STDIN_FILENO, "/dev/null", O_RDONLY, 0)
        for descriptor in [stdoutPipe.read, stderrPipe.read, progressPipe.read, controlPipe.write] {
            posix_spawn_file_actions_addclose(&actions, descriptor)
        }
        posix_spawn_file_actions_adddup2(&actions, stdoutPipe.write, STDOUT_FILENO)
        posix_spawn_file_actions_adddup2(&actions, stderrPipe.write, STDERR_FILENO)
        posix_spawn_file_actions_adddup2(&actions, progressPipe.write, 3)
        posix_spawn_file_actions_adddup2(&actions, controlPipe.read, 4)
        for descriptor in [stdoutPipe.write, stderrPipe.write, progressPipe.write, controlPipe.read]
        where ![STDOUT_FILENO, STDERR_FILENO, 3, 4].contains(descriptor) {
            posix_spawn_file_actions_addclose(&actions, descriptor)
        }
        let flags = Int16(POSIX_SPAWN_SETPGROUP | POSIX_SPAWN_CLOEXEC_DEFAULT)
        posix_spawnattr_setflags(&attributes, flags)
        posix_spawnattr_setpgroup(&attributes, 0)

        let strings = [command.executable.path] + command.arguments
        let duplicated = strings.map { strdup($0) }
        defer { duplicated.forEach { free($0) } }
        var argumentPointers = duplicated + [nil]
        let environmentStrings = Self.childEnvironment()
        let duplicatedEnvironment = environmentStrings.map { strdup($0) }
        defer { duplicatedEnvironment.forEach { free($0) } }
        var environmentPointers = duplicatedEnvironment + [nil]
        var pid: pid_t = 0
        let spawnResult = posix_spawn(
            &pid,
            command.executable.path,
            &actions,
            &attributes,
            &argumentPointers,
            &environmentPointers
        )
        stdoutPipe.closeWrite()
        stderrPipe.closeWrite()
        progressPipe.closeWrite()
        controlPipe.closeRead()
        guard spawnResult == 0 else {
            stdoutPipe.closeRead()
            stderrPipe.closeRead()
            progressPipe.closeRead()
            controlPipe.closeWrite()
            throw SubprocessError.spawnFailed(spawnResult)
        }
        let childPID = pid
        currentPID = childPID
        currentControlDescriptor = controlPipe.takeWrite()
        let stdoutRead = stdoutPipe.takeRead()
        let stderrRead = stderrPipe.takeRead()
        let progressRead = progressPipe.takeRead()
        let stdoutTask = Task.detached(priority: .utility) { @Sendable in
            try Self.readAll(
                descriptor: stdoutRead,
                maximumBytes: Self.maximumStandardOutputBytes,
                stream: "stdout",
                processGroup: childPID
            )
        }
        let stderrTask = Task.detached(priority: .utility) { @Sendable in
            try Self.readAll(
                descriptor: stderrRead,
                maximumBytes: Self.maximumStandardErrorBytes,
                stream: "stderr",
                processGroup: childPID
            )
        }
        let progressTask = Task.detached(priority: .utility) { @Sendable in
            try await Self.readProgress(
                descriptor: progressRead,
                processGroup: childPID,
                onProgress: onProgress
            )
        }
        let waitTask = Task.detached(priority: .utility) { @Sendable in
            try Self.wait(for: childPID)
        }
        do {
            let status = try await waitTask.value
            let output = try await stdoutTask.value
            let error = try await stderrTask.value
            try await progressTask.value
            clearCurrent()
            return CLIExecution(
                exitCode: Self.exitCode(status),
                standardOutput: output,
                standardError: error
            )
        } catch {
            kill(-childPID, SIGKILL)
            _ = try? await waitTask.value
            _ = try? await stdoutTask.value
            _ = try? await stderrTask.value
            _ = try? await progressTask.value
            clearCurrent()
            throw error
        }
    }

    public func finishRecording() throws {
        try writeControl("finish\n")
    }

    public func cancelCurrentCommand() throws {
        guard let pid = currentPID else { return }
        try writeControl("cancel\n")
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(5))
            await self?.forceStopIfCurrent(pid)
        }
    }

    private func writeControl(_ value: String) throws {
        guard let descriptor = currentControlDescriptor else { return }
        let data = Data(value.utf8)
        let result = data.withUnsafeBytes { bytes in
            Darwin.write(descriptor, bytes.baseAddress, bytes.count)
        }
        guard result == data.count else { throw SubprocessError.writeFailed(errno) }
    }

    private func forceStopIfCurrent(_ pid: pid_t) {
        guard currentPID == pid else { return }
        kill(-pid, SIGTERM)
    }

    private func clearCurrent() {
        if let descriptor = currentControlDescriptor { Darwin.close(descriptor) }
        currentControlDescriptor = nil
        currentPID = nil
    }

    private nonisolated static func readAll(
        descriptor: Int32,
        maximumBytes: Int,
        stream: String,
        processGroup: pid_t
    ) throws -> Data {
        defer { Darwin.close(descriptor) }
        var output = Data()
        var buffer = [UInt8](repeating: 0, count: 16 * 1_024)
        while true {
            let count = Darwin.read(descriptor, &buffer, buffer.count)
            if count == 0 { return output }
            if count < 0 {
                if errno == EINTR { continue }
                throw SubprocessError.readFailed(errno)
            }
            if output.count + count > maximumBytes {
                kill(-processGroup, SIGKILL)
                throw SubprocessError.outputExceededLimit(
                    stream: stream,
                    maximumBytes: maximumBytes
                )
            }
            output.append(buffer, count: count)
        }
    }

    private nonisolated static func readProgress(
        descriptor: Int32,
        processGroup: pid_t,
        onProgress: @escaping @Sendable (CLIProgressEvent) async -> Void
    ) async throws {
        defer { Darwin.close(descriptor) }
        var pending = Data()
        var buffer = [UInt8](repeating: 0, count: 4 * 1_024)
        var expectedSequence = 0
        var events = 0
        while true {
            let count = Darwin.read(descriptor, &buffer, buffer.count)
            if count < 0 {
                if errno == EINTR { continue }
                throw SubprocessError.readFailed(errno)
            }
            if count == 0 {
                guard pending.isEmpty else {
                    kill(-processGroup, SIGKILL)
                    throw SubprocessError.invalidProgress
                }
                return
            }
            pending.append(buffer, count: count)
            if pending.count > maximumProgressLineBytes && !pending.contains(0x0A) {
                kill(-processGroup, SIGKILL)
                throw SubprocessError.progressLineExceededLimit
            }
            while let newline = pending.firstIndex(of: 0x0A) {
                let line = pending.prefix(upTo: newline)
                pending.removeSubrange(...newline)
                guard !line.isEmpty, line.count <= maximumProgressLineBytes else {
                    kill(-processGroup, SIGKILL)
                    throw SubprocessError.progressLineExceededLimit
                }
                events += 1
                guard events <= maximumProgressEvents else {
                    kill(-processGroup, SIGKILL)
                    throw SubprocessError.tooManyProgressEvents
                }
                let event = try ContractDecoder.decode(
                    CLIProgressEvent.self,
                    from: Data(line),
                    maximumBytes: maximumProgressLineBytes
                )
                guard event.sequence == expectedSequence else {
                    kill(-processGroup, SIGKILL)
                    throw SubprocessError.invalidProgress
                }
                expectedSequence += 1
                await onProgress(event)
            }
        }
    }

    private nonisolated static func wait(for pid: pid_t) throws -> Int32 {
        var status: Int32 = 0
        while true {
            let result = waitpid(pid, &status, 0)
            if result == pid { return status }
            if result < 0 && errno == EINTR { continue }
            throw SubprocessError.waitFailed(errno)
        }
    }

    private nonisolated static func exitCode(_ status: Int32) -> Int32 {
        if status & 0x7F == 0 { return (status >> 8) & 0xFF }
        return 128 + (status & 0x7F)
    }

    private nonisolated static func childEnvironment() -> [String] {
        let inherited = ProcessInfo.processInfo.environment
        var values = ["PATH=/usr/bin:/bin", "LANG=en_US.UTF-8"]
        for key in [
            "HOME", "TMPDIR", "CUTNOTES_FFMPEG", "CUTNOTES_FFPROBE",
            "CUTNOTES_LOCAL_ENGINE", "CUTNOTES_PARAKEET_MODEL",
            "CUTNOTES_MACWHISPER", "CUTNOTES_CODEX",
        ] {
            if let value = inherited[key], !value.contains("\0") {
                values.append("\(key)=\(value)")
            }
        }
        return values
    }
}

private final class POSIXPipe: @unchecked Sendable {
    private let lock = NSLock()
    private var readDescriptor: Int32
    private var writeDescriptor: Int32

    var read: Int32 { lock.withLock { readDescriptor } }
    var write: Int32 { lock.withLock { writeDescriptor } }

    init() throws {
        var descriptors: [Int32] = [0, 0]
        guard Darwin.pipe(&descriptors) == 0 else { throw SubprocessError.pipeCreation(errno) }
        readDescriptor = descriptors[0]
        writeDescriptor = descriptors[1]
    }

    deinit {
        closeRead()
        closeWrite()
    }

    func takeRead() -> Int32 {
        lock.withLock {
            let descriptor = readDescriptor
            readDescriptor = -1
            return descriptor
        }
    }

    func takeWrite() -> Int32 {
        lock.withLock {
            let descriptor = writeDescriptor
            writeDescriptor = -1
            return descriptor
        }
    }

    func closeRead() {
        lock.withLock {
            if readDescriptor >= 0 { Darwin.close(readDescriptor); readDescriptor = -1 }
        }
    }

    func closeWrite() {
        lock.withLock {
            if writeDescriptor >= 0 { Darwin.close(writeDescriptor); writeDescriptor = -1 }
        }
    }
}
