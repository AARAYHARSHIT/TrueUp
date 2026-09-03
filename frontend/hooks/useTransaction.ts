"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useTransaction(txnId: string) {
  return useQuery({
    queryKey: ["transaction", txnId],
    queryFn: () => api.transaction(txnId),
    enabled: !!txnId,
  });
}
