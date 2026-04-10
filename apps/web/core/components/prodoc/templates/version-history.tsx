import { useNavigate } from "react-router";
import useSWR from "swr";
import { GitCompare } from "lucide-react";
import { Button } from "@plane/propel/button";
import { CircularSpinner } from "@plane/ui";
import { useProdocApi } from "@/components/prodoc/hooks/use-prodoc-api";
import { TemplateStatusBadge } from "./template-status-badge";

type Props = {
  workspaceSlug: string;
  currentTemplateId: string;
};

export function VersionHistory({ workspaceSlug, currentTemplateId }: Props) {
  const api = useProdocApi();
  const navigate = useNavigate();

  const { data: templates, isLoading } = useSWR(`PRODOC_TEMPLATES_${workspaceSlug}`, () =>
    api.listTemplates(workspaceSlug)
  );

  if (isLoading) return <CircularSpinner />;

  // Find all versions of the same template lineage
  const allVersions = (templates ?? []).filter(
    (t) => t.id === currentTemplateId || t.parent_template === currentTemplateId
  );

  if (allVersions.length <= 1) {
    return <p className="text-13 text-secondary">No other versions to compare.</p>;
  }

  return (
    <div className="space-y-2">
      {allVersions
        .filter((t) => t.id !== currentTemplateId)
        .map((t) => (
          <div
            key={t.id}
            className="flex items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3"
          >
            <div className="flex items-center gap-2">
              <span className="text-14 font-medium">v{t.version}</span>
              <TemplateStatusBadge status={t.status} />
              <span className="text-13 text-secondary">{t.name}</span>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() =>
                navigate(`/${workspaceSlug}/settings/prodoc/templates/${currentTemplateId}/versions/${t.id}`)
              }
            >
              <GitCompare className="size-3.5" />
              Compare
            </Button>
          </div>
        ))}
    </div>
  );
}
