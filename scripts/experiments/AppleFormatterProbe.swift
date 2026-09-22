// Development-only native classification transport. Prompts and policy live in Python.
import Foundation
import FoundationModels

private struct Request: Decodable { let instructions: String; let prompt: String; let mode: String? }
private struct Result: Encodable {
    var answer: Bool? = nil
    var text: String? = nil
    var facts: [EvidenceFact]? = nil
    var relevance: PassageRelevance? = nil
    var error: String? = nil
}
@Generable private struct Decision { var answer: Bool }
@Generable private struct EditorialText {
    @Guide(description: "The edited passage retaining its meaning and concrete details") var text: String
}
@Generable private enum FactRole: String, Encodable {
    case observation, request, qualification
}
@Generable private struct EvidenceFact: Encodable {
    @Guide(description: "An exact, unchanged quote from the input, containing one complete statement")
    var quote: String
    var role: FactRole
}
@Generable private struct EvidenceFacts {
    @Guide(.maximumCount(12)) var facts: [EvidenceFact]
}
@Generable private enum PassageRole: String, Encodable {
    case feedback, conversation, unclear
}
@Generable private struct PassageRelevance: Encodable {
    @Guide(description: "An exact quote from the target passage supporting the classification")
    var quote: String
    var role: PassageRole
}

@main struct AppleFormatterProbe {
    static func main() async throws {
        let model = SystemLanguageModel(useCase: .general, guardrails: .permissiveContentTransformations)
        while let line = readLine() {
            let result: Result
            do {
                let request = try JSONDecoder().decode(Request.self, from: Data(line.utf8))
                guard model.availability == .available else {
                    throw NSError(domain: "AppleFormatterProbe", code: 1,
                                  userInfo: [NSLocalizedDescriptionKey: "Apple model unavailable"])
                }
                let session = LanguageModelSession(model: model, instructions: request.instructions)
                #if compiler(>=6.4)
                let options = GenerationOptions(samplingMode: .greedy, maximumResponseTokens: request.mode == nil ? 40 : request.mode == "facts" ? 1024 : 768)
                #else
                let options = GenerationOptions(sampling: .greedy, maximumResponseTokens: request.mode == nil ? 40 : request.mode == "facts" ? 1024 : 768)
                #endif
                if request.mode == "text" {
                    let response = try await session.respond(to: request.prompt, options: options)
                    result = Result(text: response.content)
                } else if request.mode == "facts" {
                    let response = try await session.respond(to: request.prompt, generating: EvidenceFacts.self, options: options)
                    result = Result(facts: response.content.facts)
                } else if request.mode == "relevance" {
                    let response = try await session.respond(to: request.prompt, generating: PassageRelevance.self, options: options)
                    result = Result(relevance: response.content)
                } else if request.mode == "edit" {
                    let response = try await session.respond(to: request.prompt, generating: EditorialText.self, options: options)
                    result = Result(answer: nil, text: response.content.text, error: nil)
                } else {
                    let response = try await session.respond(to: request.prompt, generating: Decision.self, options: options)
                    result = Result(answer: response.content.answer, text: nil, error: nil)
                }
            } catch {
                result = Result(answer: nil, text: nil, error: String(describing: error))
            }
            FileHandle.standardOutput.write(try JSONEncoder().encode(result))
            FileHandle.standardOutput.write(Data("\n".utf8))
        }
    }
}
