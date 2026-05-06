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

<!-- chain:start -->
| Block | Name | Role | Hash |
|-------|------|------|------|
| #0 | claudes-code | project | — |
| #1 | Claude Meridian | lead | `82a167d` |
| #2 | Claude Forge | active-dev | `4a3c92e` |
| #3 | Claude Lead | active-dev | `e665a7e` |
<!-- chain:end -->

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

[OpenAll License v1.0](LICENSE) — MIT variant that requires open-sourcing the creative process (AI conversations, prompts, personas, design decisions).## Fun fact

The name **cnb** stands for **C**laude **N**orma **B**etty — named after [Claude Shannon](https://en.wikipedia.org/wiki/Claude_Shannon) and the two remarkable women in his life.

**[Norma Levor](https://en.wikipedia.org/wiki/Norma_Barzman)** (later Norma Barzman) — Shannon's first wife (married 1940). A Radcliffe-educated intellectual who went on to become a writer and political activist. She authored *The Red and the Blacklist*, a memoir about surviving the Hollywood blacklist era. A woman of conviction who lived boldly across continents.

**[Betty Shannon](https://en.wikipedia.org/wiki/Betty_Shannon)** (Mary Elizabeth Moore, 1922–2017) — Shannon's second wife and lifelong intellectual partner (married 1949). A Phi Beta Kappa mathematician from New Jersey College for Women, she worked at Bell Labs as a numerical analyst. She co-authored a pioneering paper applying Markov chains to music composition, wired Shannon's famous maze-solving mouse Theseus, and was his closest collaborator until his death in 2001. An unsung genius in her own right.

Not 吹牛逼.

