/**
 * Prodoc Templates UI — End-to-end smoke test
 *
 * STATUS: PLACEHOLDER — Plane does not ship any frontend test infrastructure
 * (no Playwright, Cypress, Jest, or Vitest config exists in the web app).
 * This file documents the intended test scenario so it can be wired up once
 * an e2e framework is adopted.
 *
 * To run when Playwright is available:
 *   npx playwright test apps/web/tests/e2e/prodoc-templates.spec.ts
 *
 * Prerequisites:
 *   - A running Plane instance with PRODOC_FEATURES_ENABLED = True
 *   - An authenticated workspace with at least one project
 *   - The Prodoc backend (Extension 3) deployed and migrated
 */

// import { test, expect } from "@playwright/test";

// Exported constant to satisfy the no-empty-file lint rule while the test remains a placeholder.
export const PRODOC_TEMPLATES_E2E_STATUS = "placeholder" as const;

/*
test.describe("Prodoc template creation and materialization", () => {
  // ----------------------------------------------------------------
  // Step 1: Reference data setup
  // ----------------------------------------------------------------
  test("create reference data items", async ({ page }) => {
    // Navigate to workspace settings → reference data → migration requirements
    // Click "Add requirement" → fill name "EMR Data Migration" → save
    // Verify the item appears in the list

    // Navigate to workspace settings → reference data → third-party tools
    // Click "Add tool" → fill name "Epic Systems" → save
    // Verify the item appears in the list
  });

  // ----------------------------------------------------------------
  // Step 2: Template creation
  // ----------------------------------------------------------------
  test("create a new Prodoc template with 2 waves and 5 tasks", async ({ page }) => {
    // Navigate to workspace settings → templates → click "New template"
    // Fill metadata: name "Onboarding Template", description "Smoke test template"
    //
    // Add 2 waves:
    //   Wave 1: name "Discovery", slug "discovery", sequence 1
    //   Wave 2: name "Implementation", slug "implementation", sequence 2
    //
    // Add 5 tasks:
    //   Task 1: "Kick-off meeting", wave discovery, duration 1, offset 0
    //   Task 2: "Data assessment", wave discovery, duration 3, offset 1
    //   Task 3: "System config", wave implementation, duration 5, offset 5
    //   Task 4: "Data migration", wave implementation, duration 3, offset 10, linked to "EMR Data Migration" requirement
    //   Task 5: "Go-live prep", wave implementation, duration 2, offset 13, linked to "Epic Systems" tool
    //
    // Add 2 dependencies:
    //   "Data assessment" blocks "System config"
    //   "System config" blocks "Data migration"
    //
    // Click "Save draft"
    // Verify redirect to template list
    // Verify the template appears with "draft" badge
  });

  // ----------------------------------------------------------------
  // Step 3: Publish and lock
  // ----------------------------------------------------------------
  test("edit draft → publish and lock", async ({ page }) => {
    // Navigate to template list → click on "Onboarding Template"
    // Click "Publish & lock" button
    // Confirm in the AlertModal
    // Verify status badge changes from "draft" to "locked"
  });

  // ----------------------------------------------------------------
  // Step 4: Apply template to a project
  // ----------------------------------------------------------------
  test("apply template to a new project", async ({ page }) => {
    // Navigate to an empty project → issues page
    // Click "Apply template" button
    // In the TemplateSelectionModal, select "Onboarding Template"
    // DryRunModal opens automatically:
    //   Verify it shows 2 collapsible waves
    //   Verify 5 tasks are listed with computed absolute dates
    //   Verify dependency summary shows 2 dependency edges
    //   Verify no errors are displayed
    // Click "Materialize this template"
    // Wait for MaterializationStatusBanner to show "complete"
    // Verify the project now has 5 issues
    // Verify dependency edges exist between the correct issues
  });

  // ----------------------------------------------------------------
  // Step 5: Sites management
  // ----------------------------------------------------------------
  test("add a site to the project", async ({ page }) => {
    // Navigate to the project's Prodoc Sites page
    // Click "Add site"
    // Fill name "Main Hospital", address "123 Health St", go-live date
    // Click "Create"
    // Verify the site appears in the list with correct details
  });

  // ----------------------------------------------------------------
  // Step 6: Waves view
  // ----------------------------------------------------------------
  test("verify waves are listed with module links", async ({ page }) => {
    // Navigate to the project's Prodoc Waves page
    // Verify 2 waves are listed: "Discovery" and "Implementation"
    // Verify each wave shows "View module →" link
    // Click a wave → verify navigation to the Plane Module page
  });
});
*/
