/**
 * Recorded-style Gmail answers built from synthetic values (ADR-0016: the adapter is tested with fake responses).
 * No real address, subject or message appears here.
 */

export const ADDRESS = "kullanici@example.com";
export const SUBJECT = "Hesap Özetiniz Hazır";
export const IK = "a1b2c3d4e5";

export interface FakeEntry {
  readonly id: bigint;
  readonly sender: string;
  readonly hexInLink?: boolean;
}

export function feedXml(entries: readonly FakeEntry[], unread = entries.length): string {
  const items = entries.map(
    (entry) => `<entry>
<title>${SUBJECT}</title>
<summary>Sayın müşterimiz, ${SUBJECT.toLowerCase()} &amp; ekte.</summary>
<link rel="alternate" href="https://mail.google.com/mail?account_id=${ADDRESS}&amp;message_id=${
      entry.hexInLink === false ? "" : entry.id.toString(16)
    }&amp;view=conv&amp;extsrc=atom" type="text/html" />
<modified>2026-10-31T09:00:00Z</modified>
<issued>2026-10-31T09:00:00Z</issued>
<id>tag:gmail.google.com,2004:${entry.id.toString()}</id>
<author>
<name>Banka</name>
<email>${entry.sender}</email>
</author>
</entry>`,
  );
  return `<?xml version="1.0" encoding="UTF-8"?>
<feed version="0.3" xmlns="http://purl.org/atom/ns#">
<title>Gmail - Inbox for ${ADDRESS}</title>
<tagline>New messages in your Gmail Inbox</tagline>
<fullcount>${unread}</fullcount>
<link rel="alternate" href="https://mail.google.com/mail" type="text/html" />
<modified>2026-10-31T09:00:00Z</modified>
${items.join("\n")}
</feed>`;
}

export interface FakeMessage {
  readonly from: string;
  /** The topmost Authentication-Results; null leaves it out. */
  readonly authentication?: string | null;
}

export function rawMessage(message: FakeMessage): string {
  const domain = message.from.slice(message.from.lastIndexOf("@") + 1).replace(/>$/, "");
  const authentication =
    message.authentication === undefined
      ? `mx.google.com;\r\n       dkim=pass header.i=@${domain} header.s=s1;\r\n       spf=pass smtp.mailfrom=${domain};\r\n       dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=${domain}`
      : message.authentication;
  const lines = [
    `Delivered-To: ${ADDRESS}`,
    "Received: by 2002:a05:6400::1 with SMTP id x1; Sat, 31 Oct 2026 02:00:00 -0700 (PDT)",
  ];
  if (authentication !== null) {
    lines.push(`Authentication-Results: ${authentication}`);
  }
  lines.push(
    "Received: from mail.example.net (mail.example.net [192.0.2.1]) by mx.google.com",
    "Authentication-Results: mail.example.net; dmarc=pass header.from=example.net",
    `From: Banka <${message.from}>`,
    `To: ${ADDRESS}`,
    `Subject: =?UTF-8?Q?Hesap_=C3=96zetiniz_Haz=C4=B1r?=`,
    "Message-ID: <fake-1@example.net>",
    "MIME-Version: 1.0",
    'Content-Type: text/plain; charset="UTF-8"',
    "",
    "Sayın müşterimiz, ekstreniz ektedir.",
    "",
  );
  return lines.join("\r\n");
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export function originalPage(raw: string, id: bigint, withDownload = true): string {
  const download = withDownload
    ? `<a href="?ui=2&amp;ik=${IK}&amp;attid=0&amp;permmsgid=msg-f:${id}&amp;view=att&amp;disp=comp&amp;safe=1&amp;zw" class="download-link">Download Original</a>`
    : "";
  return `<!DOCTYPE html><html><head><title>Original Message</title></head><body>
<table><tr><td>Message ID</td><td>&lt;fake-1@example.net&gt;</td></tr></table>
<div>${download}<a href="#" id="copy">Copy to clipboard</a></div>
<pre class="raw_message_text" id="raw_message_text">
${escapeHtml(raw)}</pre>
</body></html>`;
}

export function gmailPage(ik: string): string {
  return `<!DOCTYPE html><html><head><script>var GLOBALS=[null,null,1234567,"a,b",[1,[2,"]"],3],{"k":"v"},
"tr",'x\\'y',0,"${ik}",null,"${ADDRESS}"];</script></head><body></body></html>`;
}

export function threadList(hexIds: readonly string[]): string {
  return `)]}'\n[["tb",0,[${hexIds.map((id) => `["${id}","${id}",1]`).join(",")}]]]`;
}
