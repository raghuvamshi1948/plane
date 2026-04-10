import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { Button } from "@plane/propel/button";
import { Input } from "@plane/ui";
import type { ProdocSite } from "@/components/prodoc/hooks/use-prodoc-api";

type FormValues = {
  name: string;
  address: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  go_live_date: string;
};

type Props = {
  item?: ProdocSite;
  onSubmit: (data: FormValues) => Promise<void>;
  onCancel: () => void;
};

export function SiteEditor({ item, onSubmit, onCancel }: Props) {
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    defaultValues: {
      name: item?.name ?? "",
      address: item?.address ?? "",
      contact_name: item?.contact_name ?? "",
      contact_email: item?.contact_email ?? "",
      contact_phone: item?.contact_phone ?? "",
      go_live_date: item?.go_live_date ?? "",
    },
  });

  useEffect(() => {
    if (item)
      reset({
        name: item.name,
        address: item.address,
        contact_name: item.contact_name,
        contact_email: item.contact_email,
        contact_phone: item.contact_phone,
        go_live_date: item.go_live_date ?? "",
      });
  }, [item, reset]);

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3 rounded-lg border border-subtle bg-surface-1 p-4">
      <div className="space-y-1">
        <Controller
          name="name"
          control={control}
          rules={{ required: "Site name is required" }}
          render={({ field: { value, onChange } }) => (
            <Input
              name="name"
              placeholder="Site name"
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
        name="address"
        control={control}
        render={({ field: { value, onChange } }) => (
          <Input
            name="address"
            placeholder="Address"
            value={value}
            onChange={onChange}
            inputSize="md"
            className="w-full"
          />
        )}
      />
      <div className="flex gap-3">
        <Controller
          name="contact_name"
          control={control}
          render={({ field: { value, onChange } }) => (
            <Input
              name="contact_name"
              placeholder="Contact name"
              value={value}
              onChange={onChange}
              inputSize="md"
              className="flex-1"
            />
          )}
        />
        <Controller
          name="contact_email"
          control={control}
          render={({ field: { value, onChange } }) => (
            <Input
              name="contact_email"
              placeholder="Contact email"
              value={value}
              onChange={onChange}
              inputSize="md"
              className="flex-1"
            />
          )}
        />
        <Controller
          name="contact_phone"
          control={control}
          render={({ field: { value, onChange } }) => (
            <Input
              name="contact_phone"
              placeholder="Phone"
              value={value}
              onChange={onChange}
              inputSize="md"
              className="w-32"
            />
          )}
        />
      </div>
      <Controller
        name="go_live_date"
        control={control}
        render={({ field: { value, onChange } }) => (
          <Input
            name="go_live_date"
            type="date"
            placeholder="Go-live date"
            value={value}
            onChange={onChange}
            inputSize="md"
            className="w-48"
          />
        )}
      />
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
