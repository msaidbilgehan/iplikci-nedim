// The service's API types, generated from its OpenAPI document by `iplikci dev api-tipleri` (ADR-0007).
// Do not edit by hand: change the API's models and generate again; a test keeps this file current.

export interface AlarmIn {
  layer: number;
  version?: string;
}

export interface AlarmOut {
  news: boolean;
}

export interface AppliedOut {
  stored: number;
  counts: Record<string, number>;
  trash: string | null;
}

export interface ApplyIn {
  plan_id: string;
}

export interface BackupHealthOut {
  last: string;
  next: string;
  count: number;
  size: number;
  rehearsal: string;
  rehearsal_ok: boolean | null;
}

export interface BackupOut {
  name: string;
  created_at: string;
  reason: string;
  app: string;
  documents: number;
  annotations: number;
  size: number;
  damaged: number;
}

export interface BridgeOut {
  id: string;
  name: string;
  created_at: string;
  last_seen: string;
  active: boolean;
}

export interface CursorOut {
  last_id: string;
  last_date: string;
  start_day: string;
  senders: string[];
}

export interface DeliveredOut {
  taken: string;
  documents: number;
}

export interface DiskOut {
  vault: number;
  database: number;
  free: number;
}

export interface DocumentOut {
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

export interface DocumentPageOut {
  items: DocumentOut[];
  next: string;
}

export interface EventOut {
  id: number;
  at: string;
  kind: string;
  target: string;
  detail: Record<string, unknown>;
}

export interface FailedJobOut {
  id: number;
  kind: string;
  attempts: number;
  finished_at: string;
  error: string;
}

export interface FetchQueuedOut {
  queued: boolean;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

/** The Turkish label of every code, by code type (DocumentStatus, JobKind, …). */
export type LabelsOut = Record<string, Record<string, string>>;

export interface LoginLink {
  url: string;
}

export interface MailOut {
  connector: "imap" | "browser_bridge";
  configured: boolean;
  last_run: string;
  last_error: string;
  stopped: boolean;
}

export interface PairIn {
  code: string;
  name?: string;
}

export interface PairedOut {
  id: string;
  token: string;
}

export interface PairingOut {
  code: string;
  expires_in: number;
}

/** The document a plan item would add: a statement, an account statement or a receipt, and its check. */
export interface PlanDocumentOut {
  kind: string;
  account: string;
  start: string | null;
  end: string;
  rows: number;
  verified: boolean | null;
  check: string;
}

export interface PlanIn {
  upload?: string;
}

/**
 * One file of a plan (intake.describe): what it is and what happens to it. The MCP client reads the same keys, so two
 * keep their camelCase names.
 */
export interface PlanItemOut {
  action: string;
  label: string;
  name: string;
  source: string;
  reason: string;
  copyOf: string | null;
  target: string | null;
  fromInbox: boolean;
  document?: PlanDocumentOut | null;
}

export interface PlanOut {
  plan_id: string;
  changes: number;
  by_action: Record<string, number>;
  items: PlanItemOut[];
}

export interface ProofOut {
  proof: string;
}

export interface QueueOut {
  counts: Record<string, number>;
  next_run: string;
  failures: FailedJobOut[];
}

export interface QueuedOut {
  queued: boolean;
}

export interface ReaderHealthOut {
  parser: string;
  name: string;
  version: string;
  documents: number;
  statements: number;
  verified: number;
  last_read: string;
  alarms: number;
}

export interface ServiceOut {
  version: string;
  started_at: string;
  pid: number;
  home: string;
}

export interface SystemOut {
  service: ServiceOut;
  documents: Record<string, number>;
  readers: ReaderHealthOut[];
  disk: DiskOut;
  queue: QueueOut;
  mail: MailOut;
  backup: BackupHealthOut;
}

export interface UploadOut {
  batch: string;
  status: "eklendi" | "zaten-var" | "reddedildi";
  name: string;
  reason: string;
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}
