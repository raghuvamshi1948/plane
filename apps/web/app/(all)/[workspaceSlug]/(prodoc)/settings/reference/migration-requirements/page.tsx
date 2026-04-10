import { observer } from "mobx-react";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { MigrationRequirementsList } from "@/components/prodoc/reference/migration-requirements-list";
import { useWorkspace } from "@/hooks/store/use-workspace";
import type { Route } from "./+types/page";

function MigrationRequirementsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const { currentWorkspace } = useWorkspace();
  const pageTitle = currentWorkspace?.name ? `${currentWorkspace.name} - Migration Requirements` : undefined;

  return (
    <SettingsContentWrapper>
      <PageHead title={pageTitle} />
      <MigrationRequirementsList workspaceSlug={workspaceSlug} />
    </SettingsContentWrapper>
  );
}

export default observer(MigrationRequirementsPage);
