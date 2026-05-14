import Foundation

struct CNBLiveStateReader {
    func read() throws -> CNBLiveState {
        let data = try CNBRuntimeFileLocator.data(
            named: "live_state.json",
            overrideEnvironmentKey: "CNB_LIVE_STATE_PATH"
        )
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(CNBLiveState.self, from: data)
    }
}
