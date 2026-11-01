/**
 * The proof that the service on 127.0.0.1:8643 is the one this extension paired with (ADR-0016): the service answers
 * a fresh nonce with HMAC-SHA256 keyed with the token's SHA-256 (hexadecimal), which only the paired service holds.
 * A process listening in the service's place cannot answer, so it receives no message.
 */

const encoder = new TextEncoder();

function hex(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(text: string): Promise<string> {
  return hex(await crypto.subtle.digest("SHA-256", encoder.encode(text)));
}

/** What the paired service answers to nonce. */
export async function expectedProof(token: string, nonce: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(await sha256Hex(token)),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return hex(await crypto.subtle.sign("HMAC", key, encoder.encode(nonce)));
}

/** 32 hexadecimal characters from the browser's random source. */
export function newNonce(): string {
  return hex(crypto.getRandomValues(new Uint8Array(16)).buffer);
}
