# Contributing to LUNA-SCOPE

## Before starting
- Read `README.md` and the relevant documents in `docs/`.
- Check the GitHub Project board and take an assigned issue.
- Confirm the issue's owner, expected output, and acceptance criteria.

## Branch naming
Use descriptive branches:
- `feature/<short-name>`
- `fix/<short-name>`
- `docs/<short-name>`
- `test/<short-name>`

Examples: `feature/lola-dem-reader`, `feature/spice-sun-vector`.

## Commit messages
Use concise conventional-style messages:
- `feat: add lunar DEM metadata reader`
- `fix: correct longitude conversion`
- `docs: document time conventions`
- `test: add horizon geometry cases`

## Pull requests
Keep each PR focused. Link the relevant issue, explain what changed and how it was tested, include screenshots for visual changes, and state data sources, units, assumptions, and limitations for scientific changes.

## Scientific integrity
Never fabricate ephemeris, terrain, illumination, power, thermal, or communication values. Clearly label mock data and assumptions. Every scientific output should be traceable to inputs, data versions, model assumptions, units, and validation tests.

## Data and secrets
Never commit `.env`, API keys, passwords, private credentials, large source datasets, or SPICE kernels. Add dataset provenance and retrieval instructions to `docs/DATA_SOURCES.md`.
