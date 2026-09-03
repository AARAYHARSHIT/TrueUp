"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useCashPosition() {
  return useQuery({
    queryKey: ["cashPosition"],
    queryFn: api.cashPosition,
  });
}
