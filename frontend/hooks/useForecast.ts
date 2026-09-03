"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useForecast() {
  return useQuery({
    queryKey: ["forecast"],
    queryFn: api.forecast,
  });
}
