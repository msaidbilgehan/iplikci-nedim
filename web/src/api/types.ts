// The names the screens give the service's answers. The shapes come from the API's OpenAPI document (schema.ts, made
// by `uv run iplikci dev api-tipleri`, ADR-0007). Codes travel in the data; their Turkish labels come from
// /api/labels. Times are ISO 8601 strings, sizes are bytes.

import type {
  AppliedOut,
  BridgeOut,
  DocumentOut,
  DocumentPageOut,
  EventOut,
  LabelsOut,
  MailCoverageOut,
  PairingOut,
  PlanOut,
  QueuedOut,
  RefusedMailOut,
  SystemOut,
  UploadOut,
} from "./schema";

export type SystemStatus = SystemOut;
export type DocumentItem = DocumentOut;
export type DocumentPage = DocumentPageOut;
export type Labels = LabelsOut;
export type Pairing = PairingOut;
export type Bridge = BridgeOut;
export type Uploaded = UploadOut;
export type Plan = PlanOut;
export type Applied = AppliedOut;
export type LoggedEvent = EventOut;
export type Queued = QueuedOut;
export type RefusedMail = RefusedMailOut;
export type MailCoverage = MailCoverageOut;
