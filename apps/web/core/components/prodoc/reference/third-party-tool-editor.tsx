import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { Button } from "@plane/propel/button";
import { Input, TextArea } from "@plane/ui";
import type { ProdocThirdPartyTool } from "@/components/prodoc/hooks/use-prodoc-api";

type FormValues = {
  name: string;
  description: string;
  category: string;
  default_owner_role: string;
};

type Props = {
  item?: ProdocThirdPartyTool;
  onSubmit: (data: FormValues) => Promise<void>;
  onCancel: () => void;
};

export function ThirdPartyToolEditor({ item, onSubmit, onCancel }: Props) {
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    defaultValues: {
      name: item?.name ?? "",
      description: item?.description ?? "",
      category: item?.category ?? "",
      default_owner_role: item?.default_owner_role ?? "",
    },
  });

  useEffect(() => {
    if (item)
      reset({
        name: item.name,
        description: item.description,
        category: item.category,
        default_owner_role: item.default_owner_role,
      });
  }, [item, reset]);

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3 rounded-lg border border-subtle bg-surface-1 p-4">
      <div className="space-y-1">
        <Controller
          name="name"
          control={control}
          rules={{ required: "Name is required" }}
          render={({ field: { value, onChange } }) => (
            <Input
              name="name"
              placeholder="Name"
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
      <Controller
        name="description"
        control={control}
        render={({ field: { value, onChange } }) => (
          <TextArea
            name="description"
            placeholder="Description"
            value={value}
            onChange={onChange}
            className="min-h-16 w-full resize-none text-14"
          />
        )}
      />
      <div className="flex gap-3">
        <Controller
          name="category"
          control={control}
          render={({ field: { value, onChange } }) => (
            <Input
              name="category"
              placeholder="Category"
              value={value}
              onChange={onChange}
              inputSize="md"
              className="flex-1"
            />
          )}
        />
        <Controller
          name="default_owner_role"
          control={control}
          render={({ field: { value, onChange } }) => (
            <Input
              name="default_owner_role"
              placeholder="Default owner role"
              value={value}
              onChange={onChange}
              inputSize="md"
              className="flex-1"
            />
          )}
        />
      </div>
      <div className="flex items-center justify-end gap-2 pt-1">
        <Button variant="secondary" size="sm" onClick={onCancel} type="button">
          Cancel
        </Button>
        <Button variant="primary" size="sm" type="submit" loading={isSubmitting}>
          {item ? "Update" : "Create"}
        </Button>
      </div>
    </form>
  );
}
