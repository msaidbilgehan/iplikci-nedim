/**
 * Gmail answered, but not in the shape a layer knows. The layer stops and the service raises `mail.bridge_alarm`
 * (ADR-0016); the fix comes with an update of the extension.
 */
export class FormatError extends Error {
  override name = "FormatError";
}
