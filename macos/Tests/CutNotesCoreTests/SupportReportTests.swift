import Foundation
import Testing
@testable import CutNotesCore

private func application() -> SupportApplicationInfo {
    .init(version: "1.0.2", build: "3", operatingSystem: "26.0.0", architecture: "arm64")
}

private func state() -> CutNotesSupportState {
    .init(
        workflow: "format",
        isRunning: false,
        isRecording: false,
        isPaused: false,
        hasSource: true,
        transcriptOnly: false,
        language: "en",
        transcriber: "parakeet",
        formatter: "apple",
        usesSystemDefaultMicrophone: true,
        microphoneCount: 2,
        coreHealthy: true,
        defaultWorkflowReady: true,
        parakeetReady: true,
        appleFormatterReady: true,
        ffmpegAvailable: true,
        macwhisperAvailable: false,
        codexAvailable: true,
        progressStage: "formatting",
        failureCode: "apple_guardrail"
    )
}

@Test func currentStateReportIsStrictAndContainsNoProjectContent() throws {
    let report = CutNotesSupportReport(
        state: state(),
        application: application(),
        id: UUID(uuidString: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")!
    )
    #expect(report.isValid)
    let data = try JSONEncoder().encode(report)
    let json = String(decoding: data, as: UTF8.self)
    #expect(!json.contains("/Users/private"))
    #expect(!json.contains("secret transcript"))
    #expect(!json.contains("project"))
    #expect(json.contains("apple_guardrail"))

    let invalid = CutNotesSupportState(
        workflow: "format",
        isRunning: false,
        isRecording: false,
        isPaused: false,
        hasSource: true,
        transcriptOnly: false,
        language: "Private transcript",
        transcriber: "parakeet",
        formatter: "apple",
        usesSystemDefaultMicrophone: true,
        microphoneCount: 2,
        coreHealthy: true,
        defaultWorkflowReady: true,
        parakeetReady: true,
        appleFormatterReady: true,
        ffmpegAvailable: true,
        macwhisperAvailable: false,
        codexAvailable: true,
        progressStage: nil,
        failureCode: nil
    )
    #expect(!invalid.isValid)
}

@Test func nativeCrashParserProjectsOnlyAllowlistedFacts() throws {
    let id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    let header: [String: Any] = [
        "bundleID": "com.dustwave.cutnotes",
        "incident_id": id,
        "app_version": "1.0.2",
        "build_version": "3",
        "privatePath": "/Users/private/secret",
    ]
    let body: [String: Any] = [
        "procName": "CutNotes",
        "cpuType": "ARM-64",
        "osVersion": ["train": "macOS 26.0.0"],
        "exception": ["type": "EXC_BREAKPOINT", "signal": "SIGTRAP", "message": "private transcript"],
        "faultingThread": 0,
        "threads": [["frames": [
            ["imageIndex": 0, "imageOffset": 1234, "symbol": "privateFunction"],
            ["imageIndex": 1, "imageOffset": 9876],
        ]]],
        "usedImages": [["name": "SecretPlugin", "path": "/Users/private/plugin"], ["name": "CutNotes"]],
    ]
    let headerData = try JSONSerialization.data(withJSONObject: header)
    let bodyData = try JSONSerialization.data(withJSONObject: body)
    let report = CutNotesNativeCrashReports.parse(headerData + Data([10]) + bodyData)
    #expect(report?.isValid == true)
    #expect(report?.id == id)
    #expect(report?.crash?.image == "CutNotes")
    #expect(report?.crash?.imageOffset == 9876)
    let publicJSON = String(decoding: try JSONEncoder().encode(report), as: UTF8.self)
    #expect(!publicJSON.contains("private"))
    #expect(!publicJSON.contains("symbol"))
    #expect(!publicJSON.contains("path"))

    var otherHeader = header
    otherHeader["bundleID"] = "com.example.other"
    let other = try JSONSerialization.data(withJSONObject: otherHeader) + Data([10]) + bodyData
    #expect(CutNotesNativeCrashReports.parse(other) == nil)
}

@Test func submissionRequiresEnablementAndExactReceipt() async throws {
    let report = CutNotesSupportReport(state: state(), application: application())
    let disabledCalls = LockedCounter()
    let disabled = CutNotesSupportSubmissionClient(enabled: false) { _ in
        await disabledCalls.increment()
        throw CutNotesSupportSubmissionError.unavailable
    }
    await #expect(throws: CutNotesSupportSubmissionError.disabled) {
        try await disabled.submit(report)
    }
    #expect(await disabledCalls.value == 0)

    let receipt = try JSONEncoder().encode(TestReceipt(
        ok: true,
        reportId: report.id,
        action: "created",
        issueNumber: 42
    ))
    let accepted = CutNotesSupportSubmissionClient(enabled: true) { request in
        #expect(request.url == CutNotesSupportSubmissionClient.endpoint)
        #expect(request.httpMethod == "POST")
        return (receipt, HTTPURLResponse(
            url: CutNotesSupportSubmissionClient.endpoint,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!)
    }
    #expect(try await accepted.submit(report) == 42)

    let wrong = CutNotesSupportSubmissionClient(enabled: true) { _ in
        let data = try JSONEncoder().encode(TestReceipt(
            ok: true,
            reportId: UUID().uuidString.lowercased(),
            action: "created",
            issueNumber: 42
        ))
        return (data, HTTPURLResponse(
            url: CutNotesSupportSubmissionClient.endpoint,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!)
    }
    await #expect(throws: CutNotesSupportSubmissionError.rejected) {
        try await wrong.submit(report)
    }
}

private struct TestReceipt: Encodable {
    let ok: Bool
    let reportId: String
    let action: String
    let issueNumber: Int
}

private actor LockedCounter {
    private(set) var value = 0
    func increment() { value += 1 }
}
