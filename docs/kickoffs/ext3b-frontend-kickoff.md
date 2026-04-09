# Extension 3b Frontend — Consolidated Kickoff Prompt

**How to use this file:** Paste the entire body below (from "BEGIN KICKOFF" to "END KICKOFF") into a fresh Claude Code session on a new `prodoc/ext3b-templates-ui` branch off `preview`. Do this ONLY after Extension 3 has been merged and tagged as `prodoc-ext3`.

**Pre-flight checklist before pasting:**

1. Confirm `prodoc-ext3` tag exists and is reachable from `preview`.
2. Confirm the Extension 3 PR was merged with all 11 commits intact.
3. Confirm the Extension 3 e2e integration test (commit 9) passes on the latest `preview`.
4. Confirm the branch `prodoc/ext3b-templates-ui` does NOT already exist.
5. Confirm Plane's frontend test infrastructure is working — run any existing frontend test once to verify.

If any of these fail, resolve them before kicking off Claude Code.

---

## BEGIN KICKOFF

Read `docs/CLAUDE.md`, `docs/Prodoc-Plane-Fork-Build-Plan.md` §7 (including §7.5 rewrite and §7.10 build notes from Extension 3), and `docs/templates-investigation.md` before starting. This extension is the first frontend work in the Prodoc fork and sets conventions that future frontend extensions (4b, 5b) will follow.

**Branch:** `prodoc/ext3b-templates-ui` off `preview`

**Operating mode:** PR-level review only. Every architectural decision is pre-locked below. Do not ask clarifying questions during planning or implementation — build the extension end-to-end as specified, open the PR, and the user will review at the PR level. If you hit a genuine blocker not covered by the pre-locks, document it in the PR description as a TODO and continue with the best available workaround; do not halt.

**Scope:** Build the templates UI end-to-end for customer-success staff. This includes the template list view, the template editor, the version comparison view, the dry-run preview modal, the apply-template button on the project page, the materialization job status polling, and the reference data management UI. No new backend code. If a backend gap is discovered during implementation, document it as a TODO in the PR description and work around it — do not fix it by editing backend code in this branch.

---

## Locked architectural decisions (do not relitigate)

