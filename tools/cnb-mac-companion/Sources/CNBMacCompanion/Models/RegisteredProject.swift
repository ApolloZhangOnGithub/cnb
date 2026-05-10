import Foundation

struct ProjectRegistry: Decodable {
    var projects: [RegisteredProject]
}

struct RegisteredProject: Decodable {
    var path: String
    var name: String?
    var lastActive: Date?

    enum CodingKeys: String, CodingKey {
        case path
        case name
        case lastActive = "last_active"
    }
}
