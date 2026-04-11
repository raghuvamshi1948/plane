import useSWR from "swr";
import { APIService } from "@/services/api.service";

const PRODOC_FEATURE_FLAG_KEY = "PRODOC_FEATURE_FLAG";

class ProdocFeatureFlagService extends APIService {
  constructor() {
    super("/api/v1/prodoc");
  }

  async fetchFlag(): Promise<{ enabled: boolean }> {
    return this.get("/feature-flag/")
      .then((res) => res.data)
      .catch(() => ({ enabled: false }));
  }
}

const flagService = new ProdocFeatureFlagService();

export function useProdocFeatureFlag(): {
  enabled: boolean;
  loading: boolean;
  error: Error | undefined;
} {
  const { data, isLoading, error } = useSWR(PRODOC_FEATURE_FLAG_KEY, () => flagService.fetchFlag(), {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });

  return {
    enabled: data?.enabled ?? false,
    loading: isLoading,
    error,
  };
}
