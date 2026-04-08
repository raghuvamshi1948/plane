# Templates Investigation — Extension 3 Prerequisite

_Investigation only. No code, no migrations, no model changes._
_Date: 2026-04-08. Plane fork version: 1.3.0 (`apps/api/package.json:3`, `package.json:3`)._

---

## 1. Executive summary

**This open-source Plane fork has no project template system.** Zero template models exist in `apps/api/plane/db/models/`, zero migrations have ever created a template table (121 historical migrations checked), and there are no template endpoints in either `plane.app.urls` or `plane.api.urls`. The frontend ships two empty stub components — `WorkItemTemplateSelect` and `ProjectTemplateSelect` — that return `<></>` from the `apps/web/ce/` directory. The TypeScript path alias `@/plane-web/*` resolves to `./ce/*` (`apps/web/tsconfig.json:9`), confirming this fork has no Enterprise Edition (EE) bundle where the real template implementation presumably lives.

**Recommendation: parallel path.** Extension 3 should build the entire `ProjectTemplate` / `TemplateSection` / `TemplateTask` / `TemplateTaskDependency` / `Site` / `Wave` model graph inside `apps/api/plane/prodoc/` exactly as designed in build plan §7.4. There is nothing to extend — duplication cost is zero because there is nothing to duplicate.

**One required scope change before Ext 3 starts:** the build plan §7.5 assumes Plane has typed custom properties on `IssueType`. **It doesn't.** `IssueType` exists (`apps/api/plane/db/models/issue_type.py:14`) but carries no associated custom-property model — only `is_epic` / `is_default` / `level` boolean/numeric fields. The four typed properties §7.5 wants (`prodoc_template_task_id`, `prodoc_site_id`, `prodoc_wave_id`, `prodoc_sla_hours`) need a different home. See §6 open questions.

---

## 2. What exists in upstream Plane

### 2.1 Backend: nothing

| Search                                  | Method                                                            | Result            |
| --------------------------------------- | ----------------------------------------------------------------- | ----------------- |
| Models named `*template*`               | `Glob apps/api/plane/db/models/*template*`                        | Zero files        |
| `class .*Template` in any backend `.py` | `Grep` over `apps/api/plane/`                                     | Zero matches      |
| Migrations creating template tables     | `Grep template apps/api/plane/db/migrations/` (121 files)         | Zero matches      |
| Template endpoints                      | Searched `apps/api/plane/app/views/`, `apps/api/plane/api/views/` | No views, no URLs |
| Project clone / duplicate endpoint      | `grep "def duplicate\|def clone" apps/api/plane/app/views/`       | Zero matches      |
| `plane-compose` / YAML project-as-code  | `find . -name "plane-compose*"`                                   | Zero hits         |

The only `template`-shaped strings in `apps/api/plane/` are: Django email templates (`apps/api/plane/utils/email.py`), an SQL string fragment (`apps/api/plane/app/views/workspace/base.py:259`), and Django's stdlib `from django.template.defaultfilters import slugify` (`apps/api/plane/db/models/state.py:7`). None are project templates.

**Conclusion:** the Plane CE backend in this fork has never had a project template system. There is nothing to subclass, FK to, or extend.

### 2.2 Frontend: two empty stubs

Two files exist that name the concept but implement nothing:

- `apps/web/ce/components/issues/issue-modal/template-select.tsx:22` — `WorkItemTemplateSelect(props) { return <></>; }`
- `apps/web/ce/components/projects/create/template-select.tsx:13` — `ProjectTemplateSelect(props) { return <></>; }`

Both are referenced from `apps/web/core/components/issues/issue-modal/form.tsx:49` via `import { ... WorkItemTemplateSelect } from "@/plane-web/components/issues/issue-modal";`. The path alias `@/plane-web/*` is defined in `apps/web/tsconfig.json:9` as `["./ce/*"]`, so in this fork the imports resolve to the empty stubs. The CE provider also exposes a no-op `setWorkItemTemplateId: () => {}` (`apps/web/ce/components/issues/issue-modal/provider.tsx:37`).

The standard Plane CE convention is for these `ce/` stubs to be replaced by real implementations in an `ee/` folder behind a build-time alias swap. **There is no `ee/` folder for templates anywhere in this repo** (`find apps/web -type d -name "ee"` returns nothing for the components tree; the only `ee` directory is the editor at `packages/editor/src/ee`, which is unrelated). So even if upstream Plane EE has a template feature, this open-source fork does not include it.

