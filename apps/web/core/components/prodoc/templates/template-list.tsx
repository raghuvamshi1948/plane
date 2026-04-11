import { observer } from "mobx-react";
import { useNavigate } from "react-router";
import useSWR from "swr";
import { Plus } from "lucide-react";
import { Button } from "@plane/propel/button";
import { Spinner } from "@plane/ui";
import { ProdocFeatureGate } from "@/components/prodoc/components/prodoc-feature-gate";
import { useProdocApi } from "@/components/prodoc/hooks/use-prodoc-api";
import { TemplateCard } from "./template-card";

type Props = {
  workspaceSlug: string;
};

function TemplateListInner({ workspaceSlug }: Props) {
  const navigate = useNavigate();
  const api = useProdocApi();

  const { data: templates, isLoading } = useSWR(workspaceSlug ? `PRODOC_TEMPLATES_${workspaceSlug}` : null, () =>
    api.listTemplates(workspaceSlug)
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="flex items-center justify-between pb-3.5">
        <div>
          <h4 className="text-h3-medium">Prodoc Onboarding Templates</h4>
          <p className="mt-1 text-13 text-secondary">Pre-configured onboarding playbooks for healthcare providers</p>
        </div>
        <Button variant="primary" size="lg" onClick={() => navigate(`/${workspaceSlug}/settings/prodoc/templates/new`)}>
          <Plus className="size-4" />
          Create template
        </Button>
      </div>

      {!templates || templates.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-subtle py-20">
          <p className="text-14 text-secondary">No templates yet.</p>
          <p className="mt-1 text-13 text-tertiary">Create your first onboarding playbook.</p>
          <Button
            variant="primary"
            size="lg"
            className="mt-4"
            onClick={() => navigate(`/${workspaceSlug}/settings/prodoc/templates/new`)}
          >
            <Plus className="size-4" />
            Create template
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => (
            <TemplateCard key={template.id} template={template} workspaceSlug={workspaceSlug} />
          ))}
        </div>
      )}
    </div>
  );
}

export const ProdocTemplateList = observer(function ProdocTemplateList({ workspaceSlug }: Props) {
  return (
    <ProdocFeatureGate>
      <TemplateListInner workspaceSlug={workspaceSlug} />
    </ProdocFeatureGate>
  );
});
