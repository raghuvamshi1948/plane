import { useState } from "react";
import { observer } from "mobx-react";
import useSWR, { mutate } from "swr";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CircularSpinner } from "@plane/ui";
import { ProdocFeatureGate } from "@/components/prodoc/components/prodoc-feature-gate";
import { useProdocApi } from "@/components/prodoc/hooks/use-prodoc-api";
import type { ProdocMigrationRequirement } from "@/components/prodoc/hooks/use-prodoc-api";
import { MigrationRequirementEditor } from "./migration-requirement-editor";

type Props = {
  workspaceSlug: string;
};

const SWR_KEY = (ws: string) => `PRODOC_MIGRATION_REQS_${ws}`;

function MigrationRequirementsListInner({ workspaceSlug }: Props) {
  const api = useProdocApi();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const { data: items, isLoading } = useSWR(workspaceSlug ? SWR_KEY(workspaceSlug) : null, () =>
    api.listMigrationRequirements(workspaceSlug)
  );

  const handleCreate = async (data: Partial<ProdocMigrationRequirement>) => {
    await api.createMigrationRequirement(workspaceSlug, data);
    await mutate(SWR_KEY(workspaceSlug));
    setShowCreate(false);
    setToast({ type: TOAST_TYPE.SUCCESS, title: "Created migration requirement" });
  };

  const handleUpdate = async (id: string, data: Partial<ProdocMigrationRequirement>) => {
    await api.updateMigrationRequirement(workspaceSlug, id, data);
    await mutate(SWR_KEY(workspaceSlug));
    setEditingId(null);
    setToast({ type: TOAST_TYPE.SUCCESS, title: "Updated migration requirement" });
  };

  const handleDelete = async (id: string) => {
    await api.deleteMigrationRequirement(workspaceSlug, id);
    await mutate(SWR_KEY(workspaceSlug));
    setToast({ type: TOAST_TYPE.SUCCESS, title: "Deleted migration requirement" });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <CircularSpinner />
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="flex items-center justify-between pb-3.5">
        <div>
          <h4 className="text-h3-medium">Migration Requirements</h4>
          <p className="mt-1 text-13 text-secondary">Manage migration requirements available for template tasks</p>
        </div>
        <Button variant="primary" size="lg" onClick={() => setShowCreate(true)}>
          <Plus className="size-4" />
          Add requirement
        </Button>
      </div>

      {showCreate && (
        <div className="mb-3">
          <MigrationRequirementEditor onSubmit={handleCreate} onCancel={() => setShowCreate(false)} />
        </div>
      )}

      {!items || items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-subtle py-20">
          <p className="text-14 text-secondary">No migration requirements yet.</p>
          <Button variant="primary" size="lg" className="mt-4" onClick={() => setShowCreate(true)}>
            <Plus className="size-4" />
            Add requirement
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) =>
            editingId === item.id ? (
              <MigrationRequirementEditor
                key={item.id}
                item={item}
                onSubmit={(data) => handleUpdate(item.id, data)}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <div
                key={item.id}
                className="flex items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-14 font-medium">{item.name}</span>
                    {item.slug && (
                      <span className="bg-neutral-component-surface-dark rounded px-1.5 py-0.5 text-11 text-secondary">
                        {item.slug}
                      </span>
                    )}
                    {item.category && <span className="text-12 text-tertiary">{item.category}</span>}
                  </div>
                  {item.description && <p className="mt-0.5 text-13 text-secondary">{item.description}</p>}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    className="rounded p-1 text-secondary hover:bg-surface-2 hover:text-primary"
                    onClick={() => setEditingId(item.id)}
                  >
                    <Pencil className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    className="rounded p-1 text-secondary hover:bg-danger-subtle hover:text-danger-primary"
                    onClick={() => handleDelete(item.id)}
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}

export const MigrationRequirementsList = observer(function MigrationRequirementsList(props: Props) {
  return (
    <ProdocFeatureGate>
      <MigrationRequirementsListInner {...props} />
    </ProdocFeatureGate>
  );
});
