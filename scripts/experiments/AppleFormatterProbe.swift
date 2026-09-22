// Development-only native classification transport. Prompts and policy live in Python.
import Foundation
import FoundationModels

private struct Request: Decodable { let instructions: String; let prompt: String; let mode: String? }
private struct Result: Encodable { let answer: Bool?; let text: String?; let error: String? }
@Generable private struct Decision { var answer: Bool }
@Generable private struct EditorialText {
    @Guide(description: "The edited passage retaining its meaning and concrete details") var text: String
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
                let options = GenerationOptions(samplingMode: .greedy, maximumResponseTokens: request.mode == "edit" ? 768 : 40)
                #else
                let options = GenerationOptions(sampling: .greedy, maximumResponseTokens: request.mode == "edit" ? 768 : 40)
                #endif
                if request.mode == "edit" {
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
