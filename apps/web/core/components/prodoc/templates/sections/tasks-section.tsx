import { useState } from "react";
import { useFieldArray, useFormContext } from "react-hook-form";
import { ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { Input, TextArea } from "@plane/ui";
import type { TemplateFormValues } from "../template-form-types";

type Props = {
  migrationRequirementSlugs: string[];
  thirdPartyToolSlugs: string[];
};

export function TasksSection({ migrationRequirementSlugs, thirdPartyToolSlugs }: Props) {
  const {
    control,
    register,
    watch,
    formState: { errors },
  } = useFormContext<TemplateFormValues>();

  const { fields, append, remove } = useFieldArray({ control, name: "tasks" });
  const waves = watch("waves");
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const tasksErrors = errors.tasks;

  return (
    <div className="space-y-3">
      {fields.length === 0 && <p className="text-13 text-secondary">No tasks added. At least one task is required.</p>}

      <div className="space-y-2">
        {fields.map((field, index) => {
          const isExpanded = expandedIndex === index;
          return (
            <div key={field.id} className="rounded-lg border border-subtle bg-surface-1">
              <div className="flex items-center gap-2 px-3 py-2">
                <button
                  type="button"
                  className="rounded p-0.5 text-secondary hover:text-primary"
                  onClick={() => setExpandedIndex(isExpanded ? null : index)}
                >
                  {isExpanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                </button>
                <div className="flex flex-1 items-center gap-2">
                  <Input
                    {...register(`tasks.${index}.name`, { required: "Task name is required" })}
                    placeholder="Task name"
                    inputSize="md"
                    className="flex-1"
                    hasError={Boolean(tasksErrors?.[index]?.name)}
                  />
                  <select
                    {...register(`tasks.${index}.wave_slug`, { required: true })}
                    className="h-8 rounded-md border border-subtle bg-surface-1 px-2 text-13"
                  >
                    <option value="">Wave...</option>
                    {waves?.map((w) => (
                      <option key={w.slug} value={w.slug}>
                        {w.name || w.slug}
                      </option>
                    ))}
                  </select>
                  <Input
                    {...register(`tasks.${index}.duration_days`, { valueAsNumber: true })}
                    type="number"
                    placeholder="Days"
                    inputSize="md"
                    className="w-16"
                  />
                  <Input
                    {...register(`tasks.${index}.offset_days`, { valueAsNumber: true })}
                    type="number"
                    placeholder="Offset"
                    inputSize="md"
                    className="w-16"
                  />
                  <Input
                    {...register(`tasks.${index}.assignee_role_label`)}
                    placeholder="Role"
                    inputSize="md"
                    className="w-28"
                  />
                </div>
                <button
                  type="button"
                  className="rounded p-1 text-secondary hover:bg-danger-subtle hover:text-danger-primary"
                  onClick={() => {
                    if (expandedIndex === index) setExpandedIndex(null);
                    remove(index);
                  }}
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
              {tasksErrors?.[index]?.name && (
                <div className="px-10 pb-1">
                  <span className="text-11 text-danger-primary">{tasksErrors[index].name.message}</span>
                </div>
              )}

              {isExpanded && (
                <div className="space-y-3 border-t border-subtle px-10 py-3">
                  <div className="flex gap-2">
                    <div className="w-24 space-y-1">
                      <span className="text-12 text-secondary">Slug</span>
                      <Input
                        {...register(`tasks.${index}.slug`, { required: "Slug required" })}
                        placeholder="task-slug"
                        inputSize="md"
                        className="w-full"
                        hasError={Boolean(tasksErrors?.[index]?.slug)}
                      />
                    </div>
                    <div className="w-20 space-y-1">
                      <span className="text-12 text-secondary">Sequence</span>
                      <Input
                        {...register(`tasks.${index}.sequence`, { valueAsNumber: true })}
                        type="number"
                        inputSize="md"
                        className="w-full"
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <span className="text-12 text-secondary">Description</span>
                    <TextArea
                      {...register(`tasks.${index}.description`)}
                      placeholder="Task description"
                      className="min-h-16 w-full resize-none text-13"
                    />
                  </div>

                  <div className="space-y-1">
                    <span className="text-12 text-secondary">Migration requirements</span>
                    <MultiSlugSelect
                      availableSlugs={migrationRequirementSlugs}
                      fieldName={`tasks.${index}.migration_requirement_slugs`}
                    />
                  </div>

                  <div className="space-y-1">
                    <span className="text-12 text-secondary">Third-party tools</span>
                    <MultiSlugSelect
                      availableSlugs={thirdPartyToolSlugs}
                      fieldName={`tasks.${index}.third_party_tool_slugs`}
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <Button
        variant="secondary"
        size="sm"
        type="button"
        onClick={() =>
          append({
            name: "",
            slug: "",
            description: "",
            wave_slug: waves?.[0]?.slug ?? "",
            duration_days: 1,
            offset_days: 0,
            assignee_role_label: "",
            migration_requirement_slugs: [],
            third_party_tool_slugs: [],
            sequence: fields.length + 1,
          })
        }
      >
        <Plus className="size-3.5" />
        Add task
      </Button>
    </div>
  );
}

function MultiSlugSelect({ availableSlugs, fieldName }: { availableSlugs: string[]; fieldName: string }) {
  const { watch, setValue } = useFormContext();
  const selected: string[] = watch(fieldName) ?? [];

  const toggleSlug = (slug: string) => {
    const next = selected.includes(slug) ? selected.filter((s) => s !== slug) : [...selected, slug];
    setValue(fieldName, next);
  };

  if (availableSlugs.length === 0) {
    return <p className="text-12 text-tertiary">No items available. Create reference data first.</p>;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {availableSlugs.map((slug) => (
        <button
          key={slug}
          type="button"
          className={`rounded-full border px-2.5 py-0.5 text-12 transition-colors ${
            selected.includes(slug)
              ? "border-accent-primary bg-accent-primary/10 text-accent-primary"
              : "hover:border-primary border-subtle text-secondary hover:text-primary"
          }`}
          onClick={() => toggleSlug(slug)}
        >
          {slug}
        </button>
      ))}
    </div>
  );
}
