import { observer } from "mobx-react";
import { useNavigate } from "react-router";
import { ChevronLeft } from "lucide-react";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { VersionDiff } from "@/components/prodoc/templates/version-diff";
import { useWorkspace } from "@/hooks/store/use-workspace";
import type { Route } from "./+types/page";

function VersionComparePage({ params }: Route.ComponentProps) {
  const { workspaceSlug, templateId, compareId } = params;
  const { currentWorkspace } = useWorkspace();
  const navigate = useNavigate();
  const pageTitle = currentWorkspace?.name ? `${currentWorkspace.name} - Version Compare` : undefined;

  return (
    <SettingsContentWrapper>
      <PageHead title={pageTitle} />
      <div className="space-y-4">
        <button
          type="button"
          className="flex items-center gap-1 rounded text-13 text-secondary hover:text-primary"
          onClick={() => navigate(`/${workspaceSlug}/settings/prodoc/templates/${templateId}/edit`)}
        >
          <ChevronLeft className="size-4" />
          Back to template
        </button>
        <VersionDiff workspaceSlug={workspaceSlug} templateId={templateId} compareId={compareId} />
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(VersionComparePage);
