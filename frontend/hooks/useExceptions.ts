"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useExceptions(type?: string) {
  return useQuery({
    queryKey: ["exceptions", type],
    queryFn: () => api.exceptions(type),
  });
}
