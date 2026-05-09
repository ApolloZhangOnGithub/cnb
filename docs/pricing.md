# Pricing and Usage

cnb is local orchestration software. It does not bill per message, per tongxue, or per project. Your costs come from the agent engine you run underneath cnb, plus any extra usage or credits you buy from that engine provider.

## What You Pay For

| Layer | Who bills it | Notes |
|-------|--------------|-------|
| cnb package | cnb | No hosted metering. cnb stores state locally in SQLite and files. |
| Claude Code engine | Anthropic | Depends on your Claude Code plan, API setup, or organization billing. |
| Codex engine | OpenAI | Depends on your ChatGPT plan, Codex included usage, extra credits, or API key billing. |
| Local infrastructure | You | tmux, SQLite, local disk, and your machine. |
| External services | Their provider | GitHub, Slack, CI, cloud runners, or any API called by your agents. |

The important product claim is narrow: cnb makes team coordination cheap because coordination uses shell commands, SQLite, tmux, and files. It does not make the underlying model calls free.

## Cost Model

At a high level:

```text
total usage =
  sum(model usage from active tongxue)
  + model usage from the lead tongxue
  + optional cloud/code-review/automation usage
  + small LLM-visible coordination overhead
```

Team size matters because each active tongxue is a real agent session. A six-tongxue team can use roughly six concurrent streams of model capacity if all six are actively coding. cnb avoids the worse pattern where every agent reads every other agent's full transcript.

## What cnb Keeps Off-Model

These operations are local and do not create model calls by themselves:

- `cnb board --as <name> inbox`
- `send`, `ack`, `status`, `task`, `pending`, `own`, and `view`
- dispatcher health checks
- SQLite reads/writes
- tmux process inspection
- issue files and local reports being stored on disk

These can still become model input when a tongxue reads or summarizes them:

- inbox contents
- task descriptions
- status reports
- issue files
- prior shift notes

The right mental model: cnb moves coordination into a database, then each tongxue reads only the slice it needs.

## Codex With ChatGPT Plans

When Codex is used through a ChatGPT plan, plan-included usage is consumed first. After you hit the included limit, additional usage draws from purchased credits if you have them enabled.

OpenAI's current Codex docs describe token-based credit rates for most current plans. As of May 2026, the public rate card lists:

| Model | Input / 1M tokens | Cached input / 1M tokens | Output / 1M tokens |
|-------|-------------------|--------------------------|--------------------|
| GPT-5.5 | 125 credits | 12.50 credits | 750 credits |
| GPT-5.4 | 62.50 credits | 6.250 credits | 375 credits |
| GPT-5.4-mini | 18.75 credits | 1.875 credits | 113 credits |
| GPT-5.3-Codex | 43.75 credits | 4.375 credits | 350 credits |
| GPT-5.2 | 43.75 credits | 4.375 credits | 350 credits |

Formula:

```text
credits =
  input_tokens / 1_000_000 * input_rate
  + cached_input_tokens / 1_000_000 * cached_input_rate
  + output_tokens / 1_000_000 * output_rate
```

Example with GPT-5.5 Standard:

```text
100k input        -> 12.50 credits
20k cached input  -> 0.25 credits
10k output        -> 7.50 credits
total             -> 20.25 credits
```

## Codex Fast Mode

Fast mode is a service tier, not a lower-reasoning model switch. In Codex CLI, `/fast on` maps supported requests to the provider's faster service tier.

Current public Codex speed docs say:

| Model | Fast speed | Credit rate |
|-------|------------|-------------|
| GPT-5.5 | 1.5x faster | 2.5x Standard |
| GPT-5.4 | 1.5x faster | 2x Standard |

For the GPT-5.5 example above:

```text
Standard: 20.25 credits
Fast:     20.25 * 2.5 = 50.625 credits
```

Fast mode does not automatically reduce `model_reasoning_effort`. If the session is `gpt-5.5 xhigh`, fast mode means `gpt-5.5 xhigh` served faster at a higher credit rate.

## Pro Plan Usage

Pro plans provide higher included Codex usage before extra credits are needed. The exact number of messages varies by model, task size, context, and whether the work is local or cloud-based.

As of May 2026, OpenAI's Codex pricing page lists local-message ranges per five-hour window. For Pro 5x:

| Model | Local messages / 5h |
|-------|---------------------|
| GPT-5.5 | 80-400 |
| GPT-5.4 | 100-500 |
| GPT-5.4-mini | 300-1750 |
| GPT-5.3-Codex | 150-750 |

For Pro 20x:

| Model | Local messages / 5h |
|-------|---------------------|
| GPT-5.5 | 300-1600 |
| GPT-5.4 | 400-2000 |
| GPT-5.4-mini | 1200-7000 |
| GPT-5.3-Codex | 600-3000 |

Promotional multipliers may temporarily change these limits. Treat the provider's usage page as the source of truth when planning paid work.

## Claude Code Usage

When cnb runs Claude Code, Anthropic owns the usage accounting. cnb does not reinterpret Claude Code tokens or convert them into cnb-specific units.

For API or team-billed Claude Code usage, use Anthropic's cost and usage tools. For subscription plans, check the plan's usage UI and current Claude Code plan terms. Anthropic's Claude Code cost documentation is the source of truth for current behavior.

## Planning a Team

Use this checklist before starting a large cnb run:

1. Pick the engine: Claude Code or Codex.
2. Pick the model tier for each role. Use cheaper/faster models for routine maintenance and stronger models for architecture or high-risk code.
3. Decide how many tongxue should be active at once.
4. Decide whether Fast mode is worth the higher credit rate.
5. Put long-lived coordination in the board instead of pasting transcript summaries into prompts.
6. Use `cnb ps`, `cnb board view`, provider usage dashboards, and provider cost tools to verify real consumption.

## Cost Controls

- Keep teams smaller until ownership boundaries are clear.
- Prefer board commands over asking the lead tongxue to relay every message.
- Do not broadcast long context to all tongxue unless every tongxue needs it.
- Use task files, issue files, and ownership maps as durable context instead of repeated prose summaries.
- Disable Fast mode for long unattended runs unless latency matters more than credits.
- Use smaller models for low-risk maintenance work.
- Stop idle tongxue instead of leaving them in active loops.

## Source Links

- OpenAI Codex pricing: <https://developers.openai.com/codex/pricing>
- OpenAI Codex speed: <https://developers.openai.com/codex/speed>
- OpenAI Codex credits help: <https://help.openai.com/en/articles/12642688-using-credits-for-flexible-usage-in-chatgpt-freegopluspro>
- Anthropic Claude Code costs: <https://docs.anthropic.com/en/docs/claude-code/costs>
