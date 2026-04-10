import { observer } from "mobx-react";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { ProdocTemplateList } from "@/components/prodoc/templates/template-list";
import { useWorkspace } from "@/hooks/store/use-workspace";
import type { Route } from "./+types/page";

function ProdocTemplatesPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const { currentWorkspace } = useWorkspace();
  const pageTitle = currentWorkspace?.name ? `${currentWorkspace.name} - Prodoc Templates` : undefined;

  return (
    <SettingsContentWrapper>
      <PageHead title={pageTitle} />
      <ProdocTemplateList workspaceSlug={workspaceSlug} />
    </SettingsContentWrapper>
  );
}

export default observer(ProdocTemplatesPage);
