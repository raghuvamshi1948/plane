import { Controller, useFormContext } from "react-hook-form";
import { Input, ToggleSwitch } from "@plane/ui";
import type { TemplateFormValues } from "../template-form-types";

export function ProjectDefaultsSection() {
  const { control } = useFormContext<TemplateFormValues>();

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <span className="text-13 font-medium text-primary">Default project name pattern</span>
        <Controller
          name="default_project_name_pattern"
          control={control}
          render={({ field: { value, onChange } }) => (
            <Input
              name="default_project_name_pattern"
              placeholder="e.g. {site_name} - Onboarding"
              value={value}
              onChange={onChange}
              inputSize="md"
              className="w-full"
            />
          )}
        />
      </div>

      <div className="space-y-1">
        <span className="text-13 font-medium text-primary">Default lead role</span>
        <Controller
          name="default_lead_role"
          control={control}
          render={({ field: { value, onChange } }) => (
            <Input
              name="default_lead_role"
              placeholder="e.g. Project Manager"
              value={value}
              onChange={onChange}
              inputSize="md"
              className="w-full"
            />
          )}
        />
      </div>

      <div className="flex items-center justify-between">
        <span className="text-13 font-medium text-primary">Public project</span>
        <Controller
          name="is_public"
          control={control}
          render={({ field: { value, onChange } }) => <ToggleSwitch value={value} onChange={onChange} />}
        />
      </div>
    </div>
  );
}
