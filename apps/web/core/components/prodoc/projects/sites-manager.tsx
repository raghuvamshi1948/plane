import { useState } from "react";
import { observer } from "mobx-react";
import useSWR, { mutate } from "swr";
import { MapPin, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Spinner } from "@plane/ui";
import { ProdocFeatureGate } from "@/components/prodoc/components/prodoc-feature-gate";
import { useProdocApi } from "@/components/prodoc/hooks/use-prodoc-api";
import type { ProdocSite } from "@/components/prodoc/hooks/use-prodoc-api";
import { SiteEditor } from "./site-editor";

type Props = {
  workspaceSlug: string;
  projectId: string;
};

const SWR_KEY = (pid: string) => `PRODOC_SITES_${pid}`;

function SitesManagerInner({ workspaceSlug, projectId }: Props) {
  const api = useProdocApi();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const { data: sites, isLoading } = useSWR(projectId ? SWR_KEY(projectId) : null, () =>
    api.listSites(workspaceSlug, projectId)
  );

  const handleCreate = async (data: Partial<ProdocSite>) => {
    await api.createSite(workspaceSlug, projectId, data);
    await mutate(SWR_KEY(projectId));
    setShowCreate(false);
    setToast({ type: TOAST_TYPE.SUCCESS, title: "Site created" });
  };

  const handleUpdate = async (siteId: string, data: Partial<ProdocSite>) => {
    await api.updateSite(workspaceSlug, projectId, siteId, data);
    await mutate(SWR_KEY(projectId));
    setEditingId(null);
    setToast({ type: TOAST_TYPE.SUCCESS, title: "Site updated" });
  };

  const handleDelete = async (siteId: string) => {
    await api.deleteSite(workspaceSlug, projectId, siteId);
    await mutate(SWR_KEY(projectId));
    setToast({ type: TOAST_TYPE.SUCCESS, title: "Site deleted" });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="flex items-center justify-between pb-3.5">
        <div>
          <h4 className="text-h3-medium">Sites</h4>
          <p className="mt-1 text-13 text-secondary">Manage implementation sites for this project</p>
        </div>
        <Button variant="primary" size="lg" onClick={() => setShowCreate(true)}>
          <Plus className="size-4" />
          Add site
        </Button>
      </div>

      {showCreate && (
        <div className="mb-3">
          <SiteEditor onSubmit={handleCreate} onCancel={() => setShowCreate(false)} />
        </div>
      )}

      {!sites || sites.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-subtle py-20">
          <MapPin className="size-8 text-tertiary" />
          <p className="mt-2 text-14 text-secondary">No sites configured.</p>
          <Button variant="primary" size="lg" className="mt-4" onClick={() => setShowCreate(true)}>
            <Plus className="size-4" />
            Add site
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          {sites.map((site) =>
            editingId === site.id ? (
              <SiteEditor
                key={site.id}
                item={site}
                onSubmit={(data) => handleUpdate(site.id, data)}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <div
                key={site.id}
                className="flex items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <MapPin className="size-3.5 text-tertiary" />
                    <span className="text-14 font-medium">{site.name}</span>
                    {site.go_live_date && <span className="text-12 text-tertiary">Go-live: {site.go_live_date}</span>}
                  </div>
                  {site.address && <p className="mt-0.5 pl-5 text-13 text-secondary">{site.address}</p>}
                  {site.contact_name && (
                    <p className="pl-5 text-12 text-tertiary">
                      {site.contact_name}
                      {site.contact_email && ` · ${site.contact_email}`}
                      {site.contact_phone && ` · ${site.contact_phone}`}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    className="rounded p-1 text-secondary hover:bg-surface-2 hover:text-primary"
                    onClick={() => setEditingId(site.id)}
                  >
                    <Pencil className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    className="rounded p-1 text-secondary hover:bg-danger-subtle hover:text-danger-primary"
                    onClick={() => handleDelete(site.id)}
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

export const SitesManager = observer(function SitesManager(props: Props) {
  return (
    <ProdocFeatureGate>
      <SitesManagerInner {...props} />
    </ProdocFeatureGate>
  );
});
