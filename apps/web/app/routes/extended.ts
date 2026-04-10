/**
 * Extended routes for Prodoc frontend features.
 *
 * These are deep-merged with core routes by mergeRoutes() so Prodoc pages
 * inherit the existing workspace, settings, and project layouts.
 */

import { layout, route } from "@react-router/dev/routes";
import type { RouteConfigEntry } from "@react-router/dev/routes";

export const extendedRoutes: RouteConfigEntry[] = [
  // All routes nest inside the authenticated app layout → workspace layout
  layout("./(all)/layout.tsx", [
    layout("./(all)/[workspaceSlug]/layout.tsx", [
      // ---- Workspace settings: Prodoc templates & reference data ----
      layout("./(all)/[workspaceSlug]/(settings)/layout.tsx", [
        layout("./(all)/[workspaceSlug]/(settings)/settings/(workspace)/layout.tsx", [
          route(
            ":workspaceSlug/settings/prodoc/templates",
            "./(all)/[workspaceSlug]/(prodoc)/settings/templates/page.tsx"
          ),
          route(
            ":workspaceSlug/settings/prodoc/templates/new",
            "./(all)/[workspaceSlug]/(prodoc)/settings/templates/new/page.tsx"
          ),
          route(
            ":workspaceSlug/settings/prodoc/templates/:templateId/edit",
            "./(all)/[workspaceSlug]/(prodoc)/settings/templates/[templateId]/edit/page.tsx"
          ),
          route(
            ":workspaceSlug/settings/prodoc/templates/:templateId/versions/:compareId",
            "./(all)/[workspaceSlug]/(prodoc)/settings/templates/[templateId]/versions/[compareId]/page.tsx"
          ),
          route(
            ":workspaceSlug/settings/prodoc/reference/migration-requirements",
            "./(all)/[workspaceSlug]/(prodoc)/settings/reference/migration-requirements/page.tsx"
          ),
          route(
            ":workspaceSlug/settings/prodoc/reference/third-party-tools",
            "./(all)/[workspaceSlug]/(prodoc)/settings/reference/third-party-tools/page.tsx"
          ),
        ]),
      ]),

      // ---- Project-level: Prodoc sites & waves ----
      layout("./(all)/[workspaceSlug]/(projects)/layout.tsx", [
        layout("./(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/layout.tsx", [
          route(
            ":workspaceSlug/projects/:projectId/prodoc/sites",
            "./(all)/[workspaceSlug]/(prodoc)/projects/[projectId]/sites/page.tsx"
          ),
          route(
            ":workspaceSlug/projects/:projectId/prodoc/waves",
            "./(all)/[workspaceSlug]/(prodoc)/projects/[projectId]/waves/page.tsx"
          ),
        ]),
      ]),
    ]),
  ]),
];
