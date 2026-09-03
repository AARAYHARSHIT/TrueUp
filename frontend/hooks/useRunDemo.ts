"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useRunDemo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.runDemo,
    onSuccess: () => {
      qc.invalidateQueries();
    },
  });
}
