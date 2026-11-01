import { describe, expect, it } from "vitest";

import { keys } from "../api/queries";
import { staleBy } from "./useEventStream";

describe("staleBy", () => {
  it("refreshes the documents on a document's events and the System screen on every event", () => {
    expect(staleBy("document.received")).toEqual([keys.allDocuments, keys.system]);
    expect(staleBy("parser.format_alarm")).toEqual([keys.allDocuments, keys.system]);
    expect(staleBy("backup.failed")).toEqual([keys.system]);
    expect(staleBy("mail.auth_failed")).toEqual([keys.system]);
    expect(staleBy("bridge.paired")).toEqual([keys.bridges, keys.system]); // the pairing page shows the new one
  });
});
