import { cn } from "@plane/utils";

type Props = {
  status: "draft" | "active" | "locked";
  className?: string;
};

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-neutral-component-surface-dark text-secondary",
  active: "bg-accent-primary/10 text-accent-primary",
  locked: "bg-green-500/10 text-green-600",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  active: "Active",
  locked: "Locked",
};

export function TemplateStatusBadge({ status, className }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-11 font-medium",
        STATUS_STYLES[status],
        className
      )}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}