`packages/types/src/estimate.ts:59` defines `TTemplateValues`, but that is a preset for Estimate Point values (Fibonacci, Linear, etc.), tagged with `is_ee: boolean` (`estimate.ts:71`). It is not a project template type.

### 2.3 Models we will target during materialization (these exist and are usable)

These are the upstream models the Ext 3 materializer will write into. None of them need modification — the materializer reads from the Prodoc-side template models and creates these:

| Model           | File:line                                   | Notes                                                                                                      |
| --------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `Issue`         | `apps/api/plane/db/models/issue.py:104`     | `target_date` field at line 146; `type` FK to `IssueType` at line 162 (nullable). Materializer sets these. |
| `IssueRelation` | `apps/api/plane/db/models/issue.py:287`     | Already wired into Ext 1 dispatcher and Ext 2 cascade.                                                     |
| `IssueLabel`    | `apps/api/plane/db/models/issue.py:533`     | Available if templates ever attach labels.                                                                 |
| `IssueAssignee` | `apps/api/plane/db/models/issue.py:336`     | Materializer assigns users via this.                                                                       |
| `Module`        | `apps/api/plane/db/models/module.py:67`     | One Plane Module per Wave (build plan §7.7 step 5).                                                        |
| `ModuleIssue`   | `apps/api/plane/db/models/module.py:152`    | Join row attaching materialized work items to Wave→Module.                                                 |
| `Page`          | `apps/api/plane/db/models/page.py:23`       | `MigrationRequirement.page_id` and `ThirdPartyTool.page_id` target this.                                   |
| `Cycle`         | `apps/api/plane/db/models/cycle.py:60`      | Not used in §7 v1, but available.                                                                          |
| `IssueType`     | `apps/api/plane/db/models/issue_type.py:14` | Workspace-scoped (line 15). Used for the "Prodoc Implementation Task" type.                                |

---

## 3. Gap analysis against Prodoc requirements (build plan §7)

| Requirement (build plan §7)                                                                                          | Coverage                                                  | Notes                                                                                                                                                                                                                                                                                                                                 |
| -------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Wave structure (groups of tasks shipping together)                                                                   | **Not covered**                                           | No upstream model. Ext 3's `Wave` + `WaveSite` + `Wave.plane_module` mirror is the only path.                                                                                                                                                                                                                                         |
| Task dependencies with relative business-day offsets                                                                 | **Not covered**                                           | Ext 3's `TemplateTask.offset_days` + `TemplateTaskDependency` is the only path. Upstream `IssueRelation` exists but only operates on real issues, not template blueprints.                                                                                                                                                            |
| Sites (per-project)                                                                                                  | **Not covered**                                           | No upstream model. Ext 3's `Site` is the only path.                                                                                                                                                                                                                                                                                   |
| Custom properties on issues (template_task_id, site_id, wave_id, sla_hours)                                          | **Not covered** — _and worse than the build plan assumes_ | `IssueType` exists but has no associated typed-property model. `WorkspaceUserProperties` / `ModuleUserProperties` / `CycleUserProperties` are JSON filter-preference rows, not typed fields on Issue. The §7.5 management command cannot create typed custom properties because there are no models to create them in. **See §6 Q1.** |
| Materialize into real `Issue` + `IssueRelation` + `Module` + `Page` rows with absolute dates via `add_business_days` | **Covered (target side)**                                 | All four upstream models exist (§2.3). The Ext 2 `add_business_days` utility is in place. The materializer just needs to call ORM `.create()` on each.                                                                                                                                                                                |
| Workspace-scoped, versioned templates                                                                                | **Not covered**                                           | No upstream model. Standalone Prodoc model.                                                                                                                                                                                                                                                                                           |
| Ordered template sections                                                                                            | **Not covered**                                           | No upstream model. Standalone Prodoc model.                                                                                                                                                                                                                                                                                           |
| Migration requirements / third-party tool metadata linking to a Page                                                 | **Covered (target side)**                                 | `Page` model exists at `apps/api/plane/db/models/page.py:23`; FK from new Prodoc model is straightforward.                                                                                                                                                                                                                            |
| Issue Type assignment on materialized work items                                                                     | **Covered**                                               | `Issue.type` FK exists (`issue.py:162-168`). Setting it during `Issue.objects.create()` works.                                                                                                                                                                                                                                        |
| Workspace-level Issue Type creation via management command                                                           | **Partially covered**                                     | `IssueType` model is workspace-scoped and creatable. The four "typed custom properties" the command is supposed to add do not exist as a concept — see Q1.                                                                                                                                                                            |

