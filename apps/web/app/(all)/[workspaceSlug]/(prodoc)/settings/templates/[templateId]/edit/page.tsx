import { observer } from "mobx-react";
import { PageHead } from "@/components/core/page-title";
import { TemplateEditor } from "@/components/prodoc/templates/template-editor";
import { useWorkspace } from "@/hooks/store/use-workspace";
import type { Route } from "./+types/page";

function EditTemplatePage({ params }: Route.ComponentProps) {
  const { workspaceSlug, templateId } = params;
  const { currentWorkspace } = useWorkspace();
  const pageTitle = currentWorkspace?.name ? `${currentWorkspace.name} - Edit Template` : undefined;

  return (
    <>
      <PageHead title={pageTitle} />
      <TemplateEditor workspaceSlug={workspaceSlug} templateId={templateId} />
    </>
  );
}

export default observer(EditTemplatePage);
