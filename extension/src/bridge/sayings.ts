/**
 * İplikçi Nedim's word on the money, for the extension's window (ADR-0020). The paired service proves itself first,
 * as before every delivery and every login link; only then does the token go with the request, and the lines come
 * as the Pano has them: words and shares, never an amount, an account or a name.
 *
 * The window says nothing of the money when the extension is not paired, when nothing answers on the address, when
 * what answers is not the paired service, when the pairing was revoked, when the service is older than its lines or
 * is busy with the documents: its status card says what stands in the way, and his word comes the next time.
 */

import { type Fetcher, type Paired, type Saying, prove, sayings } from "./service";

export async function hear(service: Fetcher, paired: Paired | null): Promise<Saying[]> {
  if (paired === null) {
    return [];
  }
  try {
    await prove(service, paired);
    return await sayings(service, paired);
  } catch {
    return []; // every reason is the status card's to tell (see above): no line instead of a wrong one
  }
}
