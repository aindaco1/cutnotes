import Foundation
import XCTest
@testable import CutNotesLocal

final class EditorialDraftTests: XCTestCase {
    func testDraftContractRoundTripsGrounding() throws {
        let note = EditorialDraftNotePayload(
            title: "Impact", body: "Align the sound with the impact.", sourceIDs: ["N0001", "N0002"]
        )
        let envelope = EditorialDraftEnvelope(draft: EditorialDraftPayload(notes: [note]))
        let data = try JSONEncoder().encode(envelope)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(json["schema_version"] as? String, "cutnotes.local.draft.v1")
        let payloadData = try JSONSerialization.data(withJSONObject: XCTUnwrap(json["draft"]))
        let decoded = try JSONDecoder().decode(EditorialDraftPayload.self, from: payloadData)
        XCTAssertEqual(decoded.notes[0].sourceIDs, ["N0001", "N0002"])
        XCTAssertEqual(decoded.notes[0].body, note.body)
    }

    func testDraftContractRequiresGroundingIDs() throws {
        let malformed = Data(#"{"title":"Impact","body":"Align it."}"#.utf8)
        XCTAssertThrowsError(try JSONDecoder().decode(EditorialDraftNotePayload.self, from: malformed))
    }
}
