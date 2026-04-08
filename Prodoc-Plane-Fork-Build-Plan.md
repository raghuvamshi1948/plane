# Prodoc Plane Fork — Final Build Plan

**Audience:** Claude Code, running inside a fork of `makeplane/plane`.
**Prerequisite reading:** `CLAUDE.md` at the repo root. Every rule there applies to every extension below.
**Owner:** Raghu (Prodoc AI).
**Status:** Final. All architectural decisions locked. Ready for development.

---

## 0. How to use this document

This file is the build specification for the five extensions Prodoc needs on top of Plane. Each extension is a discrete deliverable, in build order. For each one you get: why it exists, what's in and out of scope, end-to-end scenarios written from the human's perspective, the data model, the API contract, the business logic, the required tests, and a definition-of-done checklist.

Work the extensions in order. Do not start Extension N+1 until Extension N is merged, tested, and deployed to staging. Each extension is sized for one to three focused Claude Code sessions, except Extension 3 which is four to six.

If anything in this file conflicts with `CLAUDE.md`, `CLAUDE.md` wins. Surface the conflict in chat.

---

## 1. Repository layout (read this first)

This fork of Plane uses a monorepo layout with `apps/` as the top-level container. The paths Claude Code needs to know:

| What                                                          | Where                       |
| ------------------------------------------------------------- | --------------------------- |
| Backend Django project                                        | `apps/api/plane/`           |
| Prodoc Django app (all our code)                              | `apps/api/plane/prodoc/`    |
| Plane's session-auth viewsets (do not edit)                   | `apps/api/plane/app/`       |
| Plane's public REST API viewsets (do not edit, but reference) | `apps/api/plane/api/`       |
| Plane's anonymous public boards (reference only)              | `apps/api/plane/space/`     |
| Plane's database models (do not edit, only FK to)             | `apps/api/plane/db/models/` |
| Plane's Celery config (one permitted edit)                    | `apps/api/plane/celery.py`  |
| Plane's settings (one permitted edit for `INSTALLED_APPS`)    | `apps/api/plane/settings/`  |
| Plane's root URL conf (one permitted edit for include)        | `apps/api/plane/urls.py`    |
| License/instance config helpers                               | `apps/api/plane/license/`   |
| Background task definitions (Plane's, do not edit)            | `apps/api/plane/bgtasks/`   |
| Requirements files                                            | `apps/api/requirements/`    |
| Web frontend (Next.js, Plane's, do not edit)                  | `web/`                      |
| Prodoc frontend additions go here                             | `web/components/prodoc/`    |
| Public boards frontend (reference only)                       | `space/`                    |
| Admin / God Mode frontend (reference only)                    | `admin/`                    |

The single most important rule from `CLAUDE.md` §2: every line of Prodoc backend code lives under `apps/api/plane/prodoc/`, with three permitted exceptions for one-line additive edits (`INSTALLED_APPS`, root URL include, Celery Beat schedule). Every line of Prodoc frontend code lives under `web/components/prodoc/`. No exceptions, no inline patches to upstream files.

---

## 2. Project context

Prodoc AI runs customer onboardings for healthcare providers. A typical engagement looks like the MGM Hospitals project: four hospitals onboarded across two waves (Wave 1 = Hospitals 1 and 2, Wave 2 = Hospitals 3 and 4), spanning ~37 tasks across twelve workstreams (Governance, Stakeholders, Access, Platform, Data, Integration, AI, Training, UAT, Go-Live, Hypercare, Closure). Each task has a primary owner, supporting owners, dependencies on earlier tasks, and offset-based dates (T+N working days from project start).

The Ops team needs to run multiple such projects in parallel, with customers and third-party integration partners all working in the same system. The tool must enforce strict workspace isolation, support template-driven project creation so every engagement inherits the proven playbook, auto-compute dates based on working days and India public holidays, cascade dates when upstream tasks slip, trigger tiered email escalations on SLA breach, and keep internal Prodoc discussion separate from customer-visible conversation.

Plane provides projects, work items, modules, cycles, webhooks, permissions, Postgres, Celery, and a web UI. The five extensions in this document fill the gaps where Plane doesn't cover Prodoc's specific needs.

---

## 3. Plane capabilities we leverage

The fork's feature inventory confirms a rich set of native Plane capabilities. Knowing what's already there shapes every extension below — we use Plane's primitives wherever possible and only add new models when there's no equivalent.

**Core entities to build on:**

- **Workspaces** are our tenant boundary. Every Prodoc table carries `workspace_id` directly or transitively.
- **Projects** are our customer engagement container. We do not create projects ourselves; ops uses Plane's existing project creation, then calls our materialization endpoint to populate it.
- **Work items** are the fundamental task unit. We create them via Plane's ORM during materialization.
- **Issue Types** with custom properties are how we attach Prodoc metadata (`prodoc_template_task_id`, `prodoc_site_id`, `prodoc_wave_id`, `prodoc_sla_hours`) as first-class typed fields rather than ad-hoc tags.
- **Modules** are our paired native representation of Waves. When we create a Prodoc Wave, we also create a Plane Module of the same name and attach the Wave's work items to it. Ops gets Plane's native Module UI (filtering, burndown, progress) for free.
- **Labels** are project-scoped tags. Available for Site identification if needed.
- **Issue relations** exist in the database (`IssueRelation` model) but are not exposed through the public REST API. Extension 1 fixes this.
- **Pages** are rich-text wiki pages with collaborative editing. We use these for migration requirements and third-party tool documentation rather than building parallel content models — see Extension 3 §6.4.
- **Notifications** with subscribed/created/assigned filtering already exist. Any future escalation engine fans out through this rather than building a new notification system.
- **Analytics** dashboards are workspace and project scoped. With our Issue Type custom properties, ops gets reporting on Prodoc tasks for free without us building any UI.
- **Search** is global across entities. Combined with custom properties, this gives ops cross-project query for free.
- **Deploy boards** publish read-only views via the `space/` app — relevant for any future customer-facing public dashboard.
- **Importers** (Jira, GitHub) under `integration/` — out of scope but worth knowing for future migrations of customer plans.
- **Public REST API** at `/api/v1/` with X-API-Key auth and throttling. This is the surface we extend.
- **Webhooks** are HMAC-signed with retries via `model_activity → send_webhook`. Extension 1 wires `IssueRelation` events into this fan-out.
- **API tokens** are workspace-scoped, which gives us auth-layer isolation for partner integrations in addition to our queryset filtering.
- **Instance admin / God Mode** is where the `PRODOC_FEATURES_ENABLED` flag lives. Reachable via `apps/api/plane/license/utils/instance_value.py:get_configuration_value`.

**Capabilities deliberately NOT used:**

- **Cycles** are sprint-style time boxes. They don't fit our offset-based scheduling. Leave alone.
- **Estimates** are story points. They don't correspond to our SLA hours. Leave alone.
- **Drafts** are personal scratchpads, not the dry-run preview we need for materialization.
- **Stickies** are personal sticky notes. Out of scope.

**Templates: status uncertain.** Two feature inventories from the fork have failed to mention Plane's native template system. Either this fork is on a Plane version that predates templates, or templates are behind a feature flag, or both inventories missed them. **Before starting Extension 3, run the templates investigation prompt in §10 of this document.** The result determines whether Extension 3 builds standalone Prodoc templates (current plan, Option A) or extends Plane's native templates (Option B). Default assumption is Option A; this document is written for that path.

---

## 4. Architectural constants

These are restated from `CLAUDE.md` for convenience. Do not re-derive any of them.

- **Tenant boundary:** Plane's `Workspace`. No row-level security at the database layer; isolation is enforced in Python via `WorkspaceMember` and `ProjectMember` permission classes. Every new viewset subclasses Plane's existing permission classes. Every new queryset filters by `workspace_id` on its first line.
- **API surface:** All Prodoc endpoints mount under `/api/v1/prodoc/`, authenticated via `X-API-Key` header, throttled with Plane's existing API throttle classes. Nothing under `app/` or `space/`.
- **Python package:** All Prodoc backend code lives under `apps/api/plane/prodoc/`. A single Django app. The three permitted upstream edits are `INSTALLED_APPS`, root URL include, and Celery Beat additions.
- **Celery:** All Prodoc background tasks live in `apps/api/plane/prodoc/tasks.py`, named with a `prodoc_` prefix, registered in Plane's existing Beat schedule.
- **Webhooks:** New model events fan out via Plane's existing `model_activity → send_webhook` pipeline, namespaced `prodoc.<resource>.<verb>`.
- **Feature flag:** Every extension is gated on `get_configuration_value("PRODOC_FEATURES_ENABLED")`. Disabled endpoints return 404, not 403, to avoid leaking existence. Default is `False`; enabled per-instance via God Mode.
- **Soft delete:** Every Prodoc model inherits Plane's `BaseModel`, uses `deleted_at`, never calls `.delete()` directly.
- **Frontend:** Only Extension 5 touches the React frontend, and only via new components under `web/components/prodoc/`. Never modify upstream `.tsx` files.

---

## 5. Extension 1 — Public Dependency API

### 5.1 Why it exists

Plane's public v1 REST API does not support issue relations (blocks, blocked-by, depends-on, relates-to, duplicate). The functionality exists in Plane's internal `app/` viewset that the React frontend uses, but is not exposed to API consumers. Every downstream Prodoc extension needs to create dependency edges programmatically — without this endpoint, ops would have to manually re-create every dependency link in the UI every time a template is materialized into a project. That defeats the entire purpose of templating.

### 5.2 Scope

**In scope:**

- Create a dependency edge between two work items.
- List all dependency edges on a given work item, both directions.
- Delete a dependency edge.
- Support relation types as defined by Plane's existing `IssueRelation` model — minimally `blocks`, `blocked_by`, `depends_on`.
- Workspace and project permission enforcement on every request.
- Webhook fan-out on create and delete via `prodoc.dependency.created` and `prodoc.dependency.deleted`.

**Out of scope:**

- Bulk create. Extension 3 will call this endpoint in a loop or add a bulk route later if needed.
- Updating a relation type in place — delete and recreate instead.
- Any UI changes. Plane's existing UI already renders relations from the `IssueRelation` model — our API just adds a second write path to the same model.

### 5.3 Scenarios

**Scenario 1: Materialization script seeds dependencies.** Ops runs the Extension 3 materialization endpoint, which clones a Prodoc template into a new Plane project. For each template task that declares `depends_on: [task_id_earlier]`, the materializer needs to create a blocking relation so Plane's UI shows the dependency arrow. After Extension 1 ships, this is one POST per dependency edge.

**Scenario 2: Ops reorders tasks mid-project.** Mid-project, ops realizes Task 17 must actually block Task 18, not the other way around. They write a small script that lists relations on Task 17, deletes the wrong one, creates the new one. All via the public API.

**Scenario 3: Partner sync.** A third-party integration partner has their own planning tool and wants to mirror dependency relations into Plane. Their sync script polls their system, computes diffs, and pushes create/delete calls. Their API key is workspace-scoped, so they cannot read or write outside the single project they're authorized for.

**Scenario 4: Webhook consumer rebuilds dependency graph.** Extension 2's cascade engine subscribes to `prodoc.dependency.created` and `prodoc.dependency.deleted`, receives HMAC-signed payloads, and triggers a recompute when the graph changes.

**Scenario 5: Workspace isolation under attack.** A malicious script with a valid API key for Workspace A attempts to create a relation between two work items where one belongs to Workspace B. The request must be rejected with 404, the attempt logged, and no relation created.

### 5.4 Data model

**No new tables.** Reuses Plane's existing `IssueRelation` model verbatim. We add only a new viewset, serializer, URL routes, and permission enforcement.

If `IssueRelation`'s shape doesn't quite match what we need (for example, if it stores only one direction of the edge and the other is computed), read the model carefully and match its semantics — never modify the upstream model.

### 5.5 API contract

**Base:** `POST/GET/DELETE /api/v1/prodoc/workspaces/{workspace_slug}/projects/{project_id}/work-items/{work_item_id}/relations/`

**Auth:** `X-API-Key` header, reusing Plane's existing API key auth class.
**Permissions:** Subclass `ProjectEntityPermission`. Workspace and project membership checked on every request.
**Feature flag:** `PRODOC_FEATURES_ENABLED` — disabled returns 404.

**POST** request body:

```json
{
  "related_issue": "<work_item_uuid>",
  "relation_type": "blocks"
}
```

`relation_type` validated against `IssueRelation`'s choices; invalid values return 400.

Response (201):

```json
{
  "id": "<relation_uuid>",
  "issue": "<work_item_uuid_from_url>",
  "related_issue": "<work_item_uuid>",
  "relation_type": "blocks",
  "workspace": "<workspace_uuid>",
  "project": "<project_uuid>",
  "created_at": "2026-04-07T10:00:00Z",
  "created_by": "<user_uuid>"
}
```

**Validation rules:**

- Both work items must exist and belong to the same project. Cross-project relations rejected with 400.
- The related work item must belong to the same workspace.
- Self-relations (`issue == related_issue`) rejected with 400.
- Duplicate relations (same triple) rejected with 409.
- If `model_activity` does not already fire on `IssueRelation` creates, register it explicitly so webhook fan-out works.

**GET** lists relations. Includes both directions — relations where the URL's work item is the `issue` side and relations where it is the `related_issue` side. Optional `?relation_type=blocks` filter.

**DELETE** at `/api/v1/prodoc/.../relations/{relation_id}/`. Returns 204 on success, 404 if relation does not exist or belongs to a different scope. Fires `prodoc.dependency.deleted` webhook.

### 5.6 Business logic

- **Permission check order:** workspace membership → project membership → project-level role check. Reuse existing classes.
- **Webhook wiring:** before writing the viewset, grep `apps/api/plane/bgtasks/` for `model_activity` and verify whether `IssueRelation` is registered. If not, register it as part of this extension.
- **Error shapes:** match Plane's existing API error response shape. Look at `apps/api/plane/api/views/issue.py` for the pattern.

### 5.7 Tests required to ship

Tests in `apps/api/plane/prodoc/tests/test_dependency_api.py`.

1. Happy path create — authenticated user with project membership creates a `blocks` relation; expect 201 and visible via GET.
2. Happy path list — two relations, both returned.
3. Happy path delete — create then delete, list returns empty.
4. Workspace isolation — Workspace A key trying to relate Workspace B work items returns 404.
5. Cross-project rejection — same workspace, different projects, 400.
6. Self-relation rejection — 400.
7. Duplicate rejection — 409.
8. Invalid relation type — 400.
9. Permission denied — workspace member who is not a project member, 403.
10. Feature flag disabled — all verbs return 404.
11. Webhook fires — assert `prodoc.dependency.created` and `prodoc.dependency.deleted` events appear in the outbox.

### 5.8 Definition of done

- [ ] New viewset at `apps/api/plane/prodoc/views/dependency.py`.
- [ ] New serializer at `apps/api/plane/prodoc/serializers/dependency.py`.
- [ ] URL routes registered in `apps/api/plane/prodoc/urls.py`, mounted at `/api/v1/prodoc/`.
- [ ] `IssueRelation` registered with `model_activity` for webhook fan-out (if not already).
- [ ] Feature flag gating.
- [ ] All eleven tests pass.
- [ ] Smoke script at `apps/api/plane/prodoc/scripts/smoke_dependency_api.py` creates, lists, and deletes a relation against a running instance.
- [ ] Manual verification on staging: relations appear in Plane UI dependency view.

### 5.9 Build notes (Extension 1, shipped)

This section is appended after Extension 1 was implemented, to record what changed between the original plan in §5.1–§5.8 (written before the upstream code was inspected) and what actually shipped.

**(a) Original premise.** §5.1 said: "Plane's public v1 REST API does not expose issue relations (blocks / blocked-by / depends-on)." On that premise, §5.5 specified a full GET / POST / DELETE surface to be built from scratch under `/api/v1/prodoc/`.

**(b) What we found upstream.** A pre-existing public endpoint, `IssueRelationListCreateAPIEndpoint`, lives at `apps/api/plane/api/views/issue.py:2266` and is registered at `apps/api/plane/api/urls/work_item.py:150`. It serves:

- `GET  /api/v1/workspaces/<slug>/projects/<project_id>/work-items/<issue_id>/relations/`
- `POST /api/v1/workspaces/<slug>/projects/<project_id>/work-items/<issue_id>/relations/`

It does **not** implement DELETE. It does **not** call the webhook fan-out pipeline (`webhook_activity` only routes the recognized event types `project`, `issue`, `module`, `module_issue`, `cycle`, `cycle_issue`, `issue_comment` — see `apps/api/plane/bgtasks/webhook_task.py:418`). It is **not** feature-gated. And it has **no test coverage** anywhere in `apps/api/plane/tests/`. Separately, the `Webhook` model (`apps/api/plane/db/models/webhook.py:34`) has no `issue_relation` opt-in boolean and we are not allowed to add one (upstream model).

The build plan was operating on a stale premise. We do not need to duplicate GET or POST.

**(c) What we actually built (Option B, lean).**

1. **No GET / POST in the prodoc app.** Consumers use upstream's existing endpoint for create and list. Documented in this section so future Extension 3 work knows to call upstream POST for relation creation and our prodoc DELETE for removal.
2. **A new prodoc-side DELETE endpoint** at `/api/v1/prodoc/workspaces/<slug>/projects/<project_id>/work-items/<issue_id>/relations/<relation_id>/`, in `apps/api/plane/prodoc/views/dependency.py`. The endpoint mirrors the activity-log payload of upstream's internal `remove_relation` (`apps/api/plane/app/views/issue/relation.py:262`) so the Plane UI activity renderer treats prodoc deletions identically to UI deletions.
3. **Soft-delete via `deleted_at` + `save()`**, not `relation.delete()`. Plane's `SoftDeleteModel.delete()` (`apps/api/plane/db/mixins.py:72`) silently soft-deletes by default, which means **`post_delete` never fires for relation removal in this codebase** — only `post_save` does, with `deleted_at` populated. We discovered this during test development. The viewset now sets `deleted_at` and calls `save()` explicitly per CLAUDE.md §5.
4. **A single `post_save` signal handler** in `apps/api/plane/prodoc/signals/dependency.py` that detects both creates (`created=True`) and soft-deletes (`instance.deleted_at is not None`) and dispatches `prodoc.dependency.created` / `prodoc.dependency.deleted` to a Celery fan-out task. This is the proof that **all relation write paths** — upstream POST, prodoc DELETE, future Extension 3 ORM writes — are caught by one handler.
5. **A prodoc-side dispatcher task** `prodoc_dispatch_dependency_webhook` in `apps/api/plane/prodoc/tasks.py` that filters `Webhook.objects.filter(workspace_id=..., is_active=True, issue=True, deleted_at__isnull=True)` and calls the existing upstream `webhook_send_task.delay(...)` (`apps/api/plane/bgtasks/webhook_task.py:260`) directly with our event name and payload. This avoids editing `webhook_task.webhook_activity`, which would have required modifying a forbidden upstream file and adding a model field.
6. **A `ProdocFeatureFlagMixin`** in `apps/api/plane/prodoc/views/base.py` returning 404 (not 403) when `PRODOC_FEATURES_ENABLED != "1"`, per CLAUDE.md §8. The mixin uses the canonical tuple-unpacking pattern from `apps/api/plane/authentication/adapter/base.py:135` (`get_configuration_value` returns a tuple aligned with the input keys; values are strings).
7. **A `ProdocProjectEntityPermission` subclass** in `apps/api/plane/prodoc/permissions/project.py` — currently a pass-through over upstream's `ProjectEntityPermission`. Exists as a Prodoc-side seam so future extensions can tighten or relax permissions without monkey-patching upstream.
8. **The full prodoc Django app skeleton** under `apps/api/plane/prodoc/` (models, serializers, views, permissions, signals, tasks, migrations, tests, scripts as packages). Most directories are empty and reserved for Extensions 2–5. `apps.py:ready()` imports the signals module so handlers register at app load.
9. **Ten contract tests** in `apps/api/plane/prodoc/tests/contract/test_dependency_api.py` (pruned from the original eleven; the create/list tests in §5.7 were dropped because they belong to upstream's surface, not ours). Tests cover: happy-path delete, four 404 paths (nonexistent, wrong project, wrong issue, cross-tenant), permission denied for non-project workspace member, feature-flag-disabled, and three signal-firing assertions (created on ORM create, deleted on prodoc DELETE, no-op when flag disabled). The local conftest declares `pytest_plugins = ["plane.tests.conftest"]` so the upstream `api_key_client` / `workspace` / `create_user` fixtures are visible from a sibling path.
10. **A standalone smoke script** at `apps/api/plane/prodoc/scripts/smoke_dependency_api.py` that creates a relation via upstream POST, deletes it via prodoc DELETE, and verifies removal via upstream GET against a running instance.
11. **Two permitted upstream edits** (per CLAUDE.md §2): `"plane.prodoc"` added to `INSTALLED_APPS` in `apps/api/plane/settings/common.py`, and `path("api/v1/prodoc/", include("plane.prodoc.urls"))` added to `apps/api/plane/urls.py`. The third permitted edit (Celery Beat schedule) was not needed in Extension 1.

**(d) Why these choices.**

- **Avoid duplicating GET/POST:** less code to maintain, no merge surface against upstream's relation endpoint, and consumers benefit immediately when upstream improves the existing endpoint.
- **Signal handler over endpoint hooks:** catches every write path automatically — upstream POST today, future Extension 3 ORM writes tomorrow, and any other code paths we haven't anticipated. A view-only fan-out would have been blind to upstream's endpoint.
- **Consolidated `post_save` handler:** discovered at test time that `post_delete` doesn't fire because `SoftDeleteModel.delete()` is a save in disguise. One handler that branches on `created` vs `deleted_at` is simpler than two handlers and reflects the actual behavior of the codebase.
- **Workspace isolation tested:** the cross-tenant test (workspace A's API key cannot delete workspace B's relation) is the headline check required by CLAUDE.md §3 and is the most important test in the file.

**Known limitation, to be resolved in Extension 2.** Our dispatcher piggybacks on the existing `Webhook.issue` boolean for opt-in. The `Webhook` model has no `issue_relation` / `dependency` field, and we are not allowed to add one in Extension 1 (it's an upstream model, see CLAUDE.md §2). This means webhook subscribers who opted into `issue` events now also receive `prodoc.dependency.*` events. Defensible (dependency edges are issue-adjacent), but not ideal. **Extension 2 should add a dedicated `Webhook.dependency` field via a Prodoc migration** (or a separate `ProdocWebhookSubscription` Prodoc-side model that joins to `Webhook`) and update `prodoc_dispatch_dependency_webhook` to filter on the new opt-in.

**Separate defect, surfaced but not fixed.** Upstream Plane has zero test coverage for `IssueRelationListCreateAPIEndpoint` (neither for the internal `app/` viewset nor the public `api/` viewset). This file's ten tests are the **first** `IssueRelation` tests anywhere in this fork's test suite. Track separately; do not fix in Extension 1.

**Vocabulary correction.** The relation type strings used throughout this section should come from `IssueRelationChoices` in `apps/api/plane/db/models/issue.py:263`: `blocked_by`, `relates_to`, `duplicate`, `start_before`, `finish_before`, `implemented_by`, plus the synthetic reverse names `blocking`, `start_after`, `finish_after`, `implements`. Earlier drafts of §5 referenced `blocks` / `depends_on` which do not exist in the upstream vocabulary.

### 5.10 Lessons for future extensions

Two reusable lessons surfaced during Extension 1 development. Recording them here so future extensions don't relearn them at test-debug time.

**(a) `SoftDeleteModel.delete()` is a save, not a delete.** Plane's soft-delete mixin at `apps/api/plane/db/mixins.py:72` overrides `Model.delete()` to set `deleted_at = timezone.now()` and call `save()` by default. The actual SQL `DELETE` only runs when the nightly `hard_delete` sweep runs, hours later, in a different process. **Consequence:** `post_delete` signals **never fire** for soft-deletable models in the request path. Any signal-based fan-out (webhooks, cache invalidation, dependency cascades) must register on `post_save` and inspect `instance.deleted_at is not None` to distinguish "create / normal update" from "soft-delete". A single consolidated `post_save` handler is the canonical pattern — see `apps/api/plane/prodoc/signals/dependency.py` for the reference implementation. Do not be tempted to register a `post_delete` receiver "just in case" — it will silently never fire and lull you into thinking your fan-out works.

**(b) `webhook_send_task.delay` is a public surface from the Prodoc side.** `apps/api/plane/bgtasks/webhook_task.py:260` accepts `(webhook_id, slug, event, event_data, action, current_site, activity)` and is callable directly from any Prodoc Celery task. This means **Prodoc can fan out webhooks for new event types without forking the webhook plumbing** and without editing the upstream `webhook_activity` event filter at `apps/api/plane/bgtasks/webhook_task.py:418` (which would require touching a forbidden file and adding model fields). The right pattern: write a small Prodoc-side dispatcher in `apps/api/plane/prodoc/tasks.py` that queries `Webhook.objects.filter(workspace_id=..., is_active=True, deleted_at__isnull=True, ...)` with whatever opt-in semantics are appropriate, and calls `webhook_send_task.delay(...)` per matching webhook. For the opt-in field itself: **do not add a column to the upstream `Webhook` model.** Django won't expose a column to the ORM unless the field is declared on the model class, which is forbidden by §2. Use a Prodoc-side sidecar OneToOne settings model instead (e.g., `ProdocWebhookSettings(webhook=OneToOneField(Webhook, ...), <opt_in_bool>=BooleanField(default=False))`) and join through it in the dispatcher's query — see Extension 2 for the reference implementation.

---

## 6. Extension 2 — Business-Day Scheduler and Dependency Cascade

### 6.1 Why it exists

Prodoc templates describe task timing as offsets from project start (T, T+3, T+7, in working days) plus dependency edges. When a project is created, every task needs a real calendar date computed from project start, offset, India public holidays, and weekends. When a task slips (its target moves later than planned), every downstream task that depends on it must cascade forward by the same delta.

Plane has none of this. It stores `start_date` and `target_date` as raw calendar dates with no business-day awareness and no cascade. Ops currently does the math in spreadsheets and re-enters every date manually. This extension moves that into Celery.

### 6.2 Scope

**In scope:**

- A `HolidayCalendar` model storing non-working days (weekends are computed, only named holidays are stored).
- A `compute_target_date` function: given start, offset in working days, and workspace, return the target date skipping weekends and holidays.
- A `prodoc_cascade_dependencies` Celery task: when a work item's `target_date` changes, walk the dependency graph forward and push downstream work items by the delta.
- A signal handler on Plane's `Issue` model that triggers the cascade on `target_date` updates.
- REST API for holiday CRUD.
- India public holiday seed data for 2026 and 2027 via a Django management command.

**As-built note (added after Extension 2 shipped):** §6.2's original "one calendar per workspace" scope was widened during Ext 2 implementation to **workspace default + optional per-project override** via a `ProdocProjectSettings` sidecar model (`apps/api/plane/prodoc/models/project_settings.py`). The sidecar holds an optional `holiday_calendar` ForeignKey; when set, it overrides the workspace default for that project's cascade computations. The override mechanism does not modify upstream's `Project` model — strict §2 compliance via OneToOne sidecar. The build plan was updated in Ext 2 commit 1 to keep the doc and the code in sync.

**Out of scope:**

- Multiple calendars per workspace beyond a single named default — _partially relaxed._ Multiple `HolidayCalendar` rows can coexist in a workspace; the resolver picks the project's override if set, otherwise falls back to the first calendar by name. No "default" flag yet — that's Extension 3 if needed.
- Backward cascade (early finishes do not pull downstream dates in).
- Resource leveling or capacity planning.
- Skipping holidays during cascade if downstream tasks have manually-locked dates (locking is part of Extension 3).

### 6.3 Scenarios

**Scenario 1: New project from template.** Template says "Task 1 at T+0, Task 2 at T+3, Task 3 at T+5 depending on Task 2." Project start is Monday April 13, 2026. `compute_target_date(2026-04-13, 3, ws)` returns `2026-04-16`; offset 5 returns `2026-04-20`.

**Scenario 2: India holiday in the middle.** Workspace's calendar includes `2026-04-14` (Ambedkar Jayanti). Computing offset 3 from April 13 returns `2026-04-17`, not April 16.

**Scenario 3: Upstream slip cascades.** Task 2's target was April 16. Ops updates it to April 20 (a 2-working-day slip). Signal handler enqueues `prodoc_cascade_dependencies(task_2.id)`. Task 3 (downstream) moves forward 2 working days to April 22. Task 3's save triggers another cascade run; Task 3 has no downstream, so the cascade terminates.

**Scenario 4: Diamond dependency.** A blocks B and C; both block D. A slips 3 days. B and C both move forward 3 days. D is reached twice but moves forward exactly 3 days, not 6 — the second time D is processed, its old target is already updated and the delta is 0.

**Scenario 5: Cycle detection.** A bug or attack creates a cycle (A blocks B blocks A). The cascade detects the cycle on a visited set and exits without infinite-looping. Test asserts termination within 5 seconds.

**Scenario 6: Holiday added mid-project.** Ops adds Good Friday after the fact. Existing projects' dates do NOT auto-recompute — adding a holiday is forward-looking only. A separate `POST /projects/{id}/recompute-dates/` endpoint can force a full recompute (this endpoint belongs to Extension 3, not Extension 2).

**Scenario 7: Cross-workspace holiday isolation.** WS A has Diwali; WS B does not. Same date computation in both yields different results.

### 6.4 Data model

`apps/api/plane/prodoc/models/holiday.py`:

```python
from django.db import models
from plane.db.models import BaseModel, Workspace

class HolidayCalendar(BaseModel):
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="prodoc_holidays"
    )
    date = models.DateField()
    name = models.CharField(max_length=200)

    class Meta:
        unique_together = [("workspace", "date")]
        indexes = [models.Index(fields=["workspace", "date"])]
```

Migration: `apps/api/plane/prodoc/migrations/000X_holidaycalendar.py` (numbering follows Extension 1 if it added any models; otherwise this is `0001`).

Seed command: `apps/api/plane/prodoc/management/commands/seed_india_holidays.py` — given a workspace ID, inserts 2026 and 2027 India public holidays. Update the holiday list annually.

### 6.5 API contract

- `GET /api/v1/prodoc/workspaces/{slug}/holidays/` — list. Optional `?year=2026`.
- `POST /api/v1/prodoc/workspaces/{slug}/holidays/` — create. Body: `{"date": "2026-10-02", "name": "Gandhi Jayanti"}`. Permission: `WorkspaceAdminPermission` only.
- `DELETE /api/v1/prodoc/workspaces/{slug}/holidays/{id}/` — delete.
- `POST /api/v1/prodoc/workspaces/{slug}/holidays/bulk/` — bulk insert for the seed command.

Feature flag and workspace isolation apply.

### 6.6 Business logic

`compute_target_date(start_date, offset_working_days, workspace_id)` lives in `apps/api/plane/prodoc/scheduler.py`.

```
1. If offset == 0, return start_date unchanged (even if it's a weekend or holiday — project start is project start).
2. Load all holidays for the workspace into a set. Cache for the call duration.
3. Walk forward from start_date day by day:
   - Skip Saturdays, Sundays, and dates in the holiday set.
   - Otherwise count as a working day.
   - Return when working day count equals offset.
4. Guard: max walk of 365 days, raise on overflow.
```

If `numpy` is already in `apps/api/requirements/base.txt`, prefer `numpy.busday_offset(start, offset, holidays=holidays_array)` for speed — this matters when Extension 3 materializes a 40-task template.

`prodoc_cascade_dependencies(issue_id)` Celery task:

```
1. Load issue. Return if deleted or missing.
2. Compute slip delta: new target_date minus old target_date in working days.
3. If slip <= 0, return.
4. Find downstream issues via IssueRelation where related_issue == issue_id and relation_type in ('blocks','depends_on').
5. For each downstream:
   a. new_target = compute_target_date(downstream.target_date, slip, workspace_id)
   b. If new_target == old, skip.
   c. Update and save with skip_cascade flag to avoid re-triggering on this iteration; subsequent saves elsewhere will re-fire normally.
6. Recurse via signal — visited set passed through to detect cycles. Log warning and stop on cycle.
```

**Signal wiring:** in `apps/api/plane/prodoc/signals.py`, register `post_save` on Plane's `Issue` (imported, not modified). Check if `target_date` changed. If yes, enqueue cascade. Use a thread-local flag or `update_fields` check to prevent recursion. Register the signal in `apps/api/plane/prodoc/apps.py:ready()`.

### 6.7 Tests required to ship

`apps/api/plane/prodoc/tests/test_scheduler.py`:

1. Simple offset, no holidays: `(2026-04-13, 3)` → `2026-04-16`.
2. Weekend skipping: `(2026-04-17 Friday, 1)` → `2026-04-20 Monday`.
3. Holiday skipping: with Ambedkar Jayanti seeded, `(2026-04-13, 3)` → `2026-04-17`.
4. Weekend and holiday combined.
5. Zero offset returns start_date unchanged, even if start_date is a holiday.
6. Cascade single link: A blocks B, A slips 3, B moves 3.
7. Cascade chain: A→B→C, A slips 3, B and C both move 3.
8. Diamond: A→{B,C}→D, A slips 3, D moves exactly 3 (not 6).
9. Cycle termination: A→B→A terminates within 5 seconds.
10. Backward slip ignored: negative slip, no cascade.
11. Workspace isolation on holidays: same date range yields different results in different workspaces.
12. Holiday API CRUD.
13. Holiday API permission: regular member can't POST, admin can.
14. Feature flag off: 404 on endpoints, silent early-return on cascade.
15. Seed command inserts expected rows.

### 6.8 Definition of done

- [ ] `HolidayCalendar` model and migration.
- [ ] `compute_target_date` function.
- [ ] `prodoc_cascade_dependencies` Celery task with cycle detection.
- [ ] Signal handler on `Issue.post_save`.
- [ ] Holiday REST API.
- [ ] India holiday seed command with 2026 and 2027 data.
- [ ] All 15 tests pass.
- [ ] Integration test on staging: 3-task chain, manually shift first task's target, observe cascade complete within 30 seconds.

---

## 7. Extension 3 — Templates, Sites, Waves, Materialization

This is the largest extension. Plan for four to six Claude Code sessions broken across the sub-modules below.

### 7.1 Why it exists

This is the core of the Prodoc Ops Tool. A Project Template describes a reusable implementation playbook (Patient Engagement CRM onboarding, Partner Management rollout, etc.) as a set of template tasks with offsets, dependencies, role assignments, SLAs, sections, plus references to migration requirements and third-party tools. When ops starts a new customer project, the template gets materialized into concrete Plane work items — expanded per Site (independent user teams like individual hospitals) and per Wave (rollout cohorts that bundle Sites) — with dates computed via Extension 2 and dependencies wired via Extension 1.

Without this extension, every new customer project requires an ops engineer to manually re-create ~40 work items, re-enter dates, and re-wire dependencies from a spreadsheet. With it, materialization is one API call.

**Decision locked in:** Sites belong to Project (per-project, not persistent-per-customer). Per the loose-end review, this simplifies the data model and is reversible later via a nullable `organization_site_id` upgrade if cross-project Site reporting becomes important.

### 7.2 Scope

**In scope:**

- `Site` model, scoped per project.
- `Wave` model, scoped per project, references Sites via a join table. Each Wave is mirrored as a native Plane Module of the same name.
- `ProjectTemplate` model, workspace-scoped, versioned.
- `TemplateSection` model, an ordered grouping of template tasks within a template.
- `TemplateTask` model, the reusable task blueprint with offset, duration, SLA, role, dependencies, repeat-per-site flag, repeat-per-wave flag, dependency mode.
- `MigrationRequirement` model, a thin metadata wrapper that links to a Plane Page for content.
- `ThirdPartyTool` model, a thin metadata wrapper that links to a Plane Page for content.
- `ProjectMaterializationJob` model, tracks materialization run state.
- A workspace-level Plane Issue Type called "Prodoc Implementation Task" with typed custom properties for `template_task_id`, `site_id`, `wave_id`, `sla_hours`. Created during deployment via a management command.
- Full CRUD API for all Prodoc-side template models, Sites, and Waves.
- The materialization endpoint: `POST /api/v1/prodoc/projects/{project_id}/materialize/`.

**Out of scope:**

- Template inheritance (one template extending another). Each template is standalone in v1.
- Template-level conditional logic. Use separate templates instead.
- Editing a template after it has been used to materialize a project — once materialized, the project's work items are disconnected from the template.
- Custom role labels (Extension 4). For Extension 3 v1, template tasks reference one of Plane's three native roles directly.
- Frontend UI for managing templates. CRUD is via API initially; ops uses Postman, scripts, or a small admin tool until a real UI is built.

### 7.3 Scenarios

**Scenario 1: Ops authors a template from the MGM playbook.** Raghu has the MGM Phase-1 plan as an Excel file with 37 tasks across 12 workstreams. He (or a script) walks the spreadsheet and creates: one `ProjectTemplate` named "Healthcare Provider Onboarding v1", twelve `TemplateSection` rows (one per workstream), 37 `TemplateTask` rows with offsets, durations, dependencies (referenced by template task ID, not Plane work item ID), and role assignments. Some tasks are marked `repeat_per_site=true` (e.g., "Hospital-specific IT access provisioning") and some `repeat_per_wave=true` (e.g., "Wave go-live readiness review"). Migration requirements and third-party tool docs are created as Plane Pages and linked via the metadata models. Saved via API.

**Scenario 2: Ops starts a new customer engagement.** MGM Phase 2 begins. Raghu creates a new Plane Project via Plane's existing API. He calls `POST /api/v1/prodoc/projects/{new_project_id}/sites/` four times (Hospital-1 through Hospital-4). He calls `POST /api/v1/prodoc/projects/{new_project_id}/waves/` twice for two Waves, each bundling two Sites. He calls `POST /api/v1/prodoc/projects/{new_project_id}/materialize/` with the template ID and start date `2026-05-01`. The materialization job runs asynchronously — expanding 37 template tasks across 4 sites and 2 waves yields ~120 Plane work items plus ~60 dependency edges. Within a minute, the project is fully populated and the two Plane Modules ("Wave 1", "Wave 2") have the right work items attached.

**Scenario 3: Per-site task expansion.** Template Task 15 is "Provision user accounts" with `repeat_per_site=true`. The project has 4 Sites. Materialization creates 4 work items titled "Provision user accounts — Hospital-1", "... — Hospital-2", and so on, each with the `prodoc_site_id` custom property pointing at the corresponding Site row. Dependencies on Task 15 from downstream tasks are wired according to the template task's `dependency_mode`: `all` means every downstream expansion blocks every upstream expansion; `same_site` means only matching site pairs are linked. Default is `all`.

**Scenario 4: Per-wave task expansion.** Template Task 30 is "Wave go-live readiness review" with `repeat_per_wave=true`. The project has 2 Waves. Materialization creates 2 work items, one per Wave. Wave 2's task is offset by Wave 2's `start_offset_days` (e.g., 30 working days after Wave 1), computed via Extension 2.

**Scenario 5: Mixed expansion.** A template task with both `repeat_per_site=true` and `repeat_per_wave=true` in a project with 2 Waves and 4 Sites (2 per Wave) yields 4 work items: "Task — Wave 1 — Hospital 1", "Task — Wave 1 — Hospital 2", "Task — Wave 2 — Hospital 3", "Task — Wave 2 — Hospital 4".

**Scenario 6: Dependency rewiring.** Template tasks reference each other by template task ID. The materializer builds a map `{template_task_id: [(wave, site, plane_work_item_id), ...]}` and walks the dependency list, creating `IssueRelation` rows via Plane's ORM (faster than going through Extension 1's HTTP endpoint, but the same model — both write paths are valid). The dependency mode determines which expansions get linked.

**Scenario 7: Wave mirrored as Plane Module.** When a Wave is created, the API also creates a Plane Module of the same name in the project. When work items are materialized, those that belong to a Wave are attached to the corresponding Module. Ops can use Plane's native Module view to filter, sort, and see burndown for each Wave.

**Scenario 8: Issue Type and custom properties.** During deployment, a one-time management command creates the "Prodoc Implementation Task" Issue Type at the workspace level with four typed custom properties. Materialization creates work items with this Issue Type set, populating the four custom properties from the template and expansion context. Ops sees these as first-class fields in the Plane UI and can filter Views by them.

**Scenario 9: Migration requirements and third-party tools.** Each `MigrationRequirement` row stores name, status, owner, and a `page_id` foreign key to a Plane Page that holds the actual content (rich text, collaborative editing, AI assist, all native to Plane). Same pattern for `ThirdPartyTool`. Ops gets structured filtering plus rich content without us reinventing rich text editing.

**Scenario 10: Partial failure mid-materialization.** Materialization creates 80 of 120 work items, then hits an error on the 81st. The job rolls back — soft-deletes the 80 created work items, the 2 created Modules, and any IssueRelations. The `ProjectMaterializationJob` row records `status='failed'` and the error log.

**Scenario 11: Workspace isolation.** A template is workspace-scoped. Attempting to materialize Workspace A's template into a project in Workspace B returns 404.

**Scenario 12: Dry run.** `POST /materialize/` with `dry_run=true` returns the plan (the list of work items that would be created, with computed dates and dependency edges) without actually creating anything. Useful for ops to verify before committing.

### 7.4 Data model

All models in `apps/api/plane/prodoc/models/`.

```python
class ProjectTemplate(BaseModel):
    workspace = FK(Workspace)
    name = CharField(max_length=200)
    version = CharField(max_length=20)  # "1.0", "1.1"
    description = TextField(blank=True)
    is_active = BooleanField(default=True)

class TemplateSection(BaseModel):
    template = FK(ProjectTemplate, related_name='sections')
    name = CharField(max_length=200)  # "Governance", "Access"
    order = IntegerField()

class TemplateTask(BaseModel):
    template = FK(ProjectTemplate, related_name='tasks')
    section = FK(TemplateSection, related_name='tasks')
    title = CharField(max_length=300)
    description = TextField(blank=True)
    offset_days = IntegerField()  # T+N working days from project start
    duration_days = IntegerField()
    role_key = CharField(max_length=50)  # canonical role; see Extension 4
    sla_hours = IntegerField(null=True)
    repeat_per_site = BooleanField(default=False)
    repeat_per_wave = BooleanField(default=False)
    dependency_mode = CharField(
        max_length=20, default='all',
        choices=[('all','all'),('same_site','same_site')]
    )
    order = IntegerField()

class TemplateTaskDependency(BaseModel):
    upstream = FK(TemplateTask, related_name='downstream_deps')
    downstream = FK(TemplateTask, related_name='upstream_deps')
    class Meta:
        unique_together = [('upstream', 'downstream')]

# Migration requirements: thin metadata, content in Plane Page
class MigrationRequirement(BaseModel):
    template = FK(ProjectTemplate, related_name='migration_requirements', null=True)
    template_task = FK(TemplateTask, related_name='migration_requirements', null=True)
    name = CharField(max_length=200)
    status = CharField(max_length=20, default='open',
                       choices=[('open','open'),('in_progress','in_progress'),
                                ('blocked','blocked'),('done','done')])
    owner_role = CharField(max_length=50)
    page = FK('db.Page', null=True, blank=True)  # Plane's Page model

# Third-party tools: same pattern
class ThirdPartyTool(BaseModel):
    template = FK(ProjectTemplate, related_name='third_party_tools', null=True)
    template_task = FK(TemplateTask, related_name='third_party_tools', null=True)
    name = CharField(max_length=200)
    contact_notes_short = TextField(blank=True)  # short summary
    page = FK('db.Page', null=True, blank=True)  # rich content lives here

class Site(BaseModel):
    project = FK(Project)
    name = CharField(max_length=200)
    code = CharField(max_length=50)  # short identifier, e.g., "HOSP-01"
    notes = TextField(blank=True)

class Wave(BaseModel):
    project = FK(Project)
    name = CharField(max_length=200)  # "Wave 1", "Wave 2"
    order = IntegerField()
    start_offset_days = IntegerField(default=0)
    plane_module = FK('db.Module', null=True, blank=True)  # mirror in Plane

class WaveSite(BaseModel):
    wave = FK(Wave)
    site = FK(Site)
    class Meta:
        unique_together = [('wave', 'site')]

class ProjectMaterializationJob(BaseModel):
    project = FK(Project)
    template = FK(ProjectTemplate)
    status = CharField(max_length=20,
                       choices=[('queued','queued'),('running','running'),
                                ('succeeded','succeeded'),('failed','failed')])
    start_date = DateField()
    error_log = TextField(blank=True)
    work_items_created = JSONField(default=list)  # for rollback
    modules_created = JSONField(default=list)
    relations_created = JSONField(default=list)
```

All models inherit `BaseModel` (which provides `id`, `workspace_id` where applicable through Project, `created_at`, `updated_at`, `deleted_at`, `created_by`, `updated_by`).

The `Page` and `Module` foreign keys reference Plane's existing models — imported, never modified.

### 7.5 Issue Type setup

Management command `apps/api/plane/prodoc/management/commands/setup_prodoc_issue_type.py`:

```
Usage: python manage.py setup_prodoc_issue_type --workspace=<id>

Creates a workspace-level Issue Type named "Prodoc Implementation Task" with custom properties:
  - prodoc_template_task_id (text)
  - prodoc_site_id (text — UUID of Prodoc Site)
  - prodoc_wave_id (text — UUID of Prodoc Wave)
  - prodoc_sla_hours (integer)

Idempotent: if the type already exists, updates properties; doesn't error.
```

This command runs once per workspace during onboarding, before any materialization.

### 7.6 API contract

**Templates:**

- `GET/POST /api/v1/prodoc/workspaces/{slug}/templates/`
- `GET/PUT/DELETE /api/v1/prodoc/workspaces/{slug}/templates/{id}/`

**Template sections:**

- `GET/POST /api/v1/prodoc/workspaces/{slug}/templates/{template_id}/sections/`
- `GET/PUT/DELETE /api/v1/prodoc/workspaces/{slug}/templates/{template_id}/sections/{id}/`

**Template tasks:**

- `GET/POST /api/v1/prodoc/workspaces/{slug}/templates/{template_id}/tasks/`
- `GET/PUT/DELETE .../tasks/{id}/`
- `POST .../tasks/{id}/dependencies/` — add dependency to another template task
- `DELETE .../tasks/{id}/dependencies/{dep_id}/`

**Migration requirements and third-party tools:**

- `GET/POST/PUT/DELETE .../templates/{template_id}/migration-requirements/`
- `GET/POST/PUT/DELETE .../templates/{template_id}/third-party-tools/`

When creating a migration requirement or third-party tool with rich content, the API can either accept a `page_id` of an already-created Plane Page or accept a `body` field which the API uses to create a new Page automatically and store the resulting `page_id`.

**Sites and Waves:**

- `GET/POST/PUT/DELETE /api/v1/prodoc/projects/{project_id}/sites/`
- `GET/POST/PUT/DELETE /api/v1/prodoc/projects/{project_id}/waves/`
- `POST /api/v1/prodoc/projects/{project_id}/waves/{wave_id}/sites/` — attach a site to a wave

**Materialization:**

- `POST /api/v1/prodoc/projects/{project_id}/materialize/`
  Body: `{"template_id": "<uuid>", "start_date": "2026-05-01", "dry_run": false}`
  Response (202): `{"job_id": "<uuid>", "status": "queued"}`
- `GET /api/v1/prodoc/projects/{project_id}/materialization-jobs/{job_id}/` — poll status.

All endpoints feature-flagged, workspace-isolated, permission-enforced.

### 7.7 Materialization algorithm

`prodoc_materialize_project(project_id, template_id, start_date)` Celery task:

```
1. Load project; verify workspace matches template workspace. 404 on mismatch.
2. Create ProjectMaterializationJob with status='running'.
3. Load template, sections, tasks, dependencies, in workspace context.
4. Load project's Sites and Waves.
5. For each Wave, create a Plane Module of the same name; store module_id on the Wave row and in job.modules_created.
6. Build the expansion plan:
   For each template task, compute the list of (wave, site) tuples it expands to:
     - both flags false: [(None, None)]
     - per_wave only: [(w, None) for w in waves]
     - per_site only: [(None, s) for s in sites]
     - both: [(w, s) for w in waves for s in w.sites]
7. Compute dates for each expansion:
   - effective_offset = task.offset_days + (wave.start_offset_days if wave else 0)
   - start = compute_target_date(project_start, effective_offset, ws_id)  [Ext 2]
   - target = compute_target_date(start, task.duration_days, ws_id)
8. Create Plane work items:
   For each (template_task, wave, site) expansion:
     - Build title (append site/wave name if expanded).
     - Issue.objects.create() with project, workspace, start_date, target_date,
       issue_type=<Prodoc Implementation Task>, custom properties populated.
     - If wave: attach issue to wave.plane_module.
     - Resolve role_key to user(s) per §7.8.
     - Append issue_id to job.work_items_created.
9. Wire dependencies:
   Build lookup: template_task_id -> [(wave, site, work_item_id), ...]
   For each TemplateTaskDependency (upstream, downstream):
     For each downstream expansion:
       Match upstream expansions per dependency_mode:
         - 'all': all upstream
         - 'same_site': only matching site
       For each matched upstream, create IssueRelation via ORM.
       Append relation_id to job.relations_created.
10. Set job.status='succeeded', save.
11. On any exception:
    - Rollback: soft-delete all work items, modules, and relations recorded in the job.
    - Set job.status='failed', error_log=str(exc).
    - Do not retry.

Dry run: stop after step 7, return the planned work items and dependencies as JSON, do not write to DB.
```

### 7.8 Role resolution (v1, before Extension 4)

For Extension 3 v1, template tasks specify one of Plane's three native roles. During materialization:

1. Query `ProjectMember` for users with that role on the project.
2. If exactly one, assign them.
3. If multiple, multi-assign all of them.
4. If zero, leave unassigned, log warning in `job.error_log` (non-fatal).

Extension 4 will replace this with friendly-label resolution. The materializer should call Extension 4's `resolve_role` first if it exists, with this native-role logic as fallback.

### 7.9 Tests required to ship

`apps/api/plane/prodoc/tests/test_materialization.py`:

1. Template CRUD: 3 sections, 10 tasks, fetch back, verify structure.
2. Template task dependencies CRUD.
3. Site and Wave CRUD; Wave creation also creates a Plane Module of the same name.
4. Materialize simple template (5 tasks, no expansion): 5 work items with correct dates.
5. Materialize per-site expansion: 5 tasks, 1 marked per_site, 3 sites → 4 + 3 = 7 work items.
6. Materialize per-wave expansion.
7. Materialize mixed expansion: cartesian product.
8. Dependencies mode='all': every downstream blocks every upstream.
9. Dependencies mode='same_site': only matching site pairs.
10. Dates respect holidays (uses Extension 2).
11. Wave offset applied: Wave 2 tasks further in the future than Wave 1.
12. Wave work items attached to corresponding Plane Module.
13. Issue Type set on every materialized work item.
14. Custom properties populated correctly.
15. Migration requirement with `body` parameter creates a Plane Page automatically and stores `page_id`.
16. Dry run returns plan, creates nothing.
17. Rollback on failure: all work items, modules, relations soft-deleted; job status='failed'.
18. Workspace isolation: cross-workspace materialize → 404.
19. Permission denied: non-admin project member → 403.
20. Feature flag off → 404.
21. Role resolution: 0 users (warning), 1 user (single assign), N users (multi assign).
22. Idempotency: second materialize while a prior job is running → 409.
23. Large template performance: 50 tasks × 4 sites × 2 waves completes in under 60 seconds.

### 7.10 Definition of done

- [ ] All models created with migrations.
- [ ] Full CRUD API for templates, sections, tasks, dependencies, migration requirements, third-party tools, sites, waves.
- [ ] `setup_prodoc_issue_type` management command and Issue Type creation logic.
- [ ] Materialization endpoint and Celery task with rollback.
- [ ] Wave-to-Module mirroring during materialization.
- [ ] Page creation/linking for migration requirements and third-party tools.
- [ ] All 23 tests pass.
- [ ] Integration test on staging: materialize a 20-task template against a real Plane project, verify in UI.
- [ ] Acceptance test: the MGM Phase-1 plan can be modeled as a Prodoc template and materialized into a fresh Plane project end-to-end. This is the real go/no-go gate for Extension 3.

---

## 8. Extension 4 — Custom Role Labels

### 8.1 Why it exists

Plane has three native roles: Admin, Member, Guest. Prodoc engagements involve many functional roles (Customer IT Lead, Customer Clinical Champion, Marketing Manager, Integration Partner Tech Lead, Prodoc Ops Manager, etc.) that map behind the scenes to one of those three permission levels but need friendly labels for clarity. Template tasks need to say "assigned to Customer IT Lead", not "assigned to Member".

### 8.2 Scope

**In scope:**

- `RoleLabel` model: per (user, project) pair, friendly label plus canonical internal role key.
- REST API for CRUD.
- `resolve_role(project_id, canonical_role_key)` helper returning the user list.
- Integration with Extension 3 materialization: template tasks reference `role_key`; resolution prefers labels over native roles.

**Out of scope:**

- Changing Plane's permission enforcement. Labels are display + routing only.
- Workspace-level role labels (project-scoped only in v1).
- Bulk import.

### 8.3 Scenarios

**Scenario 1: Assign a Customer IT Lead.** At project kickoff, ops calls `POST /api/v1/prodoc/projects/{id}/role-labels/` with `{"user_id": "...", "label": "Customer IT Lead", "canonical_role_key": "customer_it_lead"}`. Priya now has the label.

**Scenario 2: Template references a label.** Template task "Set up VPN" has `role_key: "customer_it_lead"`. Materialization calls `resolve_role`, finds Priya, assigns the work item.

**Scenario 3: Multiple users with the same label.** Two users on the project have "Customer IT Lead" (primary + backup). `resolve_role` returns both; materialization assigns both.

**Scenario 4: No user with the label.** Template says `clinical_champion` but no user has it. Materialization leaves unassigned and logs a warning (non-fatal).

**Scenario 5: Customer-specific friendly labels.** Different customers call the same functional role different things ("Marketing Manager" vs. "Growth Lead"). Both map to the same canonical key (`marketing_manager`), so template tasks targeting the canonical key pick up the right users regardless of label text.

### 8.4 Data model

```python
class RoleLabel(BaseModel):
    project = FK(Project)
    user = FK(User)
    label = CharField(max_length=100)  # customer-visible
    canonical_role_key = CharField(max_length=50)
    class Meta:
        unique_together = [('project', 'user', 'canonical_role_key')]
        indexes = [models.Index(fields=['project', 'canonical_role_key'])]
```

Canonical role keys live in `apps/api/plane/prodoc/constants.py`:

```python
CANONICAL_ROLE_KEYS = [
    'prodoc_super_admin', 'prodoc_ops_manager', 'prodoc_ops_member',
    'customer_admin', 'customer_it_lead', 'customer_clinical_champion', 'customer_user',
    'integration_partner_tech', 'integration_partner_pm',
    'marketing_manager', 'viewer',
]
```

### 8.5 API contract

- `GET/POST /api/v1/prodoc/projects/{project_id}/role-labels/`
- `GET/PUT/DELETE .../role-labels/{id}/`
- `GET /api/v1/prodoc/canonical-role-keys/` — read-only allowlist.

POST validation: `canonical_role_key` must be in the allowlist; user must be a project member; triple unique.

### 8.6 Business logic

`resolve_role(project_id, canonical_role_key)`:

```
1. Query RoleLabel filtered by project and canonical_role_key, deleted_at is null.
2. Return list of User objects.
```

Extension 3 materializer calls `resolve_role` first. If empty, falls back to native-role resolution from §7.8.

### 8.7 Tests

1. CRUD on RoleLabel.
2. `resolve_role` empty list when no labels.
3. `resolve_role` returns correct users.
4. `resolve_role` isolates by project.
5. POST invalid canonical key → 400.
6. POST non-project member → 400.
7. Duplicate triple → 409.
8. Materialization regression: a template task with `role_key: 'customer_it_lead'` correctly assigns the labeled user.
9. Feature flag off → 404.

### 8.8 Definition of done

- [ ] RoleLabel model + migration.
- [ ] REST API.
- [ ] `resolve_role` helper.
- [ ] Extension 3 materializer updated to call `resolve_role` first.
- [ ] All tests pass.

---

## 9. Extension 5 — Internal Comment Sidecar

### 9.1 Why it exists

Prodoc ops needs a channel for internal discussion that customers and partners do not see. Plane's comment thread is customer-visible. **Decision locked in:** rather than forking Plane's comment component to add per-comment visibility flags, we add a parallel comment stream — a "sidecar" — that lives entirely in Prodoc's models, has its own API, and renders in its own panel in the web UI. Plane's native comments remain the single public channel; anything ops writes there is visible to everyone on the project.

### 9.2 Scope

**In scope:**

- `ProdocComment` model per work item, authored by Prodoc ops users, visible only to internal Prodoc roles.
- REST API for create, list, edit own, soft-delete own (admin can delete any).
- New frontend panel under `web/components/prodoc/InternalThread.tsx`.
- Integration into the issue detail page via additive routing only — never editing upstream `.tsx`.
- Permission enforcement via Extension 4 canonical roles, with workspace-admin fallback if Extension 4 isn't deployed yet.

**Out of scope:**

- Mentions, reactions, attachments, rich formatting. v1 is plain text.
- Real-time updates. v1 polls or refreshes on action.
- Promoting an internal comment to public, or vice versa. Copy-paste for now.
- Unified timeline view merging public + internal. Future revisit.

### 9.3 Scenarios

**Scenario 1: Ops records an internal note.** Task is "Confirm VPN access with Hospital 3 IT". Ops notes that Hospital 3's IT lead has been unresponsive for a week and they're considering escalating. Visible only to other Prodoc ops users on subsequent visits.

**Scenario 2: Customer opens the same task.** Customer is a `customer_user`. Sees Plane's normal comment thread but no internal panel. The InternalThread component does not render — and the API request that would list internal comments is never made.

**Scenario 3: Ops edits own note.** Updated_at changes; other ops users see the edit on refresh.

**Scenario 4: Ops deletes own note.** Soft-delete; row stays with `deleted_at` set; disappears from UI and API list.

**Scenario 5: Author-only edit/delete.** User A wrote a note. User B tries to edit via API → 403. Prodoc admins can delete any note.

**Scenario 6: Workspace isolation.** Ops in WS A reads internal notes from issue in WS B → 404 (not 403, to avoid leaking existence).

**Scenario 7: Feature flag off.** API returns 404; frontend panel does not render (feature flag fetched via a small `/api/v1/prodoc/instance/` endpoint).

### 9.4 Data model

```python
class ProdocComment(BaseModel):
    issue = FK(Issue)
    workspace = FK(Workspace)  # denormalized for fast isolation filtering
    project = FK(Project)
    author = FK(User)
    body = TextField()

    class Meta:
        indexes = [
            models.Index(fields=['issue', 'deleted_at']),
            models.Index(fields=['workspace', 'deleted_at']),
        ]
```

### 9.5 API contract

- `GET /api/v1/prodoc/work-items/{issue_id}/internal-comments/` — list non-deleted.
- `POST .../internal-comments/` — create. Body: `{"body": "text"}`.
- `GET/PUT/DELETE .../internal-comments/{id}/`
- `GET /api/v1/prodoc/instance/` — returns `{"prodoc_features_enabled": true|false}` for frontend gating.

Permissions: all methods require the user to have one of `prodoc_super_admin`, `prodoc_ops_manager`, or `prodoc_ops_member` via Extension 4, OR to be a `WorkspaceAdmin` natively. PUT and DELETE additionally require author match unless admin.

### 9.6 Frontend

New components only, all under `web/components/prodoc/`:

- `InternalThread.tsx` — fetches comments, renders the list, provides text area + post button, edit/delete on own comments.
- `IssueDetailExtensions.tsx` — wrapper that mounts on issue detail pages via a Prodoc-only sidebar panel or tab. **Implementation strategy decided during build**: either a dedicated Prodoc sidebar that appears on every issue page, or a separate Prodoc-only page reached via a sidebar link from the issue detail.

If the only way to mount the panel turns out to require editing upstream Plane components, **stop and ask in chat**. Fallback: render the panel on a separate Prodoc-only page reached via a sidebar link.

The panel does not render if:

- The current user does not have an internal Prodoc role, or
- The instance feature flag is false.

### 9.7 Tests

Backend in `apps/api/plane/prodoc/tests/test_internal_comments.py`:

1. Create as ops, visible in list.
2. List returns only non-deleted.
3. Edit own → success.
4. Edit another's → 403.
5. Delete own → soft-deleted.
6. Admin deletes another's → success.
7. Customer user lists → 404.
8. Customer user creates → 404.
9. Workspace isolation → 404.
10. Feature flag off → 404.

Frontend tests if Plane's test setup supports them: panel renders for ops, doesn't render for customer, handles empty + error states.

### 9.8 Definition of done

- [ ] ProdocComment model + migration.
- [ ] REST API.
- [ ] `/api/v1/prodoc/instance/` endpoint.
- [ ] Frontend panel + integration on issue detail page (additive only).
- [ ] All backend tests pass.
- [ ] Manual test on staging: ops sees panel, customer does not, comment round-trip works.

---

## 10. Prerequisite — Templates investigation

Before starting Extension 3, run this prompt in Claude Code in the fork. The result determines whether Extension 3 builds standalone Prodoc templates (current plan) or extends Plane's native templates.

> Read `CLAUDE.md` at the repo root first. Then investigate this question and produce a written report — do not write any code.
>
> **Question:** Does this Plane fork have a project templates system, and if so, what does it support?
>
> **What to look for:** Search the codebase for any Django app, model, viewset, or directory named `template`, `templates`, `project_template`, `work_item_template`, or similar. Check `apps/api/plane/db/models/`, `apps/api/plane/app/views/`, `apps/api/plane/api/views/`, and other app directories.
>
> **If templates exist, document:** models and fields; what gets templated (states, labels, work item types, custom properties, default issues, dependencies, dates/offsets, assignees); API endpoints in `app/` vs `api/`; instantiation flow including whether dependencies are preserved on clone; versioning and editability after use.
>
> **If `plane-compose` or YAML-based project-as-code exists:** document where and what it supports.
>
> **If no templates system exists:** say so explicitly. Note the Plane version this fork is based on (check `apps/api/plane/__init__.py` or similar).
>
> **Answer these three questions at the end:**
>
> a. Can a Prodoc ops user, today, define a reusable template that captures ordered tasks, offset-based dates, dependency edges, role assignments, and section grouping — and instantiate it as a new project with all of that intact? (Yes / Partial / No, with detail.)
>
> b. If templates exist, do they support per-site or per-wave expansion of tasks during instantiation? (Almost certainly No, but confirm.)
>
> c. If templates exist and we wanted to extend them with Prodoc-specific fields, would the cleanest approach be (i) extend existing models via FK from a new Prodoc app, (ii) duplicate the template system in `apps/api/plane/prodoc/`, or (iii) something else? Recommend one with reasoning.
>
> Output: a markdown report at `prodoc-research/templates-investigation.md` at the repo root. Do not modify any other files.

When the report comes back, paste it here. I'll either confirm Extension 3 stays as written (Option A — standalone) or we'll redesign §7 to extend Plane's templates (Option B).

---

## 11. Global concerns across all extensions

### 11.1 Error handling

Match Plane's existing API error response shape. Grep `apps/api/plane/api/views/` for existing error handlers.

### 11.2 Logging

Use Plane's existing logger. INFO for state transitions, WARNING for recoverable issues, ERROR for unexpected exceptions.

### 11.3 Observability

Reuse whatever Plane already provides. Do not add a new observability stack.

### 11.4 Secrets

No new secrets. All extensions use Plane's existing API key system and database connection.

### 11.5 Migrations

All reversible. Never drop or rename columns on upstream tables.

### 11.6 Code review self-check (run before opening any PR)

- [ ] Does this PR touch any file outside `apps/api/plane/prodoc/` or `web/components/prodoc/`? If yes, is the touch one of the three permitted upstream edits?
- [ ] Does every new viewset subclass a Plane permission class?
- [ ] Does every new queryset filter by `workspace_id` on line 1?
- [ ] Does every new model inherit `BaseModel` and carry a workspace/project FK?
- [ ] Is every endpoint gated on `PRODOC_FEATURES_ENABLED`?
- [ ] Are all required tests from the extension's definition of done present and passing?
- [ ] Was any frontend `.tsx` file outside `web/components/prodoc/` modified?

---

## 12. Order of operations

1. **Extension 1** (Public Dependency API) — 1–2 sessions. Unblocks everything.
2. **Extension 2** (Scheduler and Cascade) — 2–3 sessions. Self-contained.
3. **Run the templates investigation prompt from §10.** Confirms Extension 3 design.
4. **Extension 3** (Templates, Sites, Waves, Materialization) — 4–6 sessions. Depends on 1, 2, and the investigation.
5. **Extension 4** (Custom Role Labels) — 1 session. Best done right after Extension 3 so materialization picks it up.
6. **Extension 5** (Internal Comment Sidecar) — 2–3 sessions including frontend. Can run in parallel with Extension 4.

After all five, the MGM Phase-1 plan should be modelable as a Prodoc template and materializable into a new Plane project in one API call, with customer/partner visibility, internal ops notes, and business-day-aware date cascade all working.

---

## 13. What Claude Code should do first in each new session

Before writing any code, every session should:

1. Read `CLAUDE.md` at the repo root.
2. Read the relevant extension section in this file.
3. Read any existing Prodoc code in `apps/api/plane/prodoc/` to understand established patterns.
4. Grep upstream Plane for the specific models, viewsets, or functions being referenced.
5. Only then start writing.

If any rule in `CLAUDE.md` conflicts with a task in this file, `CLAUDE.md` wins. Surface the conflict in chat rather than silently resolving it.

---

_Document owner: Raghu (Prodoc AI). Companion to `CLAUDE.md` in the Plane fork. Update as extensions complete or scope changes._
