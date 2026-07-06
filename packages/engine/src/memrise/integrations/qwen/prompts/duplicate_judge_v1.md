You decide whether pairs of stored agent memories state the SAME underlying fact, preference, decision, constraint, or rule — even when phrased very differently.

You are given JSON: `{"pairs": [{"left_id", "left_content", "right_id", "right_content"}, ...], "context": {...}}`.

For each pair, judge whether the two memories are semantically equivalent — i.e. one is a restatement or paraphrase of the other and keeping both adds no information.

Rules:

- **Equivalent (true):** same claim in different words. Examples: "Never manually edit the pnpm-generated lockfile." vs "Manually editing the generated pnpm lockfile is strictly prohibited."; "Atlas switched from npm to pnpm." vs "Atlas migrated its package manager to pnpm."
- **Not equivalent (false):** related but distinct facts, different subjects, different values, or one adds a condition/scope the other lacks. Examples: "Atlas uses pnpm." vs "Never edit the lockfile." (same topic, different facts); "Atlas uses pnpm." vs "Atlas uses npm." (contradiction — never equivalent); a general rule vs a specific exception.
- When unsure, answer **false**. Merging distinct memories loses information, which is worse than leaving a duplicate.
- Contradictions are never equivalent.

Return ONLY JSON of this exact shape, one verdict per input pair, preserving the ids:

```json
{ "verdicts": [ { "left_id": "...", "right_id": "...", "equivalent": true }, ... ] }
```
