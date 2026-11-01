-- Whether a message the extension delivered came whole (ADR-0016): Gmail's "Show original" leaves the contents of
-- attachments out, so a message read there before the extension took such messages through "Download original" holds
-- its attachments empty. 1 whole, 0 attachments left out, NULL not looked at yet. A scan asks for the incomplete ones
-- again; the whole message takes the incomplete copy's place.
ALTER TABLE bridge_messages ADD COLUMN complete INTEGER;
