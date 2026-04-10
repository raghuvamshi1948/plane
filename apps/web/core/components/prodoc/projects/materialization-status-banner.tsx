import { useEffect, useState, useRef } from "react";
import { CheckCircle, AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { useProdocApi } from "@/components/prodoc/hooks/use-prodoc-api";

type Props = {
  workspaceSlug: string;
  projectId: string;
  jobId: string;
  onComplete: () => void;
  onRetry: () => void;
};

export function MaterializationStatusBanner({ workspaceSlug, projectId, jobId, onComplete, onRetry }: Props) {
  const api = useProdocApi();
  const [status, setStatus] = useState<"pending" | "running" | "success" | "failed">("pending");
  const [progress, setProgress] = useState({ created: 0, total: 0 });
  const [errorMessage, setErrorMessage] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const job = await api.getMaterializationJob(workspaceSlug, projectId, jobId);
        setStatus(job.status);
        setProgress({ created: job.tasks_created_so_far, total: job.tasks_total });
        if (job.status === "failed") setErrorMessage(job.error_message);
        if (job.status === "success" || job.status === "failed") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          if (job.status === "success") {
            setTimeout(onComplete, 3000);
          }
        }
      } catch {
        // silently retry on next interval
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 2000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [api, workspaceSlug, projectId, jobId, onComplete]);

  if (status === "success") {
    return (
      <div className="border-green-200 bg-green-50 text-green-700 flex items-center gap-2 rounded-lg border px-4 py-3 transition-opacity">
        <CheckCircle className="size-4" />
        <span className="text-13">Materialization complete. Refreshing...</span>
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="border-red-200 bg-red-50 flex items-center justify-between rounded-lg border px-4 py-3">
        <div className="text-red-600 flex items-center gap-2">
          <AlertTriangle className="size-4" />
          <span className="text-13">{errorMessage || "Materialization failed."}</span>
        </div>
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  return (
    <div className="border-accent-primary/20 flex items-center gap-2 rounded-lg border bg-accent-primary/5 px-4 py-3 text-accent-primary">
      <Loader2 className="size-4 animate-spin" />
      <span className="text-13">
        Materializing template... {progress.created} of {progress.total} tasks created
      </span>
    </div>
  );
}
