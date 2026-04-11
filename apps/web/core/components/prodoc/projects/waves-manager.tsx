import { observer } from "mobx-react";
import { useNavigate } from "react-router";
import useSWR from "swr";
import { Layers } from "lucide-react";
import { Spinner } from "@plane/ui";
import { ProdocFeatureGate } from "@/components/prodoc/components/prodoc-feature-gate";
import { useProdocApi } from "@/components/prodoc/hooks/use-prodoc-api";

type Props = {
  workspaceSlug: string;
  projectId: string;
};

function WavesManagerInner({ workspaceSlug, projectId }: Props) {
  const api = useProdocApi();
  const navigate = useNavigate();

  const { data: waves, isLoading } = useSWR(projectId ? `PRODOC_WAVES_${projectId}` : null, () =>
    api.listWaves(workspaceSlug, projectId)
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="pb-3.5">
        <h4 className="text-h3-medium">Waves</h4>
        <p className="mt-1 text-13 text-secondary">
          Waves are created during template materialization. Click a wave to view its Plane Module.
        </p>
      </div>

      {!waves || waves.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-subtle py-20">
          <Layers className="size-8 text-tertiary" />
          <p className="mt-2 text-14 text-secondary">No waves yet.</p>
          <p className="text-13 text-tertiary">Waves are created when a template is materialized.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {waves.map((wave) => (
            <button
              key={wave.id}
              type="button"
              className="flex w-full items-center justify-between rounded-lg border border-subtle bg-surface-1 px-4 py-3 text-left transition-colors hover:bg-surface-2"
              onClick={() => {
                if (wave.plane_module) {
                  navigate(`/${workspaceSlug}/projects/${projectId}/modules/${wave.plane_module}`);
                }
              }}
              disabled={!wave.plane_module}
            >
              <div className="flex items-center gap-2">
                <Layers className="size-3.5 text-tertiary" />
                <span className="text-14 font-medium">{wave.name}</span>
                <span className="bg-neutral-component-surface-dark rounded px-1.5 py-0.5 text-11 text-secondary">
                  Seq {wave.sequence}
                </span>
              </div>
              {wave.plane_module ? (
                <span className="text-12 text-accent-primary">View module →</span>
              ) : (
                <span className="text-12 text-tertiary">No module linked</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export const WavesManager = observer(function WavesManager(props: Props) {
  return (
    <ProdocFeatureGate>
      <WavesManagerInner {...props} />
    </ProdocFeatureGate>
  );
});
