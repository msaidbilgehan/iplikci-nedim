/**
 * Requests to Gmail: GETs only (ADR-0016: the bridge never changes anything in Gmail), with the browser's Gmail
 * session, and never following a redirect: a redirect leaves Gmail, mostly for the sign-in page. The one exception is
 * "Download original", which Gmail sends on to its attachment server.
 */

export const ORIGIN = "https://mail.google.com";
/** Where Gmail's "Download original" leads: the whole message comes from there (ADR-0016, 2026-11-01 note). */
export const ATTACHMENTS_ORIGIN = "https://mail-attachment.googleusercontent.com";

export type Fetcher = (url: string, init: RequestInit) => Promise<Response>;

/** Gmail sent the request elsewhere: mostly to the sign-in page, as no session is open for that account. */
export class Redirected extends Error {
  override name = "Redirected";
}

/** Gmail answered with an error status. */
export class HttpError extends Error {
  override name = "HttpError";

  constructor(readonly status: number) {
    super(`Gmail ${status} yanıtı verdi`);
  }
}

/** GET a Gmail address with the browser's cookies; the response when it is a success, an error otherwise. */
export async function get(fetcher: Fetcher, url: string): Promise<Response> {
  if (!url.startsWith(`${ORIGIN}/`)) {
    throw new Error(`not a Gmail address: ${url}`);
  }
  const response = await fetcher(url, {
    method: "GET",
    credentials: "include", // cross-origin from the extension: cookies go only when asked for
    redirect: "manual",
    cache: "no-store",
  });
  if (response.type === "opaqueredirect" || (response.status >= 300 && response.status < 400)) {
    throw new Redirected("Gmail başka bir adrese yönlendirdi");
  }
  if (!response.ok) {
    throw new HttpError(response.status);
  }
  return response;
}

/**
 * GET a Gmail download, following Gmail on to its attachment server and nowhere else: a download that ends anywhere
 * else (the sign-in page, when no session is open) is Redirected.
 */
export async function download(fetcher: Fetcher, url: string): Promise<Response> {
  if (!url.startsWith(`${ORIGIN}/`)) {
    throw new Error(`not a Gmail address: ${url}`);
  }
  const response = await fetcher(url, { method: "GET", credentials: "include", redirect: "follow", cache: "no-store" });
  const ended = new URL(response.url || url).origin;
  if (ended !== ORIGIN && ended !== ATTACHMENTS_ORIGIN) {
    throw new Redirected("Gmail başka bir adrese yönlendirdi");
  }
  if (!response.ok) {
    throw new HttpError(response.status);
  }
  return response;
}
