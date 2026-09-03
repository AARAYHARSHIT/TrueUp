"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function usePipeline() {
  return useQuery({
    queryKey: ["pipeline"],
    queryFn: api.pipeline,
  });
}
