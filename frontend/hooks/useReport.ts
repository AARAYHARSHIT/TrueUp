"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useReport() {
  return useQuery({
    queryKey: ["report"],
    queryFn: api.report,
  });
}
