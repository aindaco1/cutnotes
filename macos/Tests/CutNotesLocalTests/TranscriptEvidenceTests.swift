import Foundation
import DustWaveSpeech
import XCTest
@testable import CutNotesLocal

final class TranscriptEvidenceTests: XCTestCase {
    func testEvidenceRetainsLowConfidenceNegationAndRecordingOffsets() throws {
        let transcript = ParakeetTranscriptResult(
            text: "Do not cut it.", durationSeconds: 3, confidence: 0.8,
            tokens: [.init(text: "not", tokenId: 17, startsAtSeconds: 1,
                           endsAtSeconds: 1.2, confidence: 0.01)],
            words: [.init(text: "not", startsAtSeconds: 1, endsAtSeconds: 1.2)]
        )
        let encoded = try JSONEncoder().encode(TranscriptEvidencePayload(transcript))
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: encoded) as? [String: Any])
        XCTAssertEqual(json["schema_version"] as? String, "cutnotes.local.transcript-evidence.v1")
        XCTAssertEqual(json["duration_seconds"] as? Double, 3)
        let decoded = try JSONDecoder().decode(TranscriptEvidencePayload.self, from: encoded)
        XCTAssertEqual(decoded.text, "Do not cut it.")
        XCTAssertEqual(decoded.tokens[0].text, "not")
        XCTAssertEqual(decoded.tokens[0].confidence, 0.01)
        XCTAssertEqual(decoded.words[0].start, 1)
    }

    func testEvidenceRequiresRecordingOffsets() {
        let data = Data(#"{"schema_version":"cutnotes.local.transcript-evidence.v1","text":"Hello","duration_seconds":1,"tokens":[],"words":[{"text":"Hello"}]}"#.utf8)
        XCTAssertThrowsError(try JSONDecoder().decode(TranscriptEvidencePayload.self, from: data))
    }
}
