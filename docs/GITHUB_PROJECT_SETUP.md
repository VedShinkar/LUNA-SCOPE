# GitHub Project Setup and Operating Guide

## Existing project

- Repository: https://github.com/VedShinkar/LUNA-SCOPE
- Project board: https://github.com/users/VedShinkar/projects
- Board name: `LUNA-SCOPE — Engineering Development Board`
- The current board screenshot showed 25 items in Backlog. The 25 repository issues have therefore been added to the board; do not recreate them as draft cards.
- Keep the duplicate draft card for coordinate conventions removed if it is still present, because repository issue #1 is the canonical task.

## Status workflow

Use these five statuses:

1. Backlog — planned but not yet ready.
2. Ready — dependencies satisfied and work can start.
3. In Progress — actively being implemented.
4. In Review — pull request or scientific review pending.
5. Done — acceptance criteria met, tests passed and PR merged.

Do not move an item to Done merely because coding is finished.

## Project custom fields to configure

In the Project board, open the view menu (gear icon) → Fields → New field.

### Priority
- Type: Single select
- Options: `P0 — Critical`, `P1 — Important`, `P2 — Enhancement`

### Workstream
- Type: Single select
- Options: `Terrain & Visualization`, `Celestial Mechanics`, `Mission Intelligence`, `Integration`, `Documentation`

### Target Date
- Type: Date
- Leave unset until the official submission/demo deadline and team availability are confirmed.

Keep the built-in Title, Status and Assignees fields. Do not create duplicate owner fields.

## One-click repository metadata setup

The workflow `.github/workflows/bootstrap-project-metadata.yml` creates repository labels and five phase milestones, then applies owner/workstream/priority labels and the appropriate milestone to issues #1–#25.

To run it:
1. Open the repository's Actions tab.
2. Select **Bootstrap LUNA-SCOPE labels and milestones**.
3. Click **Run workflow**.
4. Keep branch set to `main` and run.
5. Open the workflow run and confirm it completes successfully.
6. Check Issues → Labels and Issues → Milestones.

The workflow is safe to rerun: it checks for existing labels and milestones before creating them, then reapplies the intended issue metadata.

It requires the repository's GitHub Actions workflow to be enabled and the workflow token to have issue write permission.

## Milestones

- Phase 0 — Foundations: #1, #3, #4, #16, #24
- Phase 1 — First vertical slices: #2, #5, #6, #7, #10, #11, #15, #17, #18
- Phase 2 — Terrain-aware environment: #8, #9, #12, #13, #14
- Phase 3 — Mission intelligence: #19, #20, #21
- Phase 4 — Integration & demo: #22, #23, #25

Milestones intentionally have no calendar due dates yet. Add due dates only after the official challenge deadline and realistic work estimates are known.

## Dependencies

The dependency map is maintained in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md). GitHub issue bodies also name their dependencies. Treat those as blockers: do not start downstream integration until required upstream contracts/results are available.

## Views

Recommended views:
- **Board:** group by Status; use for daily execution.
- **Engineering Tasks:** Table with Title, Status, Assignees, Priority, Workstream and Target Date.
- **Mission Roadmap:** Roadmap grouped by Target Date after dates are agreed.

For the Board view, use Workstream or Priority filters to focus a work session. For the Table view, sort by Priority and then Target Date.

## Team access and assignment

When teammate GitHub usernames are available:
1. Add them as repository collaborators with Write access.
2. Add them to the private Project board separately.
3. Assign issues by the Member 1/2/3 labels and the task ownership table.
4. Keep shared issues unassigned or assign a named coordinator plus reviewers.
5. Confirm each teammate can see the repository, board and issue discussions.

## Repository settings to apply manually

The connected GitHub integration can create issues and repository files, but it does not expose Project V2 field editing, repository label/milestone creation, collaborator invitations or branch-protection mutation. Use GitHub's UI for:
- Add the custom Project fields above.
- Add teammates and Project access.
- Settings → Branches → add a ruleset for `main`: require pull requests, require at least one approval when the team is ready, require status checks once CI exists, and block force pushes/deletions.
- Do not require status checks until the corresponding CI workflow exists and is passing.
