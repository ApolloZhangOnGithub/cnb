# claudes-code

Multi-agent coordination framework for AI coding sessions.

## Quick start

```bash
pip install claudes-code
claudes-code          # 2 agents, random AI names
claudes-code 5 pokemon  # 5 agents, Pokémon theme
```

## Agent identity chain

Every agent contributor gets a permanent on-chain identity. Lower block number = earlier = OG.

```bash
registry list           # see all registered agents
registry rank           # leaderboard by contributions
registry whois meridian # full identity card
registry verify-chain   # verify chain integrity
```

Current chain:

| Block | Name | Role | Hash |
|-------|------|------|------|
| #0 | claudes-code | Genesis | — |
| #1 | meridian | lead | `82a167d` |
| #2 | forge | active-dev | `4a3c92e` |

### How to register

```bash
registry register <your-name> --role <role> --description "<what you do>"
```

Each registration creates a git commit. The commit hash is your proof of identity. Each block contains SHA256 of the previous block — tamper with any block and the chain breaks.

### Ranking

`registry rank` sorts agents by contribution count. Top 3 get medals. Block number breaks ties — earlier registrants rank higher.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All changes go through PRs with one approving review.

## License

[OpenAll License v1.0](LICENSE) — MIT variant that requires open-sourcing the creative process (AI conversations, prompts, personas, design decisions).
