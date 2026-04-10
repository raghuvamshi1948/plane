import { useFieldArray, useFormContext } from "react-hook-form";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { Input } from "@plane/ui";
import type { TemplateFormValues } from "../template-form-types";

export function WavesSection() {
  const {
    control,
    register,
    formState: { errors },
  } = useFormContext<TemplateFormValues>();

  const { fields, append, remove } = useFieldArray({ control, name: "waves" });

  const wavesErrors = errors.waves;

  return (
    <div className="space-y-3">
      {fields.length === 0 && <p className="text-13 text-secondary">No waves added. At least one wave is required.</p>}

      {fields.map((field, index) => (
        <div key={field.id} className="flex items-start gap-2 rounded-lg border border-subtle bg-surface-1 p-3">
          <div className="flex flex-1 flex-col gap-2">
            <div className="flex gap-2">
              <div className="flex-1">
                <Input
                  {...register(`waves.${index}.name`, { required: "Wave name is required" })}
                  placeholder="Wave name"
                  inputSize="md"
                  className="w-full"
                  hasError={Boolean(wavesErrors?.[index]?.name)}
                />
                {wavesErrors?.[index]?.name && (
                  <span className="text-11 text-danger-primary">{wavesErrors[index].name.message}</span>
                )}
              </div>
              <div className="w-24">
                <Input
                  {...register(`waves.${index}.slug`, { required: "Slug is required" })}
                  placeholder="Slug"
                  inputSize="md"
                  className="w-full"
                  hasError={Boolean(wavesErrors?.[index]?.slug)}
                />
              </div>
              <div className="w-20">
                <Input
                  {...register(`waves.${index}.sequence`, { valueAsNumber: true })}
                  type="number"
                  placeholder="Seq"
                  inputSize="md"
                  className="w-full"
                />
              </div>
            </div>
            <Input
              {...register(`waves.${index}.description`)}
              placeholder="Description (optional)"
              inputSize="md"
              className="w-full"
            />
          </div>
          <button
            type="button"
            className="mt-1 rounded p-1 text-secondary hover:bg-danger-subtle hover:text-danger-primary"
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
        onClick={() => append({ name: "", slug: "", sequence: fields.length + 1, description: "" })}
      >
        <Plus className="size-3.5" />
        Add wave
      </Button>
    </div>
  );
}
