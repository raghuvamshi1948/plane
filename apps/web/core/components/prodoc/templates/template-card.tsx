import { useNavigate } from "react-router";
import { FileText } from "lucide-react";
import type { ProdocTemplate } from "@/components/prodoc/hooks/use-prodoc-api";
import { TemplateStatusBadge } from "./template-status-badge";

type Props = {
  template: ProdocTemplate;
  workspaceSlug: string;
};

export function TemplateCard({ template, workspaceSlug }: Props) {
  const navigate = useNavigate();

  const taskCount = (template.rendered_preview as { task_count?: number })?.task_count ?? 0;
  const waveCount = (template.rendered_preview as { wave_count?: number })?.wave_count ?? 0;
  const estimatedDays = (template.rendered_preview as { estimated_duration_days?: number })?.estimated_duration_days;

  return (
    <button
      type="button"
      className="flex w-full flex-col gap-3 rounded-lg border border-subtle bg-surface-1 p-4 text-left transition-colors hover:bg-surface-2"
      onClick={() => navigate(`/${workspaceSlug}/settings/prodoc/templates/${template.id}/edit`)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          {template.icon ? (
            <span className="text-18">{template.icon}</span>
          ) : (
            <FileText className="size-5 text-secondary" />
          )}
          <h3 className="truncate text-14 font-medium text-primary">{template.name}</h3>
        </div>
        <TemplateStatusBadge status={template.status} />
      </div>
      {template.description && <p className="line-clamp-2 text-13 text-secondary">{template.description}</p>}
      <div className="flex items-center gap-3 text-12 text-tertiary">
        <span>
          {taskCount} {taskCount === 1 ? "task" : "tasks"}
        </span>
        <span>
          {waveCount} {waveCount === 1 ? "wave" : "waves"}
        </span>
        {estimatedDays != null && <span>{estimatedDays} business days</span>}
        <span className="ml-auto">v{template.version}</span>
      </div>
    </button>
  );
}
