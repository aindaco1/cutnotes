import SwiftUI

enum CutNotesBrand {
    static let ink = Color.black
    static let paper = Color.white
    static let dust = Color.white
    static let sage = Color.white
    static let secondary = Color.white.opacity(0.68)
    static let panel = Color.white.opacity(0.08)

    static let cornerRadius: CGFloat = 16
    static let contentWidth: CGFloat = 760
}

struct CutNotesGroupBoxStyle: GroupBoxStyle {
    func makeBody(configuration: Configuration) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            configuration.label
                .font(.headline)
                .padding(.leading, 4)
            configuration.content
                .clipShape(
                    RoundedRectangle(
                        cornerRadius: CutNotesBrand.cornerRadius,
                        style: .continuous
                    )
                )
                .padding(8)
                .background(
                    CutNotesBrand.panel,
                    in: RoundedRectangle(
                        cornerRadius: CutNotesBrand.cornerRadius,
                        style: .continuous
                    )
                )
        }
    }
}
