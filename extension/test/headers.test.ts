import { describe, expect, it } from "vitest";

import {
  field,
  headers,
  listed,
  looksLikeMessage,
  senderDomain,
  topAuthentication,
  verifiedByGmail,
} from "../src/mail/headers";
import { rawMessage } from "./fixtures";

describe("header fields", () => {
  it("join folded lines and stop at the body", () => {
    const fields = headers("A: one\r\n  two\r\nB:three\r\n\r\nC: body");
    expect(fields).toEqual([
      { name: "A", value: "one two" },
      { name: "B", value: "three" },
    ]);
    expect(field(fields, "b")).toBe("three");
    expect(field(fields, "C")).toBeNull();
  });

  it("tell an e-mail message from other text", () => {
    expect(looksLikeMessage(rawMessage({ from: "ekstre@teb.com.tr" }))).toBe(true);
    expect(looksLikeMessage("<!DOCTYPE html>\n<html></html>")).toBe(false);
    expect(looksLikeMessage("From: a@b.c\nTo: d@e.f\nSubject: x\n\nbody")).toBe(false);
  });

  it.each([
    ["Banka <Ekstre@GarantiBBVA.com.tr>", "garantibbva.com.tr"],
    ["ekstre@teb.com.tr", "teb.com.tr"],
    ['"a@b" <bilgi@isbank.com.tr>', "isbank.com.tr"],
    ["Adressiz", ""],
  ])("take the sender's domain from %s", (from, domain) => {
    expect(senderDomain([{ name: "From", value: from }])).toBe(domain);
  });
});

describe("the trust rule's header half", () => {
  it("reads the topmost Authentication-Results only", () => {
    const fields = headers(rawMessage({ from: "ekstre@garantibbva.com.tr" }));
    expect(topAuthentication(fields)).toEqual({ server: "mx.google.com", dmarcPassFor: "garantibbva.com.tr" });
    expect(verifiedByGmail(fields)).toBe(true);
  });

  it.each([
    ["another server added it", "mail.example.net; dmarc=pass header.from=garantibbva.com.tr"],
    ["DMARC failed", "mx.google.com; dmarc=fail (p=REJECT) header.from=garantibbva.com.tr"],
    ["DMARC passed for another domain", "mx.google.com; dmarc=pass header.from=example.net"],
    ["there is none", null],
  ])("refuses a message when %s", (_case, authentication) => {
    expect(verifiedByGmail(headers(rawMessage({ from: "ekstre@garantibbva.com.tr", authentication })))).toBe(false);
  });

  it("counts a listed domain and its subdomains, nothing that only ends alike", () => {
    const senders = ["isbank.com.tr", "teb.com.tr"];
    expect(listed("isbank.com.tr", senders)).toBe(true);
    expect(listed("ileti.isbank.com.tr", senders)).toBe(true);
    expect(listed("notisbank.com.tr", senders)).toBe(false);
    expect(listed("", senders)).toBe(false);
  });
});
