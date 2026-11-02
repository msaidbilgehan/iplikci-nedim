// The service's API from the interface: same origin, the session cookie, and on writes the header that tells the
// service the request comes from its own pages (ADR-0007). Errors arrive as problem+json with a Turkish title.

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }

  /** The session ended (or never began): the interface has to be opened again from İplikçi Nedim. */
  get signedOut(): boolean {
    return this.status === 401;
  }
}

const FALLBACK = "Servise ulaşılamadı; servis çalışıyor mu?";

interface Options {
  json?: unknown;
  body?: BodyInit;
  headers?: Record<string, string>;
}

async function request<T>(method: string, path: string, options: Options = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  const init: RequestInit = { method, headers, credentials: "same-origin" };
  if (method !== "GET") {
    headers["X-Iplikci"] = "1";
  }
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.json);
  } else if (options.body !== undefined) {
    init.body = options.body;
  }
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError(0, "unreachable", FALLBACK);
  }
  if (!response.ok) {
    throw await problemOf(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function problemOf(response: Response): Promise<ApiError> {
  try {
    const found = (await response.json()) as { code?: unknown; title?: unknown };
    const code = typeof found.code === "string" ? found.code : `http_${response.status}`;
    const title = typeof found.title === "string" ? found.title : FALLBACK;
    return new ApiError(response.status, code, title);
  } catch {
    return new ApiError(response.status, `http_${response.status}`, FALLBACK);
  }
}

export const api = {
  get: <T>(path: string): Promise<T> => request<T>("GET", path),
  post: <T>(path: string, json?: unknown): Promise<T> =>
    request<T>("POST", path, json === undefined ? {} : { json }),
  put: <T>(path: string, json: unknown): Promise<T> => request<T>("PUT", path, { json }),
  send: <T>(path: string, body: BodyInit, headers: Record<string, string>): Promise<T> =>
    request<T>("POST", path, { body, headers }),
  delete: <T = void>(path: string): Promise<T> => request<T>("DELETE", path),
};
