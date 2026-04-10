import { useState, useCallback } from "react";
import { observer } from "mobx-react";
import useSWR, { mutate } from "swr";
import { Wand2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { ProdocFeatureGate } from "@/components/prodoc/components/prodoc-feature-gate";
import { useProdocApi } from "@/components/prodoc/hooks/use-prodoc-api";
import type { ProdocMaterializationJob } from "@/components/prodoc/hooks/use-prodoc-api";
import { TemplateSelectionModal } from "./template-selection-modal";
import { DryRunModal } from "@/components/prodoc/templates/dry-run-modal";
import { MaterializationStatusBanner } from "./materialization-status-banner";

type Props = {
  workspaceSlug: string;
  projectId: string;
  projectName: string;
};

function ApplyTemplateButtonInner({ workspaceSlug, projectId, projectName }: Props) {
  const api = useProdocApi();
  const [showSelection, setShowSelection] = useState(false);
  const [showDryRun, setShowDryRun] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [selectedTemplateName, setSelectedTemplateName] = useState<string>("");
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const { data: settings } = useSWR(`PRODOC_PROJECT_SETTINGS_${projectId}`, () =>
    api.getProjectSettings(workspaceSlug, projectId).catch(() => null)
  );

  // Hide if project already has a template materialized
  const alreadyMaterialized = settings?.prodoc_template_source != null;
  if (alreadyMaterialized && !activeJobId) return null;

  const handleSelectTemplate = (templateId: string, templateName: string) => {
    setSelectedTemplateId(templateId);
    setSelectedTemplateName(templateName);
    setShowSelection(false);
    setShowDryRun(true);
  };

  const handleMaterialize = useCallback(async () => {
    if (!selectedTemplateId) return;
    setShowDryRun(false);
    try {
      const result = await api.materialize(workspaceSlug, projectId, {
        template_id: selectedTemplateId,
      });
      const job = result as ProdocMaterializationJob;
      setActiveJobId(job.id);
    } catch (err) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Materialization failed",
        message: err instanceof Error ? err.message : "Unknown error",
      });
    }
  }, [api, workspaceSlug, projectId, selectedTemplateId]);

  const handleJobComplete = useCallback(() => {
    setActiveJobId(null);
    mutate(`PRODOC_PROJECT_SETTINGS_${projectId}`);
  }, [projectId]);

  return (
    <>
      {activeJobId ? (
        <MaterializationStatusBanner
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          jobId={activeJobId}
          onComplete={handleJobComplete}
          onRetry={() => {
            setActiveJobId(null);
            setShowSelection(true);
          }}
        />
      ) : (
        <Button variant="primary" size="lg" onClick={() => setShowSelection(true)}>
          <Wand2 className="size-4" />
          Apply template
        </Button>
      )}

      <TemplateSelectionModal
        isOpen={showSelection}
        onClose={() => setShowSelection(false)}
        onSelect={handleSelectTemplate}
        workspaceSlug={workspaceSlug}
      />

      {selectedTemplateId && (
        <DryRunModal
          isOpen={showDryRun}
          onClose={() => setShowDryRun(false)}
          onMaterialize={handleMaterialize}
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          templateId={selectedTemplateId}
          templateName={selectedTemplateName}
          projectName={projectName}
        />
      )}
    </>
  );
}

export const ApplyTemplateButton = observer(function ApplyTemplateButton(props: Props) {
  return (
    <ProdocFeatureGate>
      <ApplyTemplateButtonInner {...props} />
    </ProdocFeatureGate>
  );
});
