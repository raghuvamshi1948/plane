import type { ReactNode } from "react";
import { useProdocFeatureFlag } from "@/components/prodoc/hooks/use-prodoc-feature-flag";

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
};

export function ProdocFeatureGate({ children, fallback = null }: Props) {
  const { enabled, loading } = useProdocFeatureFlag();

  if (loading || !enabled) return <>{fallback}</>;

  return <>{children}</>;
}
