# Tongxue Avatar Generation

cnb needs recognizable avatars for tongxue identities, but the default path must be safe enough for public GitHub display and cheap enough for automatic creation.

## Decision

Use original, non-photorealistic character avatars by default.

Recommended default provider:

- OpenAI `gpt-image-1-mini`
- square avatar output
- medium quality for normal use
- 3-4 candidates per tongxue
- prompt from role metadata, not from a celebrity photo

Escalation providers:

- `gpt-image-1.5` for a more polished first batch
- `gpt-image-2` for brand-level or homepage art
- Apple Image Playground / `ImageCreator` as a local Apple-platform provider when cnb is running inside a native Mac or iOS app

## Why Not Real Celebrity Likeness

The product goal is "musk tongxue", "lisa-su tongxue", or "lecun tongxue", not an impersonation of the living public figure. Public avatars should avoid:

- using celebrity names as the visual target
- uploading celebrity photos as reference images
- photorealistic likeness generation
- official company logos, badges, or brand marks
- anything that could confuse a GitHub viewer into thinking the App is endorsed by the real person

OpenAI policy restricts use of someone's likeness, including photorealistic image or voice, without consent in ways that could confuse authenticity. Google Imagen also frames generated imagery around original content and safety filtering rather than replication. This means "very realistic and very similar to a public figure" is the wrong default requirement for cnb.

## Prompt Shape

Generate avatars from the role, domain, and visual cues:

```text
Original cute editorial avatar, not a real person, not photorealistic.
Subject: a mischievous rocket-building engineer mascot.
Visual cues: dark hair silhouette, black jacket, tiny rocket pin, confident smirk.
Mood: playful founder energy, sharp but friendly.
Style: polished sticker avatar, soft 3D illustration, clean GitHub crop.
Constraints: no celebrity likeness, no official logos, no readable text.
```

For `lisa-su`, use semiconductor and leadership cues. For `lecun`, use research, neural nets, and chalkboard cues. The prompt should never ask for the real person.

## Provider Notes

### OpenAI GPT Image

OpenAI is the best default for headless automation:

- straightforward API
- predictable pricing tiers
- good prompt following
- content filtering that matches the safety boundary cnb needs
- easy to call from a future `cnb avatar create <name>` command

Use `gpt-image-1-mini` first because avatar images are small and tolerate stylization well. Move to `gpt-image-1.5` or `gpt-image-2` only when visual quality matters more than cost.

### Apple Image Playground

Apple is a useful local fallback, especially for a future cnb Mac companion app:

- Image Playground can be embedded in SwiftUI, AppKit, and UIKit apps.
- `ImageCreator` can generate images programmatically.
- Apple says images are generated on device, so cnb does not need to host a model for that path.

This is less useful as the default automation backend:

- it depends on Apple Intelligence support, OS version, region, language, and hardware
- it is tied to native app execution rather than a simple cloud API
- it may be less flexible for batch headless avatar generation
- it is intentionally stylized, which is good for safety but may not satisfy users asking for realistic likeness

Recommendation: keep Apple as `provider = "apple-image-playground"` behind a capability check, not as the default provider.

### Flux / Stability / Other Less Restrictive Providers

Do not use a less restrictive provider just to get closer celebrity likeness. That would optimize for bypassing safety rather than building a durable product. These providers can be reconsidered for fully original non-person characters, but they should not be the default public identity path.

## Product Workflow

Future command:

```bash
cnb avatar create musk
```

Expected behavior:

1. Read tongxue metadata: name, role, domain, color, symbols.
2. Build a safe original-character prompt.
3. Generate 3-4 candidates.
4. Save the selected output under a stable identity path.
5. Store generation metadata:
   - provider
   - model
   - prompt
   - timestamp
   - source tongxue metadata
   - `likeness_policy = "original_character"`
6. Never upload the avatar to GitHub automatically unless the target App and repository are allowlisted.

## Acceptance Criteria

- Default prompts do not contain real public figure names as likeness targets.
- The generated image is an original character, not a photorealistic public figure.
- Provider choice is explicit and recorded.
- Avatar generation works without human image editing.
- GitHub upload remains a separate, guarded operation.

## Sources

- [OpenAI image generation docs](https://developers.openai.com/api/docs/guides/image-generation)
- [OpenAI usage policies](https://openai.com/policies/usage-policies/)
- [Apple Intelligence developer pathway](https://developer.apple.com/apple-intelligence/get-started/)
- [Google Imagen responsible AI guidance](https://cloud.google.com/vertex-ai/generative-ai/docs/image/responsible-ai-imagen)
