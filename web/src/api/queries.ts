// The server state the screens read, through TanStack Query. The event stream invalidates these keys when the
// service records something new (useEventStream), so the screens stay current without polling hard.

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { Bridge, DocumentPage, Labels, Pairing, Queued, SystemStatus } from "./types";

export const keys = {
  system: ["system"] as const,
  labels: ["labels"] as const,
  documents: (filter: DocumentFilter) => ["documents", filter] as const,
  allDocuments: ["documents"] as const,
  bridges: ["bridges"] as const,
};

export type DocumentFilter = "all" | "unprocessed";

const FILTER_STATUSES: Record<DocumentFilter, string[]> = {
  all: [],
  unprocessed: ["unprocessed", "unreadable"],
};

export function useSystem() {
  return useQuery({
    queryKey: keys.system,
    queryFn: () => api.get<SystemStatus>("/api/system"),
    refetchInterval: 30_000, // the queue moves without events too
  });
}

/** The Turkish labels of every code type; they change only with a new version of the service. */
export function useLabels() {
  return useQuery({
    queryKey: keys.labels,
    queryFn: () => api.get<Labels>("/api/labels"),
    staleTime: Number.POSITIVE_INFINITY,
  });
}

export function useDocuments(filter: DocumentFilter) {
  return useInfiniteQuery({
    queryKey: keys.documents(filter),
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: "50" });
      for (const status of FILTER_STATUSES[filter]) {
        params.append("status", status);
      }
      if (pageParam) {
        params.set("cursor", pageParam);
      }
      return api.get<DocumentPage>(`/api/documents?${params.toString()}`);
    },
    initialPageParam: "",
    getNextPageParam: (last) => last.next || undefined,
  });
}

export function useBridges() {
  return useQuery({ queryKey: keys.bridges, queryFn: () => api.get<Bridge[]>("/api/bridge") });
}

export function useStartPairing() {
  return useMutation({ mutationFn: () => api.post<Pairing>("/api/bridge/pairings") });
}

export function useRevokeBridge() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/bridge/${encodeURIComponent(id)}`),
    onSettled: () => client.invalidateQueries({ queryKey: keys.bridges }),
  });
}

export function useBackupNow() {
  return useMutation({ mutationFn: () => api.post<Queued>("/api/backups") });
}
