# Extension 3 Backend — Consolidated Kickoff Prompt

**How to use this file:** Paste the entire body below (from "BEGIN KICKOFF" to "END KICKOFF") into a fresh Claude Code session on a new `prodoc/ext3-templates` branch off `preview`. Do NOT edit or summarize it first — every sentence is load-bearing because this extension runs in PR-level review mode, meaning Claude Code has no opportunity to ask clarifying questions mid-build.

**Pre-flight checklist before pasting:**

1. Confirm `docs/CLAUDE.md` exists in the repo and reflects the current additive-only rules.
2. Confirm `docs/Prodoc-Plane-Fork-Build-Plan.md` is in the repo and §7.5 has been rewritten per the templates investigation (the post-investigation version that describes the sidecar `ProdocIssueLink` approach, not the original version that assumed typed custom properties existed).
3. Confirm `docs/templates-investigation.md` is in the repo and has a "Locked decisions" section recording Q1-Q6 answers verbatim.
4. Confirm the branch `prodoc/ext3-templates` does NOT already exist.
5. Confirm `preview` is clean and contains the Extension 2 merge (`prodoc-ext2` tag should be reachable from `preview`).

If any of these fail, resolve them before kicking off Claude Code.

---

## BEGIN KICKOFF

Read `docs/CLAUDE.md`, `docs/Prodoc-Plane-Fork-Build-Plan.md` §7 (entire section including the rewritten §7.5), and `docs/templates-investigation.md` (entire document, especially the "Locked decisions" section) before starting. Stay strictly inside `apps/api/plane/prodoc/`. The two permitted upstream edit locations from §2 of CLAUDE.md still apply and nothing else.

**Branch:** `prodoc/ext3-templates` off `preview`

**Operating mode:** This extension runs in PR-level review mode. Every architectural decision is pre-locked below. Do not ask clarifying questions during planning or implementation — build the extension end-to-end as specified, open the PR, and the user will review at the PR level. If you hit a genuine blocker that is not covered by the pre-locks below, document it in the PR description as a TODO and continue with the best available workaround; do not halt.

**Naming convention:** Prodoc prefix stays on all models, all table names, and all URL route names. Views, serializers, permissions, and mixins may drop the Prodoc prefix only if they are internal to `apps/api/plane/prodoc/` and the import path disambiguates them. When in doubt, keep the prefix — do not invent new naming conventions.

---

## Locked architectural decisions (do not relitigate)

1. Parallel `ProdocTemplate` system, no reuse of any upstream template surface. Plane CE has none.
2. Workspace-scoped templates. Identity is `(workspace_id, slug, version)`.
3. Immutable after first use, with versioning. Editing a used template creates a new version row.
4. Materialization is a Celery task returning a `job_id` for status polling. Synchronous path exists only for the management command.
5. Custom properties via sidecar `ProdocIssueLink` with typed M2M to `ProdocMigrationRequirement` and `ProdocThirdPartyTool`. No JSONField for custom properties data, no Plane Pages reuse for structured data.
6. Dry-run returns the full materialization tree (issues, dependencies, modules, pages, with computed absolute dates) without DB writes.
7. Seed management command is idempotent by `(slug, version)`.
8. Sites are per-project, not persistent-per-customer.
9. Waves mirror to Plane Modules.
10. `ProdocTemplateTask.migration_requirement_slugs` and `third_party_tool_slugs` are JSONField lists of string slugs, NOT foreign keys. Templates are portable definitions; slug resolution happens at materialization time and fails fast with a clear error if a slug is missing in the target workspace. This keeps templates cloneable across workspaces as a future capability without a schema migration.
11. Cascade suppression during materialization uses a `suppress_cascade()` context manager exposed from Extension 2's `apps/api/plane/prodoc/signals/cascade.py` module. The materializer wraps its entire run in `with suppress_cascade():`. Do NOT poke at Extension 2's internal thread-local directly.
12. Celery materialization task retry policy: `max_retries=3`, exponential backoff `(5s, 25s, 125s)`, `acks_late=True`. Idempotency marker: `ProdocProjectSettings.prodoc_template_source = OneToOneField(ProdocTemplate, null=True, on_delete=SET_NULL)` — set at the start of materialization in an atomic transaction. Retries check this marker first and fail with a clear error ("Project already has template materialization in progress or completed") rather than double-materializing.

