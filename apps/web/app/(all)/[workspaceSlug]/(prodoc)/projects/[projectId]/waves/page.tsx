import { observer } from "mobx-react";
import { PageHead } from "@/components/core/page-title";
import { WavesManager } from "@/components/prodoc/projects/waves-manager";
import { useProject } from "@/hooks/store/use-project";
import type { Route } from "./+types/page";

function ProjectWavesPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { getProjectById } = useProject();
  const project = getProjectById(projectId);
  const pageTitle = project?.name ? `${project.name} - Waves` : undefined;

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto px-9 py-8">
      <PageHead title={pageTitle} />
      <WavesManager workspaceSlug={workspaceSlug} projectId={projectId} />
    </div>
  );
}

export default observer(ProjectWavesPage);
