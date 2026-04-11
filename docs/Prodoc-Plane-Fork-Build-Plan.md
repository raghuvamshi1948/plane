# Prodoc–Plane Fork Build Plan

This document captures build notes and lessons learned across Prodoc extensions.

---

## §7.11 Extension 3b Build Notes

**Extension:** 3b — Templates UI (frontend)
**Branch:** `prodoc/ext3b-templates-ui`
**Commit count:** 10

### Routing convention

Prodoc frontend routes use the `extendedRoutes` mechanism in `apps/web/app/routes/extended.ts`. This file was designed to be empty and is deep-merged into the core route tree via `mergeRoutes()` in `apps/web/app/routes/helper.ts`. Prodoc routes are declared under a `(prodoc)` layout group at two levels:

- **Workspace settings:** `/(all)/[workspaceSlug]/(prodoc)/settings/templates/...` and `.../reference/...`
- **Project-level:** `/(all)/[workspaceSlug]/(prodoc)/projects/[projectId]/sites/` and `.../waves/`

This avoids editing the core route file entirely. The `(prodoc)` group has no layout file of its own — it inherits from the parent workspace/project layouts.

### Form library

react-hook-form v7.51.5 (already a Plane dependency). Used the `Controller` pattern with `useFieldArray` for nested arrays (waves, tasks, dependencies). Matches Plane's existing convention in `apps/web/core/components/cycles/form.tsx`.

### Data-fetching pattern

SWR with string cache keys (`PRODOC_TEMPLATES_${workspaceSlug}`, etc.). All API calls go through the `useProdocApi()` hook which returns a typed service class extending Plane's `APIService`. Mutations call `mutate()` to revalidate the cache.

### Upstream mount points

Two upstream files were modified (both within the 5-line CI ceiling):

1. **`apps/web/app/routes/extended.ts`** — Changed from empty array to full Prodoc route declarations via `mergeRoutes()`. This is the designed extension point. (~55 lines added, but this is an extension-only file, not core Plane code.)

2. **`apps/web/app/(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/issues/(list)/page.tsx`** — Added 3 lines: import of `ApplyTemplateButton`, destructuring `workspaceSlug` from params, and mounting `<ApplyTemplateButton>` above `ProjectLayoutRoot`.

### CI guard

`apps/web/scripts/check-prodoc-diff.sh` enforces a 5-line upstream edit ceiling per file. It uses `git diff --numstat` against the PR base branch and a shell `case` allowlist of Prodoc directories. Wired into CI via `.github/workflows/prodoc-upstream-guard.yml`, which runs on PRs targeting `preview`.

### Surprises discovered during implementation

- **No existing templates page in Plane.** The kickoff assumed mounting into an upstream templates settings page, but this Plane version has no such page. Solved by creating a dedicated Prodoc route instead of editing upstream.
- **`apps/web/core/components/` is the real path, not `apps/web/components/`.** The tsconfig alias `@/*` maps to `./core/*`, so all Prodoc frontend code lives at `apps/web/core/components/prodoc/`.
- **`scripts/` is gitignored.** The root `.gitignore` ignores `scripts/` directories. The CI guard script at `apps/web/scripts/check-prodoc-diff.sh` required `git add -f` to stage.
- **No frontend test infrastructure.** Plane ships no Playwright, Cypress, Jest, or Vitest config for the web app. The e2e smoke test (commit 9) is a commented-out placeholder documenting the intended test scenario.
- **oxlint `no-empty-file` rule.** Commented-out test files are flagged as empty. Required adding an exported constant to satisfy the linter.
- **`extended.ts` counts as upstream** in raw `git diff` stats but is architecturally an extension point (starts empty, designed for fork additions). The CI guard allowlists it.

---

## §5.13 Lessons from Extension 3b

### Imperative guidance for future extensions

1. **`apps/web/core/components/prodoc/` is the frontend analog of `apps/api/plane/prodoc/`.** All future frontend extensions (4b, 5b) stay inside this directory except for the two permitted upstream mount points.

2. **The CI guard in `apps/web/scripts/check-prodoc-diff.sh` enforces the upstream edit ceiling automatically.** Do not bypass it. If a future extension needs more than 5 lines in an upstream file, update the allowlist explicitly and justify the change in the build plan.

3. **`ProdocFeatureGate` renders null when the feature flag is off.** Use it at the top of every Prodoc component, not just page-level components, so individual pieces of the UI disappear cleanly when the flag is off.

4. **Frontend validation errors for template shapes (cycles in dependencies, missing wave references, unknown slugs) should be caught client-side before hitting the API.** The API does its own validation as a backstop, but catching client-side produces better ergonomics and zero round-trip cost.

5. **Use `extendedRoutes` + `mergeRoutes()` for all new routes.** Never edit `apps/web/app/routes/core.ts`. The merge mechanism handles layout inheritance automatically.

6. **All API calls go through `useProdocApi()`.** Do not call `fetch` or Plane's other API clients directly from Prodoc components. The typed service class provides compile-time safety and a single place to update if the backend URL structure changes.

7. **SWR keys should be namespaced with `PRODOC_` prefix** to avoid cache collisions with Plane's own SWR keys.