**Score: 0 of 8 core template features covered, 3 of 3 target-side dependencies covered, 1 of 2 Issue Type pieces covered.**

---

## 4. Recommended path: parallel

### 4.1 Why parallel and not reuse or hybrid

There is literally nothing to reuse. This is not a "the upstream model is close but missing fields" scenario — there is no upstream model at all. The hybrid path is also moot because the only upstream concept that overlaps with the Prodoc design is `IssueRelation` (used at materialization time, not template-authoring time) and `Module` (mirror target for Waves), and both are already wired by Extensions 1 and 2 with no edits required.

The build plan §7.4 data model can be implemented exactly as written — every Prodoc model is a new table in `apps/api/plane/prodoc/models/`, every FK to upstream is read-only (`Project`, `Module`, `Page`, `IssueType`), and zero upstream files need editing. This matches the CLAUDE.md §2 cardinal rule for free.

### 4.2 What changes from the original plan

Only one change: the typed-custom-properties story in §7.5 needs replanning before Ext 3 starts. Three options laid out in §6 Q1; user picks one. The model graph in §7.4 itself is unchanged.

### 4.3 What stays from the original plan

Everything else: the model graph (§7.4), the materialization algorithm (§7.7), the role resolution (§7.8), the API contract (§7.6), the 23 tests (§7.9), and the definition of done (§7.10). These were all written assuming a parallel implementation, and the investigation confirms that assumption.

---

## 5. Estimated commit count and highest risks

### 5.1 Commit count: ~10 commits across 4–6 sessions

A reasonable decomposition (build plan §7 already groups the work this way):

1. `ProjectTemplate` + `TemplateSection` + `TemplateTask` + `TemplateTaskDependency` models, migration, CRUD endpoints, tests.
2. `MigrationRequirement` + `ThirdPartyTool` models, migration, CRUD endpoints with optional inline-Page creation, tests.
3. `Site` + `Wave` + `WaveSite` models, migration, CRUD endpoints, Wave-creates-Module hook, tests.
4. `ProjectMaterializationJob` model, migration, status polling endpoint.
5. `setup_prodoc_issue_type` management command (creates `IssueType` row only — typed-properties story per Q1 resolution).
6. **Resolution of Q1 (typed custom properties).** Could be one of: a sidecar `ProdocIssueLink(issue, template_task_id, site_id, wave_id, sla_hours)` model + migration; or a deferred decision documented in code with TODOs and a hard reference back to this report.
7. Materialization core: expansion plan, date computation, work item creation, Module attachment.
8. Materialization dependency rewiring with `dependency_mode='all'` and `'same_site'`.
9. Materialization rollback on partial failure + dry-run mode.
10. Workspace-isolation tests, permission tests, feature-flag tests across the new endpoints; integration test against a 20-task template.

### 5.2 Highest risks

1. **Typed custom properties (the §7.5 gap).** The single biggest unknown. Without a resolution to Q1, the materialized work items have no first-class place to store the four prodoc IDs, and the build plan's promise of "ops sees these as first-class fields in the Plane UI and can filter Views by them" is unachievable in this fork. The Plane UI only knows how to render fields it has model support for. **This is the only risk that could meaningfully reshape Ext 3 — resolve before starting.**
2. **Materialization rollback correctness.** Build plan §7.7 step 11 says rollback soft-deletes work items, modules, and relations. Plane's `SoftDeleteModel.delete()` is `save()` in disguise (CLAUDE.md, lessons §5.10), so the rollback path needs to walk every recorded ID and set `deleted_at` explicitly. The `ProjectMaterializationJob.work_items_created` JSONField pattern is sound; the risk is missing a model in the rollback walker. Test #17 must hit every model class.
3. **Issue Type wiring.** §7.8 wants the management command to create `IssueType` once per workspace. `IssueType` is workspace-scoped but the Plane UI may have project-level activation requirements (`ProjectIssueType` join exists at `apps/api/plane/db/models/issue_type.py:35`) — the materializer probably also needs to ensure a `ProjectIssueType` join row exists for the target project before setting `Issue.type`. Worth confirming via a small spike during Ext 3 commit 1.
4. **Performance on large templates.** Build plan §7.9 test #23 says 50 tasks × 4 sites × 2 waves in under 60 seconds. Materializer creates issues one at a time today (build plan §7.7 step 8). For 400 work items + ~800 dependency rows, that is doable but tight; if it slips, the optimization is `bulk_create` followed by manual signal re-fire — and the cascade signal handler has a precedent for explicit walkers (see `apps/api/plane/prodoc/signals/cascade.py` line 155 on the bulk-update breadcrumb). Not blocking, just a thing to watch.
5. **Page auto-creation as a side effect of POST.** §7.6 says the migration-requirements endpoint can accept either `page_id` or a `body` field, with `body` causing the API to create a Plane Page automatically. Page creation in upstream is non-trivial (`Page` has its own permission model and lives in `apps/api/plane/db/models/page.py:23`). Worth a separate commit and a separate test.

