# Contributing to LUNA-SCOPE

## Before starting
- Read `README.md` and the relevant documents in `docs/`.
- Check the GitHub Project board and take an assigned issue.
- Confirm issue ownership, dependencies, expected output and acceptance criteria.
- Do not start cross-module integration until the shared coordinate conventions and versioned data contracts are agreed.

## Branch naming
Prefer issue-specific branches:
- `feat/<issue-number>-<short-name>`
- `fix/<issue-number>-<short-name>`
- `docs/<issue-number>-<short-name>`
- `test/<issue-number>-<short-name>`

Examples: `feat/7-terrain-dem-pipeline`, `feat/11-spice-sun-earth-positions`.

## Commit messages
Use concise conventional-style messages:
- `feat: add lunar DEM metadata reader`
- `fix: correct longitude conversion`
- `docs: document time conventions`
- `test: add horizon geometry cases`

## Pull requests
- Open PRs against `main` and reference the issue (for example, `Closes #7`).
- Keep PRs focused on one issue where practical.
- Explain behavior, tests and any migration/data requirements.
- Include screenshots for visual changes.
- For scientific changes, state source/kernel identifiers, coordinate/time frames, units, model assumptions, validation and limitations.
- Request review; do not merge unreviewed scientific changes.

## Scientific integrity
Never fabricate ephemeris, terrain, illumination, power, thermal or communication values. Clearly label synthetic fixtures and user assumptions. Every scientific output must be traceable to inputs, data versions, model assumptions, units and validation tests. Missing data must not be silently converted to zero or a successful feasibility result.

## Data and secrets
Never commit `.env`, API keys, passwords, private credentials, large source datasets or SPICE kernels. Add dataset provenance and retrieval instructions to `docs/DATA_SOURCES.md`.
