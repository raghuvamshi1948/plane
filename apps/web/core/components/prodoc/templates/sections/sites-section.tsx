import { Controller, useFormContext } from "react-hook-form";
import { Input, ToggleSwitch } from "@plane/ui";
import type { TemplateFormValues } from "../template-form-types";

export function SitesSection() {
  const { control, watch } = useFormContext<TemplateFormValues>();
  const requireSites = watch("require_sites");

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-13 font-medium text-primary">Require sites to be configured before materialization</span>
        <Controller
          name="require_sites"
          control={control}
          render={({ field: { value, onChange } }) => <ToggleSwitch value={value} onChange={onChange} />}
        />
      </div>

      {requireSites && (
        <div className="space-y-1">
          <span className="text-13 font-medium text-primary">Expected number of sites per project</span>
          <Controller
            name="expected_site_count"
            control={control}
            render={({ field: { value, onChange } }) => (
              <Input
                name="expected_site_count"
                type="number"
                value={String(value)}
                onChange={(e) => onChange(Number(e.target.value))}
                inputSize="md"
                className="w-32"
              />
            )}
          />
        </div>
      )}
    </div>
  );
}
