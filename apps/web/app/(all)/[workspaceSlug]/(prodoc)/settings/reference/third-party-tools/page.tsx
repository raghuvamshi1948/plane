import { observer } from "mobx-react";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { ThirdPartyToolsList } from "@/components/prodoc/reference/third-party-tools-list";
import { useWorkspace } from "@/hooks/store/use-workspace";
import type { Route } from "./+types/page";

function ThirdPartyToolsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const { currentWorkspace } = useWorkspace();
  const pageTitle = currentWorkspace?.name ? `${currentWorkspace.name} - Third-Party Tools` : undefined;

  return (
    <SettingsContentWrapper>
      <PageHead title={pageTitle} />
      <ThirdPartyToolsList workspaceSlug={workspaceSlug} />
    </SettingsContentWrapper>
  );
}

export default observer(ThirdPartyToolsPage);
