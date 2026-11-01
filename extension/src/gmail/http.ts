/**
 * Requests to Gmail: GETs only (ADR-0016: the bridge never changes anything in Gmail), with the browser's Gmail
 * session, and never following a redirect: a redirect leaves Gmail, mostly for the sign-in page.
 */

export const ORIGIN = "https://mail.google.com";

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
