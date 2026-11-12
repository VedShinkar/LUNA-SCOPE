# GitHub Projects Board Setup

## Create the board
1. Sign in to GitHub.
2. Open your profile, select Projects, then New project.
3. Choose the **Board** layout.
4. Name it `LUNA-SCOPE — Engineering Development Board`.
5. Click Create project.

## Link the repository
After the LUNA-SCOPE repository exists:
1. Open the repository and select its **Projects** tab.
2. Choose **Link a project**.
3. Select `LUNA-SCOPE — Engineering Development Board`.

## Configure the board
Use a Status field with:
- Backlog
- Ready
- In Progress
- In Review
- Done

Recommended additional fields:
- Priority: P0 / P1 / P2
- Workstream: Terrain / Geometry / Mission Intelligence / Integration / Documentation
- Target date: date

Create repository Issues for tasks with owners and acceptance criteria, then add those Issues to the Project board. Use branches and pull requests for code changes.

## Suggested first issues
1. Agree lunar coordinate and time conventions.
2. Catalogue NASA terrain and ephemeris datasets.
3. Create the frontend application shell.
4. Create the backend application shell.
5. Define the first API contracts.
6. Build a LOLA DEM metadata inspection script.
7. Build a SPICE environment and kernel validation test.
