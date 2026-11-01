// What the service's API answers (src/iplikci/api). Codes travel in the data; their Turkish labels come from
// /api/labels. Times are ISO 8601 strings, sizes are bytes.

export interface ReaderHealth {
  parser: string;
  name: string;
  version: string;
  documents: number;
  statements: number;
  verified: number;
  last_read: string;
  alarms: number;
}

export interface FailedJob {
  id: number;
  kind: string;
  attempts: number;
  finished_at: string;
  error: string;
}

export interface MailHealth {
  connector: "imap" | "browser_bridge";
  configured: boolean;
  last_run: string;
  last_error: string;
  stopped: boolean;
}

export interface BackupHealth {
  last: string;
  next: string;
  count: number;
  size: number;
  rehearsal: string;
  rehearsal_ok: boolean | null;
}

export interface SystemStatus {
  service: { version: string; started_at: string; pid: number; home: string };
  documents: Record<string, number>;
  readers: ReaderHealth[];
  disk: { vault: number; database: number; free: number };
  queue: { counts: Record<string, number>; next_run: string; failures: FailedJob[] };
  mail: MailHealth;
  backup: BackupHealth;
}

export interface DocumentItem {
  sha256: string;
  name: string;
  file: string;
  kind: string;
  parser: string;
  reader: string;
  status: "processed" | "unprocessed" | "unreadable";
  reason: string;
  verified: boolean | null;
  period_start: string;
  period_end: string;
  sources: string[];
  added_at: string;
  size: number;
}

export interface DocumentPage {
  items: DocumentItem[];
  next: string;
}

export type Labels = Record<string, Record<string, string>>;

export interface Pairing {
  code: string;
  expires_in: number;
}

export interface Bridge {
  id: string;
  name: string;
  created_at: string;
  last_seen: string;
  active: boolean;
}

export interface Uploaded {
  batch: string;
  status: "eklendi" | "zaten-var" | "reddedildi";
  name: string;
  reason: string;
}

export interface PlanDocument {
  kind: string;
  account: string;
  start: string | null;
  end: string;
  rows?: number;
  verified?: boolean;
  check?: string;
}

export interface PlanItem {
  action: string;
  label: string;
  name: string;
  source: string;
  reason: string;
  copyOf: string;
  target: string | null;
  fromInbox: boolean;
  document?: PlanDocument;
}

export interface Plan {
  plan_id: string;
  changes: number;
  by_action: Record<string, number>;
  items: PlanItem[];
}

export interface Applied {
  stored: number;
  counts: Record<string, number>;
  trash: string | null;
}

export interface LoggedEvent {
  id: number;
  at: string;
  kind: string;
  target: string;
  detail: Record<string, unknown>;
}
