import { Controller, useFormContext } from "react-hook-form";
import { Input, TextArea } from "@plane/ui";
import type { TemplateFormValues } from "../template-form-types";

export function MetadataSection() {
  const {
    control,
    formState: { errors },
  } = useFormContext<TemplateFormValues>();

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <span className="text-13 font-medium text-primary">Name *</span>
        <Controller
          name="name"
          control={control}
          rules={{ required: "Template name is required" }}
          render={({ field: { value, onChange } }) => (
            <Input
              name="name"
              placeholder="e.g. MGM Phase 1 Onboarding"
              value={value}
              onChange={onChange}
              hasError={Boolean(errors.name)}
              inputSize="md"
              className="w-full"
            />
          )}
        />
        {errors.name && <span className="text-11 text-danger-primary">{errors.name.message}</span>}
      </div>

      <div className="space-y-1">
        <span className="text-13 font-medium text-primary">Description *</span>
        <Controller
          name="description"
          control={control}
          rules={{ required: "Description is required" }}
          render={({ field: { value, onChange } }) => (
            <TextArea
              name="description"
              placeholder="Describe this onboarding playbook"
              value={value}
              onChange={onChange}
              hasError={Boolean(errors.description)}
              className="min-h-20 w-full resize-none text-14"
            />
          )}
        />
        {errors.description && <span className="text-11 text-danger-primary">{errors.description.message}</span>}
      </div>

      <div className="flex gap-3">
        <div className="flex-1 space-y-1">
          <span className="text-13 font-medium text-primary">Cover image URL</span>
          <Controller
            name="cover_image_url"
            control={control}
            render={({ field: { value, onChange } }) => (
              <Input
                name="cover_image_url"
                placeholder="https://..."
                value={value}
                onChange={onChange}
                inputSize="md"
                className="w-full"
              />
            )}
          />
        </div>
        <div className="w-24 space-y-1">
          <span className="text-13 font-medium text-primary">Icon</span>
          <Controller
            name="icon"
            control={control}
            render={({ field: { value, onChange } }) => (
              <Input
                name="icon"
                placeholder="e.g. rocket"
                value={value}
                onChange={onChange}
                inputSize="md"
                className="w-full"
              />
            )}
          />
        </div>
      </div>
    </div>
  );
}
