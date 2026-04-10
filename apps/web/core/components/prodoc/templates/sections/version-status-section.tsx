import { useNavigate } from "react-router";
import { Button } from "@plane/propel/button";
import { TemplateStatusBadge } from "../template-status-badge";

type Props = {
  version: number;
  status: "draft" | "active" | "locked";
  templateId: string;
  workspaceSlug: string;
};

export function VersionStatusSection({ version, status, templateId, workspaceSlug }: Props) {
  const navigate = useNavigate();

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-13 text-secondary">Version {version}</span>
        <TemplateStatusBadge status={status} />
      </div>
      {status === "locked" && (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate(`/${workspaceSlug}/settings/prodoc/templates/new?parent=${templateId}`)}
        >
          Create new version
        </Button>
      )}
    </div>
  );
}
