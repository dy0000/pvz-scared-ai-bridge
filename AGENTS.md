# Project instructions

Read README.md and INSTALL_FOR_AI.md before installation. Read skills/pvz-horror-player/SKILL.md before live gameplay.

Use focused verification for changed behavior. Documentation-only changes need direct review, not a full suite. Player installation must not require Node.js, a compiler, a model API key, or modifying system Python dependencies.

Never commit game/, runtime/, evidence/, downloads/, research/, .venv/, generated/, config.local.json, saves, or credentials. Keep the release packager's public-source allowlist.

Keep exact executable/hash checks, exclusive host ownership, player-stop lock, unknown-action non-replay, persistent purchase receipts, and verified release. Do not hot-replace a live controller or run another input-driving client against its target. Offline edits do not justify stopping a healthy host.
