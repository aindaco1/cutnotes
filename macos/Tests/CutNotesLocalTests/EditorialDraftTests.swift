import Foundation
import XCTest
@testable import CutNotesLocal

final class EditorialDraftTests: XCTestCase {
    func testEditorialResultsRoundTripFalseAndText() throws {
        for result in [EditorialResultPayload(answer: false), EditorialResultPayload(text: "The light is warm.")] {
            let data = try JSONEncoder().encode(EditorialResultEnvelope(result: result))
            let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
            XCTAssertEqual(json["schema_version"] as? String, "cutnotes.local.editorial.v1")
            let decoded = try JSONDecoder().decode(EditorialResultPayload.self,
                from: JSONSerialization.data(withJSONObject: XCTUnwrap(json["result"])))
            XCTAssertEqual(decoded.answer, result.answer)
            XCTAssertEqual(decoded.text, result.text)
        }
    }

    func testEditorialResultRejectsStringInsteadOfBoolean() {
        XCTAssertThrowsError(try JSONDecoder().decode(EditorialResultPayload.self, from: Data(#"{"answer":"false"}"#.utf8)))
    }
    func testCompatiblePromptRemovesOnlyDuplicatedInstructions() {
        let instructions = "Preserve the feedback."
        let source = "<source>Private transcript</source>"
        XCTAssertEqual(draftSourcePrompt(instructions + "\n\n" + source, instructions: instructions), source)
        XCTAssertEqual(draftSourcePrompt(source, instructions: instructions), source)
        XCTAssertEqual(draftSourcePrompt(instructions + "\n" + source, instructions: instructions), instructions + "\n" + source)
    }

    func testLegacyPromptWithoutSeparateInstructionsRemainsWhole() {
        let prompt = "Task instructions\n\n<source>Private transcript</source>"
        XCTAssertEqual(draftSourcePrompt(prompt, instructions: nil), prompt)
        XCTAssertEqual(draftSourcePrompt(prompt, instructions: ""), prompt)
    }

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
