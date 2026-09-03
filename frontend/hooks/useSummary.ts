"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useSummary() {
  return useQuery({
    queryKey: ["summary"],
    queryFn: api.summary,
  });
}
