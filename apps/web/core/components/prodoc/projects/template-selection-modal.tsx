import { useState } from "react";
import useSWR from "swr";
import { Search } from "lucide-react";
import { Button } from "@plane/propel/button";
import { Spinner, ModalCore, EModalWidth } from "@plane/ui";
import { useProdocApi } from "@/components/prodoc/hooks/use-prodoc-api";
import { TemplateStatusBadge } from "@/components/prodoc/templates/template-status-badge";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (templateId: string, templateName: string) => void;
  workspaceSlug: string;
};

export function TemplateSelectionModal({ isOpen, onClose, onSelect, workspaceSlug }: Props) {
  const api = useProdocApi();
  const [search, setSearch] = useState("");

  const { data: templates, isLoading } = useSWR(
    isOpen && workspaceSlug ? `PRODOC_TEMPLATES_${workspaceSlug}` : null,
    () => api.listTemplates(workspaceSlug)
  );

  const filtered = (templates ?? []).filter(
    (t) => (t.status === "active" || t.status === "locked") && t.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} width={EModalWidth.XXL}>
      <div className="flex flex-col">
        <div className="border-b border-subtle px-5 py-4">
          <h3 className="text-16 font-medium">Select a template</h3>
          <p className="mt-1 text-13 text-secondary">Choose an onboarding template to apply to this project</p>
        </div>

        <div className="px-5 pt-3">
          <div className="flex items-center gap-1.5 rounded-md border border-subtle bg-surface-1 px-2.5 py-1.5">
            <Search className="size-3.5 text-placeholder" />
            <input
              className="w-full border-none bg-transparent text-13 outline-none placeholder:text-placeholder"
              placeholder="Search templates..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="max-h-80 overflow-y-auto px-5 py-3">
          {isLoading ? (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          ) : filtered.length === 0 ? (
            <p className="py-10 text-center text-13 text-secondary">No published templates found.</p>
          ) : (
            <div className="space-y-2">
              {filtered.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className="flex w-full items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3 text-left transition-colors hover:bg-surface-2"
                  onClick={() => onSelect(t.id, t.name)}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-14 font-medium">{t.name}</span>
                      <TemplateStatusBadge status={t.status} />
                    </div>
                    {t.description && <p className="mt-0.5 line-clamp-1 text-13 text-secondary">{t.description}</p>}
                  </div>
                  <span className="text-12 text-tertiary">v{t.version}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end border-t border-subtle px-5 py-4">
          <Button variant="secondary" size="lg" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </ModalCore>
  );
}
