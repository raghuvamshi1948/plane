import { useState, useCallback } from "react";
import { ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import { Button } from "@plane/propel/button";
import { CircularSpinner, ModalCore, EModalWidth } from "@plane/ui";
import { useProdocApi } from "@/components/prodoc/hooks/use-prodoc-api";
import type { DryRunResult } from "@/components/prodoc/hooks/use-prodoc-api";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onMaterialize: () => void;
  workspaceSlug: string;
  projectId: string;
  templateId: string;
  templateName: string;
  projectName: string;
};

export function DryRunModal({
  isOpen,
  onClose,
  onMaterialize,
  workspaceSlug,
  projectId,
  templateId,
  templateName,
  projectName,
}: Props) {
  const api = useProdocApi();
  const [result, setResult] = useState<DryRunResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedWaves, setExpandedWaves] = useState<Set<string>>(new Set());

  const runDryRun = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.materialize(workspaceSlug, projectId, {
        template_id: templateId,
        dry_run: true,
      });
      setResult(data as DryRunResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dry-run failed");
    } finally {
      setLoading(false);
    }
  }, [api, workspaceSlug, projectId, templateId]);

  const handleOpen = useCallback(() => {
    if (!result && !loading) runDryRun();
  }, [result, loading, runDryRun]);

  // Trigger fetch on open
  if (isOpen && !result && !loading && !error) {
    handleOpen();
  }

  const toggleWave = (waveName: string) => {
    setExpandedWaves((prev) => {
      const next = new Set(prev);
      if (next.has(waveName)) next.delete(waveName);
      else next.add(waveName);
      return next;
    });
  };

  const hasErrors = result?.errors && result.errors.length > 0;

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} width={EModalWidth.XXXXL}>
      <div className="flex flex-col">
        {/* Header */}
        <div className="border-b border-subtle px-5 py-4">
          <h3 className="text-16 font-medium">Dry-run preview</h3>
          <p className="mt-1 text-13 text-secondary">
            Template: {templateName} → Project: {projectName}
          </p>
          {result && (
            <p className="mt-0.5 text-12 text-tertiary">
              Estimated duration: {result.estimated_duration_days} business days
            </p>
          )}
        </div>

        {/* Body */}
        <div className="max-h-[60vh] overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex flex-col items-center justify-center py-16">
              <CircularSpinner />
              <p className="mt-3 text-13 text-secondary">Running dry-run...</p>
            </div>
          )}

          {error && (
            <div className="border-red-200 bg-red-50 rounded-lg border p-4">
              <div className="text-red-600 flex items-center gap-2">
                <AlertTriangle className="size-4" />
                <span className="text-14 font-medium">Dry-run failed</span>
              </div>
              <p className="text-red-600 mt-1 text-13">{error}</p>
            </div>
          )}

          {result && hasErrors && (
            <div className="mb-4 space-y-2">
              <h4 className="text-red-600 flex items-center gap-2 text-14 font-medium">
                <AlertTriangle className="size-4" />
                Errors that must be fixed
              </h4>
              {result.errors.map((err) => (
                <div key={err} className="border-red-200 bg-red-50 text-red-600 rounded border px-3 py-2 text-13">
                  {err}
                </div>
              ))}
            </div>
          )}

          {result && !hasErrors && (
            <div className="space-y-3">
              {/* Waves with tasks */}
              {result.waves.map((wave) => {
                const waveName = (wave as { name?: string }).name ?? "Unknown wave";
                const waveSlug = (wave as { slug?: string }).slug ?? waveName;
                const isExpanded = expandedWaves.has(waveSlug);
                const waveTasks = result.tasks.filter((t) => (t as { wave_slug?: string }).wave_slug === waveSlug);

                return (
                  <div key={waveSlug} className="rounded-lg border border-subtle">
                    <button
                      type="button"
                      className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-surface-2"
                      onClick={() => toggleWave(waveSlug)}
                    >
                      {isExpanded ? (
                        <ChevronDown className="size-4 text-secondary" />
                      ) : (
                        <ChevronRight className="size-4 text-secondary" />
                      )}
                      <span className="text-14 font-medium">{waveName}</span>
                      <span className="text-12 text-tertiary">({waveTasks.length} tasks)</span>
                    </button>

                    {isExpanded && (
                      <div className="border-t border-subtle">
                        {waveTasks.map((task) => {
                          const taskData = task as {
                            name?: string;
                            slug?: string;
                            start_date?: string;
                            target_date?: string;
                          };
                          return (
                            <div key={taskData.slug} className="flex items-center justify-between px-8 py-2 text-13">
                              <span>{taskData.name}</span>
                              <span className="text-tertiary">
                                {taskData.start_date} → {taskData.target_date}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Dependencies summary */}
              {result.dependencies.length > 0 && (
                <div className="rounded-lg border border-subtle p-4">
                  <h4 className="text-14 font-medium">Dependencies ({result.dependencies.length})</h4>
                  <div className="mt-2 space-y-1">
                    {result.dependencies.map((dep) => {
                      const depData = dep as { blocker_name?: string; blocked_name?: string };
                      const depKey = `${depData.blocker_name}-${depData.blocked_name}`;
                      return (
                        <div key={depKey} className="text-13 text-secondary">
                          {depData.blocker_name} → {depData.blocked_name}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-subtle px-5 py-4">
          <Button variant="secondary" size="lg" onClick={onClose}>
            Close
          </Button>
          <Button variant="primary" size="lg" onClick={onMaterialize} disabled={loading || !!error || !!hasErrors}>
            Materialize this template
          </Button>
        </div>
      </div>
    </ModalCore>
  );
}