---

## Commit ordering (11 commits, in order, do not bundle)

### Commit 0 — Extension 2 `suppress_cascade` context manager refactor

This commit modifies only `apps/api/plane/prodoc/signals/cascade.py` and is a precondition for the materializer in commit 5. Do this FIRST before any Extension 3 models exist.

Add to `apps/api/plane/prodoc/signals/cascade.py`:

```python
from contextlib import contextmanager

@contextmanager
def suppress_cascade():
    """Temporarily suppress the dependency cascade signal handler.

    Use during bulk operations that create or modify Issue rows in ways
    that should not trigger cascade walks (e.g., template materialization).
    Thread-local, so concurrent requests are unaffected.

    Example:
        with suppress_cascade():
            materializer.materialize(...)
    """
    was_active = getattr(_cascade_local, "active", False)
    _cascade_local.active = True
    try:
        yield
    finally:
        _cascade_local.active = was_active
```

The existing `on_issue_target_date_change` handler's re-entry guard already checks `_cascade_local.active`, so no changes to the handler are needed. The context manager simply sets the flag around whatever code block needs suppression.

Tests in `tests/contract/test_cascade.py` — add two new cases:

- `suppress_cascade()` prevents the cascade from firing on an Issue save inside the context
- `suppress_cascade()` is reentrant-safe (nested `with` blocks leave the flag cleared to its prior state)

Commit message: `refactor(prodoc): expose suppress_cascade context manager from Extension 2 signals`

### Commit 1 — Custom property reference tables

Files to create:

