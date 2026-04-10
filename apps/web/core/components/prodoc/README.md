# Prodoc Frontend — Convention Guide

All Prodoc-specific frontend code lives in this directory (`apps/web/core/components/prodoc/`), importable as `@/components/prodoc/`. This is the frontend analog of the backend's `apps/api/plane/prodoc/`.

## Routing

Plane uses **React Router v7** with declarative route configuration in `apps/web/app/routes/`.

- **Core routes**: `apps/web/app/routes/core.ts` — Plane's upstream routes. Do not edit.
- **Extended routes**: `apps/web/app/routes/extended.ts` — Our extension point. The `mergeRoutes()` helper deep-merges extended routes into core routes by matching layout file paths.

Prodoc routes are declared in `extended.ts` and use the existing workspace layouts (`(all)`, `(settings)`, `(projects)`) so we inherit auth, sidebar, and breadcrumbs for free.

Route page files (thin wrappers) live in `apps/web/app/(all)/[workspaceSlug]/(prodoc)/`.

### URL patterns

| Page              | URL                                                      | Route page file                                                  |
| ----------------- | -------------------------------------------------------- | ---------------------------------------------------------------- |
| Template list     | `/:ws/settings/prodoc/templates`                         | `(prodoc)/settings/templates/page.tsx`                           |
| New template      | `/:ws/settings/prodoc/templates/new`                     | `(prodoc)/settings/templates/new/page.tsx`                       |
| Edit template     | `/:ws/settings/prodoc/templates/:id/edit`                | `(prodoc)/settings/templates/[id]/edit/page.tsx`                 |
| Version compare   | `/:ws/settings/prodoc/templates/:id/versions/:compareId` | `(prodoc)/settings/templates/[id]/versions/[compareId]/page.tsx` |
| Migration reqs    | `/:ws/settings/prodoc/reference/migration-requirements`  | `(prodoc)/settings/reference/migration-requirements/page.tsx`    |
| Third-party tools | `/:ws/settings/prodoc/reference/third-party-tools`       | `(prodoc)/settings/reference/third-party-tools/page.tsx`         |
| Project sites     | `/:ws/projects/:pid/prodoc/sites`                        | `(prodoc)/projects/[projectId]/sites/page.tsx`                   |
| Project waves     | `/:ws/projects/:pid/prodoc/waves`                        | `(prodoc)/projects/[projectId]/waves/page.tsx`                   |

## Form library

**react-hook-form** v7 — matches Plane's existing pattern.

```tsx
import { Controller, useForm } from "react-hook-form";
const {
  control,
  handleSubmit,
  formState: { errors },
} = useForm<MyType>({ defaultValues });
```

## Data fetching

**SWR** — matches Plane's existing pattern.

```tsx
import useSWR from "swr";
const { data, isLoading, error } = useSWR(key, fetcher);
```

## API client

All backend calls go through `useProdocApi()` hook (`@/components/prodoc/hooks/use-prodoc-api`). The hook returns a typed service instance wrapping Plane's `APIService` base class with all Extension 3 endpoints.

## Feature gating

Every Prodoc component must be wrapped in `<ProdocFeatureGate>` or check `useProdocFeatureFlag()` directly. The flag fetches from `/api/v1/prodoc/feature-flag/` and returns `enabled: false` on any error (fail closed).

## UI components

Use `@plane/ui` and `@plane/propel` packages:

- Buttons: `import { Button } from "@plane/propel/button"`
- Forms: `import { Input, TextArea } from "@plane/ui"`
- Modals: `import { ModalCore, AlertModalCore, EModalWidth } from "@plane/ui"`
- Collapsible: `import { Collapsible } from "@plane/ui"`
- Toast: `import { TOAST_TYPE, setToast } from "@plane/propel/toast"`

## Testing

Plane's frontend has no existing test infrastructure (no Jest, Vitest, or Playwright configs). Frontend tests for Prodoc are documented as TODOs in the PR description. When Plane adds test tooling upstream, Prodoc tests should be added retroactively.

## Permitted upstream edits

Only two upstream files may be edited, each limited to 3 lines:

1. `apps/web/app/routes/extended.ts` — Prodoc route declarations
2. `apps/web/app/(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/issues/(list)/page.tsx` — `<ApplyTemplateButton />` mount

The CI guard script (`apps/web/scripts/check-prodoc-diff.sh`) enforces a 5-line ceiling on all other upstream files.