---

## 6. Open questions for the user

These need answers before Ext 3 planning can finalize. None block this report.

**Q1 (highest priority — see §3 row 4 and §5.2 risk 1). Typed custom properties on Issue.**
The build plan §7.5 assumes Plane has a typed-custom-properties feature on `IssueType`. It does not in this CE fork. Pick one of:

- **(a) Sidecar table.** New Prodoc model `ProdocIssueLink(issue=OneToOneField(Issue), template_task_id, site_id, wave_id, sla_hours)`. Lookup and filter via Prodoc-side endpoints. The Plane UI will not show these fields natively; ops uses the Prodoc API or a future admin view.
- **(b) Build typed custom properties as a Prodoc feature.** A new Prodoc app feature (`ProdocCustomProperty` + `ProdocCustomPropertyValue`) that mirrors what Plane EE presumably has. Larger scope, but the most generally useful.
- **(c) Stash IDs in `Issue.external_source` / `Issue.external_id`** (`issue.py:160-161`). These two CharFields exist on every Issue, are indexed, and are a textbook misuse of "external system reference" fields. Cheap, ugly, and works today.
- **(d) Upgrade the CE fork to include EE templates.** Out of scope per CLAUDE.md §2 (no upstream edits) and not a real option, listed only for completeness.

**Recommended default: (a) sidecar table.** It is the smallest scope, matches the existing Prodoc patterns from Ext 1/2, and leaves option (b) open for later if a real custom-properties story becomes a roadmap item.

**Q2. Materialization execution model: foreground or Celery?**
Build plan §7.6 says `POST /materialize/` returns 202 with a `job_id` and the work happens async. §7.7 describes a Celery task. Confirm: is it OK to depend on Celery being healthy at materialization time, or does ops want a synchronous endpoint that takes 30 seconds and returns the job result inline? For a 40-task template, sync would work and avoids polling complexity. For a 400-work-item template, async is mandatory. Pick a threshold.

**Q3. Template versioning and editability after use.**
Build plan §7.2 out-of-scope says "editing a template after it has been used to materialize a project — once materialized, the project's work items are disconnected from the template." Confirm: should the `ProjectTemplate.is_active` flag be flipped to read-only after the first successful materialization? Or just enforce the disconnect at the API layer? This affects the immutability story in §7.4.

**Q4. Workspace scope vs instance scope for templates.**
Build plan §7.4 says `ProjectTemplate.workspace = FK(Workspace)`. Confirm. The alternative — instance-global templates that all workspaces can read — is simpler for a single-tenant Prodoc deployment but breaks if Prodoc ever multi-tenants. Workspace-scoped is the safer default and matches CLAUDE.md §3.

**Q5. Dry-run output schema.**
Build plan §7.6 says `dry_run=true` returns "the plan." Specify: what fields per planned work item? At minimum: `title`, `start_date`, `target_date`, `wave_name`, `site_name`, `assignee_count`, `dependency_count`. Locking this before Ext 3 starts saves a re-spec round-trip during commit 9.

**Q6. Should the management command in §7.5 be one-time-per-workspace or idempotent on every run?**
§7.5 says "idempotent: if the type already exists, updates properties; doesn't error." But "updates properties" presupposes the typed-properties feature in Q1. If Q1 picks (a) or (c), the command only ensures the `IssueType` row exists and is otherwise a no-op. Confirm.

---

## 7. Stop-and-report flag

Per the prompt: "Stop and report if you find that Plane's template system has been substantially refactored since the build plan was written, the same way Extension 1's investigation surfaced the public relations API."

**Status: yes, but in the opposite direction.** The build plan §10 prompt was written with the expectation that "if templates exist" the investigator should document them. The investigator should be aware that (a) zero template models exist in the open-source fork, and (b) the §7.5 typed-custom-properties assumption is broken — see Q1. Both findings are documented above. Neither requires a redesign of the §7.4 model graph; both require a small scope decision before commit 1.

No other refactor surprises were found.