- `apps/api/plane/prodoc/models/migration_requirement.py` — `ProdocMigrationRequirement(BaseModel)`. Fields: `workspace` FK (required), `name`, `description`, `category` enum (`data`, `integration`, `compliance`, `training`), `default_owner_role` nullable CharField (will be wired to Extension 4's role labels later — add a `# TODO(ext4): wire to ProdocRoleLabel FK` comment). Unique constraint on `(workspace, name)`.
- `apps/api/plane/prodoc/models/third_party_tool.py` — `ProdocThirdPartyTool(BaseModel)`. Fields: `workspace` FK, `name`, `vendor`, `category` enum (`ehr`, `billing`, `lab`, `scheduling`, `telephony`, `other`), `documentation_url` (URLField, nullable). Unique constraint on `(workspace, name)`.
- `apps/api/plane/prodoc/migrations/0008_reference_tables.py` — both tables.
- `apps/api/plane/prodoc/serializers/migration_requirement.py` and `serializers/third_party_tool.py` — all validation errors must be human-readable sentences, not Django exception strings.
- `apps/api/plane/prodoc/views/migration_requirement.py` and `views/third_party_tool.py` — full CRUD, gated by `ProdocFeatureFlagMixin` and `ProdocWorkspaceEntityPermission` from Extension 2.
- `apps/api/plane/prodoc/urls.py` — add four routes:
  - `GET/POST /workspaces/<slug>/migration-requirements/`
  - `GET/PATCH/DELETE /workspaces/<slug>/migration-requirements/<id>/`
  - `GET/POST /workspaces/<slug>/third-party-tools/`
  - `GET/PATCH/DELETE /workspaces/<slug>/third-party-tools/<id>/`
- `apps/api/plane/prodoc/tests/contract/test_reference_tables.py` — 8 tests: CRUD happy paths for both models (4), workspace isolation (2), feature flag gating (1), permission denied (1).

Commit message: `feat(prodoc): add ProdocMigrationRequirement and ProdocThirdPartyTool reference tables`

### Commit 2 — ProdocIssueLink sidecar

Files to create:

- `apps/api/plane/prodoc/models/issue_link.py` — `ProdocIssueLink(BaseModel)` with `issue = OneToOneField("db.Issue", on_delete=CASCADE, related_name="prodoc_link")`, `migration_requirements = M2M(ProdocMigrationRequirement)`, `third_party_tools = M2M(ProdocThirdPartyTool)`.
- `apps/api/plane/prodoc/migrations/0009_issue_link.py` — sidecar table plus the two M2M through tables.
- `apps/api/plane/prodoc/serializers/issue_link.py` — accepts M2M updates via slug arrays so the materializer and the API both use the same input shape. Rejects slugs that don't resolve in the issue's workspace with a clear error.
- `apps/api/plane/prodoc/views/issue_link.py` — `GET/PATCH` at `/api/v1/prodoc/workspaces/<slug>/projects/<project_id>/work-items/<issue_id>/links/`. Lazy-create on first PATCH.
- `apps/api/plane/prodoc/urls.py` — add the route.
- `apps/api/plane/prodoc/tests/contract/test_issue_link.py` — 6 tests: lazy-create on first PATCH, M2M happy path for migration_requirements, M2M happy path for third_party_tools, workspace isolation, cross-workspace M2M rejection (linking workspace-A's tool from workspace-B's issue must fail), feature flag gating.

Commit message: `feat(prodoc): add ProdocIssueLink sidecar with typed M2M`

### Commit 3 — ProdocSite and ProdocWave models

Files to create:

- `apps/api/plane/prodoc/models/site.py` — `ProdocSite(BaseModel)`. Fields: `project` FK with `related_name="prodoc_sites"`, `name`, `address` (TextField), `contact_name`, `contact_email`, `contact_phone`, `go_live_date` (DateField, nullable). Per-project, not workspace-scoped.
- `apps/api/plane/prodoc/models/wave.py` — `ProdocWave(BaseModel)`. Fields: `project` FK, `name`, `sequence` (PositiveIntegerField for ordering), `plane_module = OneToOneField("db.Module", null=True, on_delete=SET_NULL, related_name="prodoc_wave")`. The Module mirror is created at materialization time, not at wave-creation time, so the FK is initially null. Unique constraint on `(project, sequence)`.
- `apps/api/plane/prodoc/migrations/0010_site_and_wave.py`.
- Serializers for both with human-readable error messages.
- Full CRUD viewsets for both, gated and permission-classed with `ProdocProjectEntityPermission` from Extension 1.
- `apps/api/plane/prodoc/urls.py` — four new routes:
  - `GET/POST /workspaces/<slug>/projects/<project_id>/sites/`
  - `GET/PATCH/DELETE /workspaces/<slug>/projects/<project_id>/sites/<id>/`
  - `GET/POST /workspaces/<slug>/projects/<project_id>/waves/`
  - `GET/PATCH/DELETE /workspaces/<slug>/projects/<project_id>/waves/<id>/`
- Tests in `tests/contract/test_site_api.py` and `tests/contract/test_wave_api.py`. ~10 tests across both files: CRUD, project isolation, unique sequence constraint on waves, feature flag gating.

Commit message: `feat(prodoc): add ProdocSite and ProdocWave models with Plane Module mirror FK`

### Commit 4 — ProdocTemplate model family and idempotency marker

Files to create:

- `apps/api/plane/prodoc/models/template.py` — four models:
  - `ProdocTemplate(BaseModel)`: `workspace` FK, `slug` CharField, `version` PositiveIntegerField default 1, `name`, `description` TextField, `cover_image_url` URLField nullable, `icon` CharField nullable, `status` enum CharField (`draft`, `active`, `locked`). Unique constraint `(workspace, slug, version)`. Status starts `draft`, flips to `active` when first saved as non-draft, flips to `locked` on first successful materialization. Editing a `locked` template raises an error from the serializer.
  - `ProdocTemplateWave(BaseModel)`: `template` FK with `related_name="waves"`, `slug`, `name`, `sequence` PositiveIntegerField, `description`. Unique constraint `(template, slug)` and `(template, sequence)`.
  - `ProdocTemplateTask(BaseModel)`: `template` FK with `related_name="tasks"`, `slug` CharField (unique within template), `name`, `description` TextField, `wave_slug` CharField (string reference to a wave defined in the same template — resolved at materialization time), `duration_business_days` PositiveIntegerField, `offset_from_template_start_business_days` PositiveIntegerField (can be 0), `assignee_role_label` CharField nullable (will be resolved against Ext 4's role labels later), `migration_requirement_slugs` JSONField default list, `third_party_tool_slugs` JSONField default list.
  - `ProdocTemplateDependency(BaseModel)`: `template` FK with `related_name="dependencies"`, `blocker_task_slug` CharField, `blocked_task_slug` CharField, `relation_type` CharField choices matching Plane's `IssueRelationChoices` (default `blocked_by`).
- Files to EDIT (prodoc only):
  - `apps/api/plane/prodoc/models/project_settings.py` from Extension 2 — add the idempotency marker field `prodoc_template_source = ForeignKey(ProdocTemplate, null=True, blank=True, on_delete=SET_NULL, related_name="+")`. This cannot be a OneToOne because a workspace may have multiple projects materialized from the same template. It is a plain FK.
- `apps/api/plane/prodoc/migrations/0011_template_models.py` — all four template models plus the new FK on ProdocProjectSettings. Order: template first (so the FK target exists), then waves/tasks/dependencies, then the alter on ProdocProjectSettings.
- `apps/api/plane/prodoc/tests/contract/test_template_models.py` — 6 tests: unique constraints (3), status transition draft → active → locked (1), edit-after-locked rejection (1), idempotency marker field exists and is nullable (1).

Commit message: `feat(prodoc): add ProdocTemplate model family and idempotency marker on ProdocProjectSettings`

### Commit 5 — Materialization engine (pure function, no Celery yet)

Files to create:

- `apps/api/plane/prodoc/templates/__init__.py` — empty.
- `apps/api/plane/prodoc/templates/materializer.py`:
  - `materialize_template(template_id, project_id, options) -> MaterializationResult`. Pure synchronous function. Wrapped in `transaction.atomic()` by the caller, not by itself, so the management command path and the Celery path can both call it. Internally wraps the work in `with suppress_cascade():` to prevent Extension 2's cascade from firing during the bulk create.
  - Walks in order: (1) idempotency check against `ProdocProjectSettings.prodoc_template_source` — if already set, raise `MaterializationAlreadyAppliedError` with a clear message; (2) set the idempotency marker; (3) resolve the project's holiday calendar via Extension 2's `resolve_calendar_for_project`; (4) create `ProdocWave` rows + mirrored Plane `Module` rows for each template wave; (5) create Plane `Issue` rows with computed absolute `target_date` via `add_business_days` from Extension 2 against the resolved holiday calendar; (6) create Plane `IssueRelation` rows from the template's dependencies; (7) resolve migration_requirement_slugs and third_party_tool_slugs against the target workspace and create `ProdocIssueLink` sidecars with the resolved M2M rows.
  - Slug resolution failures raise `MaterializationSlugNotFoundError` with the specific slug, the task it came from, and the workspace it was looked up in. Caller rolls back via the atomic context.
  - Returns a `MaterializationResult` dataclass with: `created_issues`, `created_relations`, `created_modules`, `created_links`, `created_waves`, `created_sites` (empty for commit 5 — sites are populated at per-project configuration time, not at template materialization time), `errors` (empty on success).
- `apps/api/plane/prodoc/templates/dry_run.py`:
  - `dry_run_template(template_id, project_id, options) -> DryRunResult`. Walks the same logic as `materialize_template` but builds an in-memory tree instead of saving anything. Returns the full set of issues/dependencies/modules/links that would be created, with computed dates. No DB writes anywhere in this code path. Slug resolution failures are collected into the `errors` field rather than raising, so the frontend can show all problems at once.
- `apps/api/plane/prodoc/templates/calendar_resolution.py`:
  - Helper wrappers around Extension 2's `resolve_calendar_for_project` and `add_business_days`, plus an ISO-string-to-date parser for template holiday lists.
- `apps/api/plane/prodoc/templates/exceptions.py`:
  - `MaterializationError` base class
  - `MaterializationAlreadyAppliedError` (for the idempotency marker case)
  - `MaterializationSlugNotFoundError` (for unresolved slugs)
  - All exceptions have a `to_dict()` method returning `{code, message, details}` for frontend consumption.

Tests in `tests/contract/test_materializer.py` and `tests/contract/test_dry_run.py` — 14 tests minimum:

- Materialize a 5-task template into a fresh project, assert all issues/relations/modules/links exist with correct dates (1)
- Materialize the same template twice into two DIFFERENT projects — both succeed (1)
- Materialize the same template twice into the SAME project — second attempt raises `MaterializationAlreadyAppliedError` (1)
- Materialize a template with a missing migration requirement slug — fails fast with `MaterializationSlugNotFoundError`, transaction rolls back, no partial state (1)
- Materialize a template with a missing wave_slug on a task — fails fast (1)
- Dry-run returns the same tree structure as materialize but with zero DB writes (assert via row-count snapshot before/after) (1)
- Dry-run with missing-slug failure modes — returns errors in the result, does NOT raise (1)
- Cascade-suppression test: materialize a template with a 3-task dependency chain, assert the cascade did NOT fire during materialization (use a signal-call counter), but a manual date change AFTER materialization DOES fire the cascade (proves suppression is scoped) (1)
- Materialization respects the project's holiday calendar (use a calendar with a holiday in the middle of the template timeline, assert dates jump over it) (1)
- Materialization falls back to workspace default calendar when project has no override (1)
- Materialization with no calendar at all (null resolution) — uses weekend-only arithmetic (1)
- `suppress_cascade()` is reentrant across nested calls (1)
- `MaterializationSlugNotFoundError.to_dict()` returns frontend-friendly shape (1)
- `ProdocProjectSettings.prodoc_template_source` is set correctly after successful materialization (1)

Commit message: `feat(prodoc): add template materialization engine with cascade suppression and idempotency`

### Commit 6 — Template CRUD endpoints and version diff

Files to create:

- Serializers for `ProdocTemplate`, `ProdocTemplateWave`, `ProdocTemplateTask`, `ProdocTemplateDependency`. The top-level template serializer accepts a nested representation so a single POST can create the entire template definition in one call. All validation errors are human-readable sentences.
- The `ProdocTemplate` serializer response includes a computed `rendered_preview` field that returns `{cover_image_url, icon, name, description, task_count, wave_count, estimated_duration_business_days}` when the template status is `active` or `locked`, and returns `null` when status is `draft`. `estimated_duration_business_days` is computed as the max of `offset_from_template_start_business_days + duration_business_days` across all tasks in the template.
- `apps/api/plane/prodoc/views/template.py` — list/create/detail/patch endpoints. PATCH on a `locked` template returns 409 Conflict with a clear message and a suggestion to create a new version.
- New endpoint: `POST /api/v1/prodoc/workspaces/<slug>/templates/<id>/versions/` — creates a new version of an existing template by copying its definition (waves, tasks, dependencies) and incrementing the version field. The new version starts in `draft` status.
- New endpoint: `GET /api/v1/prodoc/workspaces/<slug>/templates/<id>/diff/<other_id>/` — returns a structured diff between two template versions. Response shape: `{added_tasks: [...], removed_tasks: [...], changed_tasks: [{slug, field_changes: {...}}], added_dependencies: [...], removed_dependencies: [...], added_waves: [...], removed_waves: [...]}`. Both template IDs must belong to the same workspace and same base slug, otherwise 400.
- `apps/api/plane/prodoc/urls.py` — add all routes.
- Tests in `tests/contract/test_template_api.py` — 14 tests minimum:
  - Full nested create (template + waves + tasks + dependencies in one POST) (1)
  - List, retrieve, update happy paths (3)
  - Editing a locked template returns 409 (1)
  - Creating a new version succeeds and the new version is independent (1)
  - New version starts in draft status (1)
  - Version diff happy path for same-slug templates (1)
  - Version diff rejects cross-slug comparison (1)
  - Version diff rejects cross-workspace comparison (1)
  - `rendered_preview` is populated for active template (1)
  - `rendered_preview` is null for draft template (1)
  - `estimated_duration_business_days` computed correctly (1)
  - Workspace isolation on templates list (1)

Commit message: `feat(prodoc): REST API for template CRUD, versioning, and diff`

### Commit 7 — Materialization Celery task, progress tracking, and status polling

Files to create:

- `apps/api/plane/prodoc/models/materialization_job.py` — `ProdocMaterializationJob(BaseModel)`. Fields: `workspace` FK, `template` FK to ProdocTemplate, `project` FK to Project, `status` enum CharField (`pending`, `running`, `succeeded`, `failed`), `result_summary` JSONField nullable (for the MaterializationResult dataclass), `error_message` TextField nullable, `tasks_total` PositiveIntegerField default 0, `tasks_created_so_far` PositiveIntegerField default 0, `started_at` DateTimeField nullable, `finished_at` DateTimeField nullable.
- `apps/api/plane/prodoc/migrations/0012_materialization_job.py`.
- Add to `apps/api/plane/prodoc/tasks.py`: `prodoc_materialize_template_task(job_id)` Celery task decorated with `@shared_task(bind=True, max_retries=3, acks_late=True, autoretry_for=(OperationalError, DatabaseError), retry_backoff=5, retry_backoff_max=125, retry_jitter=False)`. Loads the job row, updates status to `running` with `started_at`, sets `tasks_total` from the template, wraps the materialization in `transaction.atomic()` and calls `materialize_template`. On success, updates status to `succeeded` with `result_summary` and `finished_at`. On `MaterializationAlreadyAppliedError` or `MaterializationSlugNotFoundError`, catches the exception, rolls back, and updates status to `failed` with `error_message` from `exception.to_dict()`. On transient errors, Celery retries per the decorator. After max retries, updates status to `failed` with a clear message.
- The `tasks_created_so_far` counter is incremented inside the materializer itself (pass the job_id through to the materializer so it can do `job.tasks_created_so_far = F('tasks_created_so_far') + 1; job.save(update_fields=['tasks_created_so_far'])` after each Issue save). The increment happens inside the same atomic transaction, so the counter is always consistent with committed state — on rollback, the counter returns to its pre-transaction value.
- `apps/api/plane/prodoc/views/materialization.py`:
  - `POST /api/v1/prodoc/workspaces/<slug>/projects/<project_id>/materialize/` — accepts `{template_id, options}`, creates a `ProdocMaterializationJob` row in `pending` status with `tasks_total=0` (the task will set it when it starts), dispatches `prodoc_materialize_template_task.delay(job.id)`, returns `{job_id, status_url}` immediately with HTTP 202 Accepted.
  - `GET /api/v1/prodoc/workspaces/<slug>/materialization-jobs/<job_id>/` — returns the job's current status, progress fields (`tasks_created_so_far`, `tasks_total`), result summary (if succeeded), and error message (if failed). Response shape includes a computed `progress_percentage` field as a convenience.
  - `POST /api/v1/prodoc/workspaces/<slug>/projects/<project_id>/materialize/dry-run/` — synchronous, returns the dry-run tree directly (no job row, no Celery). Response includes any slug resolution errors as a list so the frontend can display all problems at once.
- `apps/api/plane/prodoc/urls.py` — three new routes.
- Tests in `tests/contract/test_materialization_api.py` — 10 tests minimum:
  - Happy path: POST materialize → poll status → success (1)
  - Dry-run endpoint returns full tree without writes (1)
  - Dry-run endpoint returns errors for unresolvable slugs without raising (1)
  - Failed materialization: POST → poll → status=failed with error_message populated (1)
  - Workspace isolation: workspace A's job_id is invisible from workspace B (1)
  - Feature flag gating (1)
  - `tasks_total` is set when task starts running (1)
  - `tasks_created_so_far` increments during materialization (simulate by mocking the materializer to pause mid-run, assert the counter is > 0 and < tasks_total) (1)
  - Retry with `MaterializationAlreadyAppliedError` does not double-materialize (1)
  - Partial failure rollback: `tasks_created_so_far=0` after rollback from a failure (prove the atomic guarantee holds) (1)

Commit message: `feat(prodoc): Celery materialization task with progress tracking and retry safety`

### Commit 8 — Seed management command

Files to create:

- `apps/api/plane/prodoc/management/__init__.py` and `management/commands/__init__.py` — empty.
- `apps/api/plane/prodoc/management/commands/seed_prodoc_template.py`:
  - Accepts `--workspace <slug> --template-file <path>` arguments. Optional `--materialize-into-project <project_slug>` flag.
  - Reads a YAML template definition from the file (use PyYAML — it's already in Plane's requirements).
  - Idempotent by `(workspace, slug, version)`: re-running with the same identity is a no-op that prints "Template already exists at version N, skipping." Different version creates a new template row.
  - Without `--materialize-into-project`, just creates the template definition.
  - With `--materialize-into-project`, calls `materialize_template` synchronously (not via Celery) inside a `transaction.atomic()` wrapper. Prints progress to stdout.
  - Prints a clear summary: template_id, version, task count, and (if materialized) the materialization result.
  - Exits non-zero on YAML parse errors, missing workspace, or materialization failures.
- `apps/api/plane/prodoc/management/commands/example_template.yaml` — a small example template definition (2 waves, 5 tasks, 2 dependencies, references to 1 migration requirement and 1 third party tool) usable as a reference and in tests.
- Tests in `tests/contract/test_seed_command.py` — 7 tests:
  - First run creates the template (1)
  - Second run with same version is a no-op (1)
  - Different version creates a new template row (1)
  - With `--materialize-into-project`, the template materializes into the specified project (1)
  - Invalid YAML errors with a clear message (1)
  - Missing workspace errors clearly (1)
  - Materialization failure exits non-zero (1)

Commit message: `feat(prodoc): seed_prodoc_template management command`

### Commit 9 — End-to-end integration smoke test

No new production code. A single comprehensive integration test that proves Extensions 1 + 2 + 3 work together.

File to create:

- `apps/api/plane/prodoc/tests/contract/test_e2e_integration.py`:
  - Create a workspace, a project, a HolidayCalendar with one holiday in the middle of the template's timeline.
  - Set `ProdocProjectSettings.holiday_calendar` override.
  - Create a workspace-scoped ProdocMigrationRequirement and ProdocThirdPartyTool.
  - Create a 10-task template with a 3-deep dependency chain, 2 waves, and references to the migration requirement and third-party tool slugs. Template status: `active`.
  - Materialize synchronously via the management command path.
  - Assert all 10 issues exist with correct absolute dates that jump over the holiday.
  - Assert all relations exist with the correct `relation_type`.
  - Assert both Plane Modules (mirroring the two waves) exist.
  - Assert `ProdocIssueLink` sidecars exist with the correct M2M resolutions.
  - Assert `ProdocProjectSettings.prodoc_template_source` points at the template.
  - Assert NO cascade fired during materialization (signal counter).
  - Now manually move the root issue's `target_date` forward by 2 business days.
  - Assert the cascade fires and walks the chain, updating downstream dates.
  - Assert the cascade respects the holiday calendar (downstream dates jump over the holiday).
  - Assert the dependency-cascaded webhook fires for each downstream date change (use the Extension 1 webhook mock via `ProdocWebhookSettings.dependency=True`).
  - Assert `tasks_created_so_far == tasks_total == 10` at the end of the materialization.
  - Assert attempting to re-materialize the same template into the same project raises `MaterializationAlreadyAppliedError`.

This is one large test, ~150 lines of test code. It is the single most important test in the extension.

Commit message: `test(prodoc): end-to-end template materialization + cascade integration`

### Commit 10 — Build plan updates

No code. Update `docs/Prodoc-Plane-Fork-Build-Plan.md`:

Append §7.10 "Extension 3 Build Notes" documenting:

- Actual commit count (11 including commit 0)
- How the three pre-locked checkpoints resolved (slug JSONField, suppress_cascade context manager, retry-with-idempotency-marker)
- The `suppress_cascade()` context manager added to Extension 2's signals module in commit 0 as a precondition
- The `ProdocProjectSettings.prodoc_template_source` FK as the idempotency marker and why a plain FK (not OneToOne)
- The `rendered_preview` and progress field additions made for frontend consumption
- Any surprises discovered during implementation

Append §5.12 "Lessons from Extension 3" to the lessons-learned section with three new imperative-guidance entries:

- Cross-extension signal coupling should be exposed via named context managers, not thread-local pokes. Extension 3 added `suppress_cascade()` to Extension 2's signals module as a precondition for its own materializer. Future extensions that need similar suppression should add their own context managers (e.g., `suppress_webhook_fanout()`) rather than bypassing the handler directly.
- Template-shaped APIs with nested children are the right fit for DRF's nested writable serializers. A single POST creates a template, all its waves, all its tasks, and all its dependencies in one atomic call. Do not split into multiple API calls for parent + children.
- Idempotency markers for long-running Celery tasks live on a sidecar model the task can atomically set and atomically check. Setting the marker must be inside the same transaction as the first real work the task does, otherwise the retry window can double-apply.

Commit message: `docs: append §7.10 build notes and §5.12 lessons from Extension 3`

---

## Hard rules throughout

- Stay inside `apps/api/plane/prodoc/` for all code. The two permitted upstream edit locations (`settings/common.py`, `urls.py`) are already in place from Extension 1 — Extension 3 adds ZERO new upstream edits.
- All viewsets must be gated by `ProdocFeatureFlagMixin` and permission-classed by either `ProdocWorkspaceEntityPermission` or `ProdocProjectEntityPermission`.
- All querysets must be workspace-scoped on line 1.
- Soft-delete via `deleted_at`, never hard-delete.
- All validation errors from serializers must be human-readable sentences (for frontend consumption in Extension 3b).
- Do not ask clarifying questions during planning or implementation. Every architectural decision is pre-locked in the "Locked architectural decisions" section above. If you hit a genuine blocker not covered, document it in the PR description as a TODO and continue with the best available workaround.

## Out of scope (do not start)

- Extension 4 (Custom Role Labels). Explicitly forbidden.
- Extension 5 (Internal Comment Sidecar). Explicitly forbidden.
- Extension 3b (Templates UI). That's a separate extension with its own kickoff.
- Retiring the `Webhook.issue` fallback from Extension 1 — defer to Extension 4 or later.
- Computed/derived custom properties beyond the two typed models (MigrationRequirement, ThirdPartyTool).
- Template cloning across workspaces — the slug JSONField approach makes this possible in future, but not in scope this extension.
- A general-purpose typed-custom-property framework.
- UI for anything — that's Extension 3b.
- The India holiday seed command from Extension 2's deferred backlog.
- Real-time collaborative template editing.
- Template marketplace.

## PR requirements

When the extension is complete, open the PR with this description template:

```
## What this ships
Extension 3: Templates, Sites, Waves, and Materialization. 11 commits on prodoc/ext3-templates.

## Commits
0. refactor(prodoc): expose suppress_cascade context manager from Extension 2 signals
1. feat(prodoc): add ProdocMigrationRequirement and ProdocThirdPartyTool reference tables
2. feat(prodoc): add ProdocIssueLink sidecar with typed M2M
3. feat(prodoc): add ProdocSite and ProdocWave models with Plane Module mirror FK
4. feat(prodoc): add ProdocTemplate model family and idempotency marker on ProdocProjectSettings
5. feat(prodoc): add template materialization engine with cascade suppression and idempotency
6. feat(prodoc): REST API for template CRUD, versioning, and diff
7. feat(prodoc): Celery materialization task with progress tracking and retry safety
8. feat(prodoc): seed_prodoc_template management command
9. test(prodoc): end-to-end template materialization + cascade integration
10. docs: append §7.10 build notes and §5.12 lessons from Extension 3

## Known limitations
- assignee_role_label on template tasks is a CharField, will be wired to Ext 4's ProdocRoleLabel FK later (marked with TODO)
- Webhook.issue fallback from Ext 1 still in place, retire in Ext 4

## Discoveries worth preserving
[to be filled in]

## Test baseline
[prodoc test count before/after, upstream test baseline verification]

## §11.6 review checklist
- [ ] Zero files edited outside apps/api/plane/prodoc/
- [ ] All viewsets gated by ProdocFeatureFlagMixin
- [ ] All querysets workspace-scoped
- [ ] All migrations reversible
- [ ] All new models have __str__ methods
- [ ] All serializer validation errors are human-readable sentences
- [ ] Extension 1 and 2 tests still pass
- [ ] E2E integration test (commit 9) passes
```

## END KICKOFF
