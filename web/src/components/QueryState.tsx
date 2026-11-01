// Every data screen's loading, error and empty states (features.md, shared rules): an error says what happened and
// offers to try again; an ended session says how to come back in.

import type { ReactNode } from "react";

import { ApiError } from "../api/client";
import { Alert } from "./ui/Alert";
import { Button } from "./ui/Button";

export function Loading({ label = "Yükleniyor…" }: { label?: string }) {
  return (
    <div role="status" className="flex flex-col gap-2" aria-label={label}>
      <div className="h-4 w-1/3 animate-pulse rounded bg-zinc-200 motion-reduce:animate-none dark:bg-zinc-700" />
      <div className="h-4 w-2/3 animate-pulse rounded bg-zinc-200 motion-reduce:animate-none dark:bg-zinc-700" />
      <div className="h-4 w-1/2 animate-pulse rounded bg-zinc-200 motion-reduce:animate-none dark:bg-zinc-700" />
    </div>
  );
}

export function Failure({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  if (error instanceof ApiError && error.signedOut) {
    return <SignedOut />;
  }
  const message = error instanceof Error ? error.message : "Beklenmeyen bir hata oldu.";
  return (
    <Alert tone="critical" title="Yüklenemedi">
      <p>{message}</p>
      <Button variant="secondary" className="mt-2" onClick={onRetry}>
        Yeniden dene
      </Button>
    </Alert>
  );
}

export function SignedOut() {
  return (
    <Alert tone="warning" title="Oturum kapandı">
      <p>Arayüzü İplikçi Nedim'den yeniden açın; tek kullanımlık yeni bir giriş bağlantısı açılır.</p>
    </Alert>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-zinc-300 p-6 text-center dark:border-zinc-600">
      <p className="font-medium text-zinc-800 dark:text-zinc-100">{title}</p>
      {children ? <div className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">{children}</div> : null}
    </div>
  );
}
