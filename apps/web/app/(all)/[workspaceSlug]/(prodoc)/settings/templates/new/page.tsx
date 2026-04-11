import { observer } from "mobx-react";
import { useSearchParams } from "react-router";
import { PageHead } from "@/components/core/page-title";
import { TemplateEditor } from "@/components/prodoc/templates/template-editor";
import { useWorkspace } from "@/hooks/store/use-workspace";
import type { Route } from "./+types/page";

function NewTemplatePage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const [searchParams] = useSearchParams();
  const parentTemplateId = searchParams.get("parent") ?? undefined;
  const { currentWorkspace } = useWorkspace();
  const pageTitle = currentWorkspace?.name ? `${currentWorkspace.name} - New Template` : undefined;

  return (
    <>
      <PageHead title={pageTitle} />
      <TemplateEditor workspaceSlug={workspaceSlug} parentTemplateId={parentTemplateId} />
    </>
  );
}

export default observer(NewTemplatePage);
