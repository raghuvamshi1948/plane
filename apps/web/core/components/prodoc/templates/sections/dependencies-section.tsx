import { useFieldArray, useFormContext } from "react-hook-form";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import type { TemplateFormValues } from "../template-form-types";

export function DependenciesSection() {
  const { control, watch, register } = useFormContext<TemplateFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: "dependencies" });
  const tasks = watch("tasks");
  const taskSlugs = tasks?.map((t) => t.slug).filter(Boolean) ?? [];

  return (
    <div className="space-y-3">
      {fields.length === 0 && (
        <p className="text-13 text-secondary">No dependencies. Add blocker relationships between tasks.</p>
      )}

      {fields.map((field, index) => (
        <div key={field.id} className="flex items-center gap-2 rounded-lg border border-subtle bg-surface-1 px-3 py-2">
          <select
            {...register(`dependencies.${index}.blocker_task_slug`, { required: true })}
            className="h-8 flex-1 rounded-md border border-subtle bg-surface-1 px-2 text-13"
          >
            <option value="">Blocker task...</option>
            {taskSlugs.map((slug) => (
              <option key={slug} value={slug}>
                {slug}
              </option>
            ))}
          </select>
          <span className="text-12 text-secondary">blocks</span>
          <select
            {...register(`dependencies.${index}.blocked_task_slug`, { required: true })}
            className="h-8 flex-1 rounded-md border border-subtle bg-surface-1 px-2 text-13"
          >
            <option value="">Blocked task...</option>
            {taskSlugs.map((slug) => (
              <option key={slug} value={slug}>
                {slug}
              </option>
            ))}
          </select>
          <input type="hidden" {...register(`dependencies.${index}.relation_type`)} />
          <button
            type="button"
            className="rounded p-1 text-secondary hover:bg-danger-subtle hover:text-danger-primary"
            onClick={() => remove(index)}
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      ))}

      <Button
        variant="secondary"
        size="sm"
        type="button"
        onClick={() => append({ blocker_task_slug: "", blocked_task_slug: "", relation_type: "blocked_by" })}
      >
        <Plus className="size-3.5" />
        Add dependency
      </Button>
    </div>
  );
}

/**
 * Client-side cycle detection for the dependency graph.
 * Returns null if no cycle, or a descriptive error string if a cycle exists.
 */
export function detectCycle(dependencies: { blocker_task_slug: string; blocked_task_slug: string }[]): string | null {
  const adj = new Map<string, string[]>();
  for (const dep of dependencies) {
    if (!dep.blocker_task_slug || !dep.blocked_task_slug) continue;
    if (dep.blocker_task_slug === dep.blocked_task_slug) {
      return `Self-reference: "${dep.blocker_task_slug}" cannot block itself.`;
    }
    const neighbors = adj.get(dep.blocker_task_slug) ?? [];
    neighbors.push(dep.blocked_task_slug);
    adj.set(dep.blocker_task_slug, neighbors);
  }

  const visited = new Set<string>();
  const inStack = new Set<string>();

  function dfs(node: string): string | null {
    if (inStack.has(node)) return `Dependency cycle detected involving "${node}".`;
    if (visited.has(node)) return null;
    visited.add(node);
    inStack.add(node);
    for (const neighbor of adj.get(node) ?? []) {
      const result = dfs(neighbor);
      if (result) return result;
    }
    inStack.delete(node);
    return null;
  }

  for (const node of adj.keys()) {
    const result = dfs(node);
    if (result) return result;
  }
  return null;
}
