import useSWR from "swr";
import { CircularSpinner } from "@plane/ui";
import { ProdocFeatureGate } from "@/components/prodoc/components/prodoc-feature-gate";
import { useProdocApi } from "@/components/prodoc/hooks/use-prodoc-api";

type Props = {
  workspaceSlug: string;
  templateId: string;
  compareId: string;
};

type DiffEntry = {
  field: string;
  type: "added" | "removed" | "changed";
  old_value?: string;
  new_value?: string;
  task_name?: string;
};

const DIFF_COLORS: Record<string, string> = {
  added: "bg-green-500/10 border-green-500/20",
  removed: "bg-red-500/10 border-red-500/20",
  changed: "bg-yellow-500/10 border-yellow-500/20",
};

const DIFF_LABELS: Record<string, string> = {
  added: "Added",
  removed: "Removed",
  changed: "Changed",
};

function VersionDiffInner({ workspaceSlug, templateId, compareId }: Props) {
  const api = useProdocApi();

  const { data: currentTemplate } = useSWR(`PRODOC_TEMPLATE_${workspaceSlug}_${templateId}`, () =>
    api.getTemplate(workspaceSlug, templateId)
  );

  const { data: compareTemplate } = useSWR(`PRODOC_TEMPLATE_${workspaceSlug}_${compareId}`, () =>
    api.getTemplate(workspaceSlug, compareId)
  );

  const { data: currentTasks } = useSWR(`PRODOC_TEMPLATE_TASKS_${templateId}`, () =>
    api.listTasks(workspaceSlug, templateId)
  );

  const { data: compareTasks } = useSWR(`PRODOC_TEMPLATE_TASKS_${compareId}`, () =>
    api.listTasks(workspaceSlug, compareId)
  );

  if (!currentTemplate || !compareTemplate || !currentTasks || !compareTasks) {
    return (
      <div className="flex items-center justify-center py-20">
        <CircularSpinner />
      </div>
    );
  }

  // Compute diff entries
  const diffs: DiffEntry[] = [];

  // Compare template-level fields
  const fieldsToCompare: (keyof typeof currentTemplate)[] = [
    "name",
    "description",
    "default_project_name_pattern",
    "default_lead_role",
  ];
  for (const field of fieldsToCompare) {
    if (currentTemplate[field] !== compareTemplate[field]) {
      diffs.push({
        field,
        type: "changed",
        old_value: String(compareTemplate[field] ?? ""),
        new_value: String(currentTemplate[field] ?? ""),
      });
    }
  }

  // Compare tasks by slug
  const currentTaskMap = new Map(currentTasks.map((t) => [t.slug, t]));
  const compareTaskMap = new Map(compareTasks.map((t) => [t.slug, t]));

  for (const [slug, task] of currentTaskMap) {
    if (!compareTaskMap.has(slug)) {
      diffs.push({ field: "task", type: "added", new_value: task.name, task_name: task.name });
    }
  }
  for (const [slug, task] of compareTaskMap) {
    if (!currentTaskMap.has(slug)) {
      diffs.push({ field: "task", type: "removed", old_value: task.name, task_name: task.name });
    }
  }
  for (const [slug, current] of currentTaskMap) {
    const compare = compareTaskMap.get(slug);
    if (!compare) continue;
    const taskFields = ["name", "duration_days", "offset_days", "wave_slug", "assignee_role_label"] as const;
    for (const tf of taskFields) {
      if (String(current[tf]) !== String(compare[tf])) {
        diffs.push({
          field: `task.${tf}`,
          type: "changed",
          old_value: String(compare[tf] ?? ""),
          new_value: String(current[tf] ?? ""),
          task_name: current.name,
        });
      }
    }
  }

  return (
    <div className="w-full space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-16 font-medium">
          Version comparison: v{compareTemplate.version} → v{currentTemplate.version}
        </h3>
      </div>

      {diffs.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-subtle py-20">
          <p className="text-14 text-secondary">No differences found between these versions.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {diffs.map((diff) => {
            const diffKey = `${diff.type}-${diff.field}-${diff.task_name ?? ""}`;
            return (
              <div key={diffKey} className={`rounded-lg border p-3 ${DIFF_COLORS[diff.type]}`}>
                <div className="flex items-center gap-2">
                  <span className="rounded px-1.5 py-0.5 text-11 font-medium">{DIFF_LABELS[diff.type]}</span>
                  <span className="text-13 font-medium">
                    {diff.task_name ? `${diff.task_name} — ${diff.field}` : diff.field}
                  </span>
                </div>
                {diff.type === "changed" && (
                  <div className="mt-1 flex gap-4 text-12">
                    <span className="text-red-600 line-through">{diff.old_value}</span>
                    <span className="text-green-600">{diff.new_value}</span>
                  </div>
                )}
                {diff.type === "added" && diff.new_value && (
                  <p className="text-green-600 mt-1 text-12">{diff.new_value}</p>
                )}
                {diff.type === "removed" && diff.old_value && (
                  <p className="text-red-600 mt-1 text-12 line-through">{diff.old_value}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function VersionDiff(props: Props) {
  return (
    <ProdocFeatureGate>
      <VersionDiffInner {...props} />
    </ProdocFeatureGate>
  );
}