1. **Visual style:** Match Plane Commercial's template editor style exactly — form-based, collapsible "Optional" sections, workspace settings location, primary action buttons at the bottom. Use Plane's existing shared UI components (`@/components/ui/*`) wherever possible. Do not introduce new UI libraries or styling systems.
2. **Directory convention:** All Prodoc-specific React components live in `web/components/prodoc/`. Nothing outside this directory is created, except for the two permitted upstream mount points below.
3. **Routing convention:** Investigate Plane's current routing in commit 1 BEFORE creating any routes. Identify whether Plane uses route groups like `(prodoc)` at the workspace level or at the app level, and match Plane's existing pattern exactly. Document the chosen pattern in `web/components/prodoc/README.md`. If neither pattern matches, document the finding and pick the closest match — do NOT invent a third option.
4. **Form library:** Investigate which form library Plane's own template editor uses in commit 1 (most likely react-hook-form based on the Plane codebase's general React ecosystem). Match it exactly — same library, same validation patterns, same error display style. Document the choice in `web/components/prodoc/README.md`. Do not introduce new form libraries.
5. **Feature flagging:** Every Prodoc component must check a `useProdocFeatureFlag()` hook and render null when the flag is off. The hook fetches flag state from the same backend endpoint the mixin uses. No Prodoc UI is ever visible when the feature is disabled.
6. **Permitted upstream mount points:** Exactly two, each limited to a 3-line edit (one import, one component mount, optionally one prop):
   - `web/app/[workspaceSlug]/settings/templates/page.tsx` (or Plane's current equivalent — verify path first) — mount `<ProdocTemplateList />` below Plane's existing templates section.
   - `web/app/[workspaceSlug]/(projects)/projects/[projectId]/page.tsx` (or Plane's current equivalent) — mount `<ApplyTemplateButton />` near the project header.
   - If either file requires MORE than a 3-line edit (e.g., requires importing a new layout component, requires wrapping existing content, requires prop changes on sibling components), document the finding in the PR description as a blocker TODO and implement a workaround where possible.
7. **Upstream edit size ceiling — CI guard:** Add a CI check in commit 1 that fails the build if any file outside `apps/api/plane/prodoc/`, `web/components/prodoc/`, the chosen `(prodoc)` route group location, or the two known upstream mount points has a diff greater than 5 lines compared to `preview`. The check is implemented as a bash script in `web/scripts/check-prodoc-diff.sh` invoked from Plane's existing CI configuration (usually GitHub Actions or a Makefile). This is a hard, automated guard, not a soft promise.

---

## Commit ordering (10 commits, in order, do not bundle)

### Commit 1 — Frontend convention setup and CI guard

Files to create:

- `web/components/prodoc/README.md` — documents the convention rules above for future contributors. Includes the chosen routing pattern, the chosen form library, and the list of permitted upstream mount points.
- `web/components/prodoc/hooks/use-prodoc-feature-flag.ts` — React hook that fetches feature flag state from `/api/v1/prodoc/feature-flag/` on mount, caches via Plane's existing data-fetching pattern (investigate whether it's SWR, React Query, or custom), and returns `{enabled, loading, error}`. Must not throw on error; must return `enabled: false` on any fetch failure to fail closed.
- `web/components/prodoc/hooks/use-prodoc-api.ts` — API client hook that wraps Plane's existing fetch infrastructure and adds Prodoc-specific error formatting. Returns a typed client with all Extension 3 endpoints: templates (list, get, create, update, createVersion, diff), migrationRequirements (CRUD), thirdPartyTools (CRUD), sites (CRUD), waves (CRUD), issueLinks (get, patch), materialize (project, template), materializationJob (get), dryRun (project, template).
- `web/components/prodoc/components/prodoc-feature-gate.tsx` — wrapper component that uses `useProdocFeatureFlag` and renders children only when enabled, returns null otherwise.
- `web/scripts/check-prodoc-diff.sh` — bash script that runs `git diff --stat preview...HEAD` and fails if any file outside the allowlisted directories has more than 5 lines changed. The allowlist:
  - `apps/api/plane/prodoc/**`
  - `web/components/prodoc/**`
  - `web/app/(prodoc)/**` OR `web/app/[workspaceSlug]/(prodoc)/**` (whichever routing pattern was chosen in the investigation)
  - `web/app/[workspaceSlug]/settings/templates/page.tsx` (or equivalent)
  - `web/app/[workspaceSlug]/(projects)/projects/[projectId]/page.tsx` (or equivalent)
  - `docs/**`
- Wire the script into Plane's existing CI configuration so it runs on every PR to `preview`.
- Unit tests for the feature flag hook (mocked fetch responses: enabled, disabled, error → all three render correctly).

**Investigation tasks to complete in this commit:**

- Identify Plane's current routing convention and document it in the README.
- Identify Plane's form library and document it in the README.
- Identify Plane's data-fetching pattern (SWR/React Query/custom) and document it in the README.
- Identify Plane's testing framework for frontend (likely Jest + React Testing Library, possibly Vitest) and confirm it's working with a single smoke test.
- Verify the exact file paths of the two permitted upstream mount points. If either has moved, document the current path in the README.

Commit message: `feat(prodoc-ui): establish frontend convention, shared hooks, and CI guard`

### Commit 2 — Template list view in workspace settings

Files to create:

- `web/components/prodoc/templates/template-list.tsx` — main list component. Header: "Prodoc Onboarding Templates" with subtitle "Pre-configured onboarding playbooks for healthcare providers". "Create template" button on the right. Grid or list of template cards below. Empty state: "No templates yet. Create your first onboarding playbook." with CTA button. Wrapped in `ProdocFeatureGate`.
- `web/components/prodoc/templates/template-card.tsx` — individual card showing `rendered_preview` fields from the backend (cover image, icon, name, description, task count, wave count, estimated duration in business days), status badge, version label. Click navigates to template detail.
- `web/components/prodoc/templates/template-status-badge.tsx` — reusable pill badge component. Colors: draft = gray, active = blue, locked = green.
- Route page at `web/app/(prodoc)/templates/page.tsx` (or the chosen routing pattern's equivalent) — renders the template list view.
- **One upstream edit** to `web/app/[workspaceSlug]/settings/templates/page.tsx`: add `<ProdocTemplateList />` below Plane's existing templates section. Exactly 3 lines: one import, one component mount, one optional wrapper div.
- Tests: empty state, populated list, feature flag off, card click navigation.

Commit message: `feat(prodoc-ui): template list in workspace settings`

### Commit 3 — Reference data management UI

Files to create:

- `web/components/prodoc/reference/migration-requirements-list.tsx` — CRUD UI for `ProdocMigrationRequirement`. Lives under workspace settings at `Workspace settings → Prodoc Reference Data → Migration Requirements`. Simple table view with add/edit/delete rows, matching Plane's workspace settings visual style.
- `web/components/prodoc/reference/migration-requirement-editor.tsx` — inline or modal form for creating/editing a single row. Fields: name, description, category dropdown, default owner role (text for now, will be a dropdown after Ext 4).
- `web/components/prodoc/reference/third-party-tools-list.tsx` — CRUD UI for `ProdocThirdPartyTool`, same pattern as migration requirements.
- `web/components/prodoc/reference/third-party-tool-editor.tsx` — same pattern.
- Route pages for both under the chosen `(prodoc)` routing group.
- No upstream edits in this commit.
- Tests: CRUD happy paths for both lists, empty states, validation error display.

**Why commit 3 comes before the template editor:** The template editor needs these reference data items to exist so users can link to them from template tasks. Without them, the template editor dropdowns are empty and the UI can't be tested end-to-end.

Commit message: `feat(prodoc-ui): reference data management for migration requirements and third-party tools`

### Commit 4 — Template editor (form-based, collapsible sections)

This is the largest commit in the extension by code volume. Build the nested template editor matching the Plane Commercial visual reference.

Files to create:

- `web/components/prodoc/templates/template-editor.tsx` — top-level editor component. Accepts either a new template or an existing draft template as props. Layout: header with "Back to templates" link and the template name as an editable title, main form area with collapsible sections using Plane's existing collapsible/accordion components, action buttons at the bottom.
- `web/components/prodoc/templates/sections/metadata-section.tsx` — name, description, cover image URL, icon. Required section, always expanded by default. Validation: name required, description required.
- `web/components/prodoc/templates/sections/project-defaults-section.tsx` — default project name pattern, default lead role, public/private toggle. Optional, collapsed by default.
- `web/components/prodoc/templates/sections/waves-section.tsx` — ordered list of waves with name, sequence, description. Add/remove buttons. Required section. Reordering via numeric "sequence" input fields, not drag-and-drop. Client-side validation: at least one wave required, sequences must be unique within the template, wave slugs must be unique.
- `web/components/prodoc/templates/sections/tasks-section.tsx` — table view of tasks with columns for name, wave (dropdown populated from the waves section), duration (business days), offset from start (business days), assignee role label. Inline "expand row" opens a detail panel with description, migration requirement links (multi-select from reference data), third-party tool links (multi-select from reference data). Required section. Client-side validation: at least one task required, task slugs must be unique within template, wave_slug must reference a wave defined in the same template, migration_requirement_slugs and third_party_tool_slugs must reference rows that exist in the workspace.
- `web/components/prodoc/templates/sections/dependencies-section.tsx` — list of blocker → blocked pairs. Each row: blocker task dropdown (populated from tasks section), relation type dropdown (defaulting to `blocked_by`), blocked task dropdown. Add/remove buttons. Optional section. Client-side validation: no self-references, no cycles (walk the dependency graph and reject if cycle detected before submit).
- `web/components/prodoc/templates/sections/sites-section.tsx` — simple form: "Require sites to be configured before materialization" toggle, and a number input "Expected number of sites per project." Optional section.
- `web/components/prodoc/templates/sections/version-status-section.tsx` — read-only display of version number and status badge. "Create new version" button when status is `locked` — navigates to a new editor instance for the new version.
- `web/components/prodoc/templates/action-buttons.tsx` — "Cancel", "Save draft", "Publish & lock" buttons. Disabled states when form is invalid. Confirmation modal before "Publish & lock" because it's irreversible: "Publishing locks this template. Future edits require creating a new version. Are you sure?"
- Form state management: use whichever form library was identified in commit 1. One top-level form with nested field arrays for waves, tasks, and dependencies. Client-side validation before allowing save. Backend validation errors from the API (which are human-readable sentences from Extension 3) are displayed inline next to the offending field.
- Route page at `web/app/(prodoc)/templates/[id]/edit/page.tsx` for editing existing templates.
- Route page at `web/app/(prodoc)/templates/new/page.tsx` for creating new templates.
- Tests: new template create happy path, edit draft happy path, edit locked template shows read-only view with "Create new version" CTA, cycle detection in dependencies, validation error inline display, save draft flow, publish and lock flow with confirmation modal.

This commit is the single biggest piece of Extension 3b. Expect 2000-3000 lines across the files above.

Commit message: `feat(prodoc-ui): form-based template editor with collapsible sections`

### Commit 5 — Version comparison view

Files to create:

- `web/components/prodoc/templates/version-diff.tsx` — side-by-side view of two template versions. Left column: version N, right column: version N+1. Differences highlighted: added tasks in green, removed tasks in red, changed fields in yellow with old and new values shown inline. Uses the backend's `/diff/<v1>/<v2>/` endpoint from Extension 3 commit 6.
- `web/components/prodoc/templates/version-history.tsx` — dropdown on the template detail page listing all versions of the template with "Compare to current" buttons for each.
- Route page at `web/app/(prodoc)/templates/[id]/versions/[compareId]/page.tsx` for the side-by-side view.
- Tests: mocked diff responses render correctly, no-difference case shows empty state, cross-slug comparison rejected (backend returns 400, frontend shows clear error).

Commit message: `feat(prodoc-ui): template version comparison view`

### Commit 6 — Dry-run preview modal

Files to create:

- `web/components/prodoc/templates/dry-run-modal.tsx` — modal that opens when a user clicks "Preview" on a template or when the apply-template flow reaches the preview step. Calls the backend's dry-run endpoint and renders the full materialization tree: waves as collapsible sections, tasks within each wave with computed absolute dates, dependencies listed below with blocker → blocked arrows, migration requirements and third-party tools summarized with counts and expandable lists.
- Header shows template name, target project name, estimated duration.
- Footer: "Close" and "Materialize this template" buttons. The "Materialize this template" button is only enabled when there are no errors in the dry-run result.
- Loading state: skeleton UI while the dry-run endpoint fetches.
- Error state: if the dry-run returns errors (unresolvable slugs, missing holiday calendar, etc.), display them as a clear list at the top of the modal with the specific problems and what needs to be fixed.
- Tests: dry-run success renders tree, dry-run error renders error list, materialize button disabled when errors present, materialize button click dispatches to the materialization flow.

Commit message: `feat(prodoc-ui): dry-run preview modal with full materialization tree`

### Commit 7 — Apply template button and materialization flow on project page

Files to create:

- `web/components/prodoc/projects/apply-template-button.tsx` — prominent button or banner on empty/new projects. Clicking opens the template selection modal. Only appears when the project has zero issues AND zero modules (i.e., untouched) OR the project's `ProdocProjectSettings.prodoc_template_source` is null. Hidden otherwise to prevent accidental re-materialization.
- `web/components/prodoc/projects/template-selection-modal.tsx` — searchable list of the workspace's `active` and `locked` templates. Selecting one opens the dry-run preview modal from commit 6 with the target project pre-filled. Confirming materialization dispatches the Celery task via the backend, closes both modals, and mounts the status banner.
- `web/components/prodoc/projects/materialization-status-banner.tsx` — banner on the project page after materialization starts. Polls the backend's job status endpoint every 2 seconds. Shows progress as "12 of 40 tasks created" using `tasks_created_so_far` and `tasks_total`. On success, banner fades out after 3 seconds and refreshes the project's issue list. On failure, banner turns red with error message and a "Try again" button that reopens the template selection modal.
- **One upstream edit** to `web/app/[workspaceSlug]/(projects)/projects/[projectId]/page.tsx`: add `<ApplyTemplateButton />` near the project header. Exactly 3 lines: one import, one component mount, one optional wrapper.
- Tests: materialization success flow, failure flow, banner polls correctly, banner fades on success, banner error state, "Try again" button reopens modal, button hidden when project already materialized.

Commit message: `feat(prodoc-ui): apply template button and materialization status polling`

### Commit 8 — Sites and waves management UI (per-project)

Files to create:

- `web/components/prodoc/projects/sites-manager.tsx` — per-project CRUD UI for `ProdocSite` rows. Lives on the project detail page under a new "Sites" tab or section. Table view with add/edit/delete, same visual style as the reference data UIs from commit 3.
- `web/components/prodoc/projects/site-editor.tsx` — form for creating/editing a site. Fields: name, address, contact name/email/phone, go-live date.
- `web/components/prodoc/projects/waves-manager.tsx` — per-project read-only view of `ProdocWave` rows. Waves are created by materialization, not manually, so this UI is read-only and shows the wave list with their Plane Module FK resolved so users can click through to the Module view.
- Route pages under the chosen `(prodoc)` routing pattern for sites (editable) and waves (read-only).
- No upstream edits in this commit.
- Tests: sites CRUD happy paths, waves read-only view renders, click-through to Plane Module works.

Commit message: `feat(prodoc-ui): per-project sites management and waves view`

### Commit 9 — End-to-end smoke test

No new production code. A single comprehensive e2e test that proves the full Extension 3 + 3b stack works from UI click to materialized project.

File to create:

- `web/tests/e2e/prodoc-templates.spec.ts` (or whichever e2e framework Plane uses — Playwright is most common; verify in commit 1 and use that).
- Test scenario:
  - Navigate to workspace settings → reference data → create one migration requirement and one third-party tool.
  - Navigate to workspace settings → templates → create a new Prodoc template with 2 waves and 5 tasks, 2 dependencies, 1 task linked to the migration requirement and 1 task linked to the third-party tool.
  - Save as draft → verify it appears in the template list with "draft" badge.
  - Open the draft → edit → publish and lock → confirm in the modal → verify status badge changes to "locked".
  - Navigate to a new empty project → click "Apply template" button → select the template → preview the dry-run → verify the preview shows all 5 tasks with absolute dates → click "Materialize this template" → wait for the banner to show success → verify the project now has 5 issues with correct dates and dependencies.
  - Navigate to the project's Sites tab → add one site → verify it saves.
  - Navigate to the project's Waves view → verify 2 waves are listed and each links to a Plane Module.

This is one large test. It is the 3b equivalent of Extension 3's commit 9 e2e test.

Commit message: `test(prodoc-ui): e2e template creation and materialization smoke`

### Commit 10 — Build plan updates

No code. Update `docs/Prodoc-Plane-Fork-Build-Plan.md`:

Append §7.11 "Extension 3b Build Notes" documenting:

- Actual commit count (10)
- Routing convention chosen and why
- Form library used
- Data-fetching pattern used
- The two upstream mount points used (exact paths, exact line counts)
- The CI guard script and how it's wired into Plane's CI
- Any surprises discovered during implementation (document even if Claude Code worked around them)

Append §5.13 "Lessons from Extension 3b" to the lessons-learned section with new imperative-guidance entries:

- The `web/components/prodoc/` convention is the frontend analog of the backend's `apps/api/plane/prodoc/`. All future frontend extensions (4b, 5b) stay inside this directory except for the two permitted upstream mount points.
- The CI guard in `web/scripts/check-prodoc-diff.sh` enforces the upstream edit ceiling automatically. Do not bypass it. If a future extension needs more than 5 lines in an upstream file, update the allowlist explicitly and justify the change in the build plan.
- `ProdocFeatureGate` renders null when the feature flag is off. Use it at the top of every Prodoc component, not just page-level components, so individual pieces of the UI disappear cleanly when the flag is off.
- Frontend validation errors for template shapes (cycles in dependencies, missing wave references, unknown slugs) should be caught client-side before hitting the API. The API does its own validation as a backstop, but catching client-side produces better ergonomics and zero round-trip cost.

Commit message: `docs: append §7.11 build notes and §5.13 lessons from Extension 3b`

---

## Hard rules throughout

- Stay inside `web/components/prodoc/` and the chosen `(prodoc)` routing location for all new code.
- The two permitted upstream mount points (project page, workspace settings templates page) are limited to 3 lines each. The CI guard enforces a 5-line ceiling per upstream file as a hard limit.
- Every Prodoc component must be wrapped in `ProdocFeatureGate` or must check `useProdocFeatureFlag` directly.
- All backend interaction must go through `useProdocApi`. Do not call `fetch` or Plane's other API clients directly from Prodoc components.
- Validation errors from the backend (human-readable sentences from Extension 3) must be displayed inline next to the offending field, not in a generic error banner.
- Client-side validation must catch form errors before submit — never rely on the backend as the only validation layer.
- Do not ask clarifying questions during planning or implementation. If you hit a genuine blocker not covered by the pre-locks, document it in the PR description as a TODO and continue with the best available workaround.

## Out of scope

- Extension 4 (Custom Role Labels) UI — that's Extension 4b.
- Extension 5 (Internal Comment Sidecar) UI — that's Extension 5b.
- Template marketplace or cross-workspace sharing.
- Real-time collaborative editing of templates.
- Template analytics or usage stats.
- Mobile-responsive design beyond what Plane's base components already provide.
- Accessibility audits beyond what Plane's base components already provide.
- Drag-and-drop reordering (form-based with numeric sequences was the locked choice).
- Visual dependency graph (list view is the locked choice).
- Editing reference data from within the template editor (must be done in the separate reference data UI first).

## PR requirements

When the extension is complete, open the PR with this description template:

```
## What this ships
Extension 3b: Templates UI. 10 commits on prodoc/ext3b-templates-ui.

## Commits
1. feat(prodoc-ui): establish frontend convention, shared hooks, and CI guard
2. feat(prodoc-ui): template list in workspace settings
3. feat(prodoc-ui): reference data management for migration requirements and third-party tools
4. feat(prodoc-ui): form-based template editor with collapsible sections
5. feat(prodoc-ui): template version comparison view
6. feat(prodoc-ui): dry-run preview modal with full materialization tree
7. feat(prodoc-ui): apply template button and materialization status polling
8. feat(prodoc-ui): per-project sites management and waves view
9. test(prodoc-ui): e2e template creation and materialization smoke
10. docs: append §7.11 build notes and §5.13 lessons from Extension 3b

## Conventions established
- Routing convention chosen: [document here]
- Form library: [document here]
- Data-fetching pattern: [document here]
- Upstream mount points used: [exact paths and line counts]
- CI guard script: web/scripts/check-prodoc-diff.sh

## Known limitations
- [document any backend gaps discovered and worked around]
- [document any Plane frontend quirks encountered]

## Test baseline
[frontend test count before/after, existing test baseline verification]

## §11.6 review checklist (frontend edition)
- [ ] Zero files edited outside web/components/prodoc/, chosen (prodoc) routing dir, and the two permitted mount points
- [ ] CI guard script is active and passing
- [ ] Every Prodoc component is wrapped in ProdocFeatureGate
- [ ] All API calls go through useProdocApi
- [ ] All validation errors displayed inline
- [ ] Client-side validation covers cycles, duplicates, missing references
- [ ] E2E smoke test (commit 9) passes against a running Plane instance
- [ ] No new UI libraries or styling systems introduced
- [ ] Visual style matches Plane Commercial's template editor reference
```

## END KICKOFF
