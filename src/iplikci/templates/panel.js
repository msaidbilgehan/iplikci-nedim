(() => {
  "use strict";

  // Only in the page the local panel serves (iplikci panel): adding documents.
  const PANEL = JSON.parse(document.getElementById("panel-veri").textContent);
  const $ = (id) => document.getElementById(id);

  // Same rule as the report: file names and document text only ever enter the DOM as text nodes.
  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid == null || kid === false) continue;
      e.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return e;
  }

  const MONL = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
  const mLong = (m) => `${MONL[+m.slice(5) - 1]} ${m.slice(0, 4)}`;
  const dLabel = (d) => `${d.slice(8)}.${d.slice(5, 7)}.${d.slice(0, 4)}`;
  const nf0 = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });
  const ICONS = { ok: "✓", warn: "!", fail: "✗", wait: "…", info: "·" };
  const mark = (kind, label) => h("span", { class: `mark ${kind}` },
    h("span", { class: "icon", "aria-hidden": "true", text: ICONS[kind] }), label);

  const ACCEPT = new Set(PANEL.accept);
  const extOf = (name) => {
    const i = name.lastIndexOf(".");
    return i > 0 ? name.slice(i).toLowerCase() : "";
  };
  const dialog = $("belge-dialog");
  const zone = $("birakma-alani");
  const overlay = $("birakma-katmani");
  let opener = null;
  let planId = null;
  let busy = false;

  // ------------------------------------------------------------ server calls
  // The custom header is what a cross-site page cannot send; the panel refuses writes without it.
  async function api(path, body, headers) {
    const res = await fetch(path, {
      method: "POST", body, cache: "no-store", credentials: "same-origin",
      headers: { "X-Iplikci": "1", ...(headers || {}) },
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* not JSON: report the HTTP status below */ }
    if (!res.ok) throw new Error(data.error || `Panel yanıt vermedi (HTTP ${res.status}). Terminalde panel çalışıyor mu?`);
    return data;
  }
  const postJSON = (path, value) => api(path, JSON.stringify(value), { "Content-Type": "application/json" });

  const setStatus = (text) => { $("plan-durum").textContent = text; };
  const setApply = (on) => { $("uygula").disabled = !on || busy; };

  // ----------------------------------------------------------------- dialog
  function open() {
    if (!dialog.open) {
      opener = document.activeElement;
      dialog.showModal();
      refreshPlan();
    }
  }
  dialog.addEventListener("close", () => {
    if (opener && opener.focus) opener.focus();
  });
  $("belge-kapat").addEventListener("click", () => dialog.close());

  function headerButtons() {
    const theme = $("theme");
    const add = h("button", { type: "button", class: "primary", id: "belge-ekle", onclick: open }, "Belge ekle",
      PANEL.pending ? h("span", { class: "count", text: `${PANEL.pending} bekliyor` }) : null);
    const box = h("div", { class: "top-actions" });
    theme.replaceWith(box);
    box.append(add, theme);
    const sources = document.querySelector("#card-sources .card-head");
    if (sources) sources.append(h("button", { type: "button", class: "ghost", onclick: open }, "Belge ekle"));
  }

  // ------------------------------------------------------------ choosing files
  function fromInput(input) {
    const list = Array.from(input.files || []).map((file) => ({ file, path: file.webkitRelativePath || file.name }));
    input.value = "";  // choosing the same file again must fire "change" again
    return list;
  }

  async function fromDrop(dt) {
    // Entries must be taken while the drop event runs; reading the folders can come after.
    const entries = [];
    for (const item of Array.from(dt.items || [])) {
      if (item.kind !== "file") continue;
      const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
      if (entry) entries.push(entry);
      else if (item.getAsFile()) entries.push(item.getAsFile());
    }
    const out = [];
    async function visit(entry, prefix) {
      if (entry instanceof File) { out.push({ file: entry, path: entry.name }); return; }
      if (entry.name.startsWith(".")) return;
      if (entry.isFile) {
        out.push({ file: await new Promise((res, rej) => entry.file(res, rej)), path: prefix + entry.name });
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        for (;;) {  // readEntries returns a folder in batches
          const batch = await new Promise((res, rej) => reader.readEntries(res, rej));
          if (!batch.length) break;
          for (const child of batch) await visit(child, `${prefix}${entry.name}/`);
        }
      }
    }
    for (const entry of entries) await visit(entry, "");
    return out;
  }

  // ---------------------------------------------------------------- uploads
  async function add(list) {
    const box = $("yuklemeler");
    const queue = [];
    const refused = [];
    for (const { file, path } of list) {
      const base = path.split("/").pop();
      if (base.startsWith(".")) continue;  // .DS_Store and friends
      if (!ACCEPT.has(extOf(base))) refused.push(`${path}: desteklenmeyen tür`);
      else if (file.size > PANEL.maxBytes) refused.push(`${path}: çok büyük`);
      else queue.push({ file, path, row: h("li", {}, h("span", { class: "up-name", text: path }), mark("wait", "sırada")) });
    }
    if (!queue.length && !refused.length) return;
    const ul = h("ul", { class: "up-list" }, ...queue.map((q) => q.row),
      ...refused.map((r) => h("li", {}, h("span", { class: "up-name", text: r }), mark("fail", "eklenmedi"))));
    const head = h("div", { class: "up-summary" }, h("span", { text: `${queue.length} dosya yükleniyor` }),
      refused.length ? h("span", { text: `${refused.length} dosya atlandı` }) : null);
    box.replaceChildren(head, ul);
    if (!queue.length) return;
    busy = true;
    setApply(false);
    let done = 0;
    for (const q of queue) {
      q.row.lastChild.replaceWith(mark("wait", "yükleniyor"));
      try {
        const r = await api("/api/yukle", q.file, { "X-Dosya-Adi": encodeURIComponent(q.path) });
        q.row.lastChild.replaceWith(r.status === "eklendi" ? mark("ok", "yüklendi")
          : r.status === "zaten-var" ? mark("info", "zaten gelen kutusunda") : mark("fail", r.reason || "eklenmedi"));
      } catch (err) {
        q.row.lastChild.replaceWith(mark("fail", err.message));
      }
      done += 1;
      head.firstChild.textContent = `${done}/${queue.length} dosya yüklendi`;
    }
    busy = false;
    await refreshPlan();
  }

  // ------------------------------------------------------------------- plan
  const GROUPS = [
    ["tut", "Yerine taşınacak", "ok"],
    ["hata", "Okunamadı — elle bakın", "warn"],
    ["kopya", "Kopya — çöp kutusuna", "info"],
    ["is", "Şirket belgesi — çöp kutusuna", "info"],
    ["kullanilmayan", "Kullanılmıyor — çöp kutusuna", "info"],
  ];
  const KIND_LABEL = { ekstre: "Kart ekstresi", hesap: "Hesap hareketleri", dekont: "Dekont" };

  function docLines(doc) {
    const period = doc.start ? `${dLabel(doc.start)} – ${dLabel(doc.end)}` : dLabel(doc.end);
    const check = doc.verified === true ? mark("ok", doc.check) : doc.verified === false ? mark("warn", `kontrol tutmadı: ${doc.check}`) : null;
    return [h("div", { class: "pl-meta", text: `${KIND_LABEL[doc.kind]} · ${doc.account} · ${period} · ${nf0.format(doc.rows)} işlem` }),
      check ? h("div", { class: "pl-meta" }, check) : null];
  }

  function itemRow(it) {
    const target = it.target ? h("div", { class: "pl-target" }, "→ ", h("span", { text: it.target })) : null;
    return h("li", {}, h("div", { class: "pl-name", text: it.source }), target, it.document ? docLines(it.document) : null,
      it.reason ? h("div", { class: "pl-reason", text: it.reason }) : null);
  }

  function renderPlan(p) {
    planId = p.id;
    const box = $("plan");
    if (!p.items.length) {
      box.replaceChildren(h("p", { class: "hint", text: `${PANEL.inboxName} klasöründe yerleştirilecek belge yok.` }));
      setStatus("");
      setApply(false);
      return;
    }
    const sections = GROUPS.map(([action, label, kind]) => {
      const rows = p.items.filter((it) => it.action === action);
      if (!rows.length) return null;
      return h("section", { class: "plan-group" }, h("h3", { class: "subhead first" }, mark(kind, `${label} (${rows.length})`)),
        h("ul", { class: "plan-list" }, ...rows.map(itemRow)));
    });
    box.replaceChildren(...sections.filter(Boolean));
    setStatus(p.changes ? "Hiçbir dosyaya henüz dokunulmadı. Çöp kutusuna gidenler oradan geri alınabilir."
      : "Yapılacak bir değişiklik yok.");
    setApply(p.changes > 0);
  }

  let planSeq = 0;
  async function refreshPlan() {
    const seq = ++planSeq;  // only the newest answer is shown (and applied)
    setStatus("Gelen kutusu okunuyor…");
    setApply(false);
    try {
      const p = await postJSON("/api/plan", {});
      if (seq === planSeq) renderPlan(p);
    } catch (err) {
      if (seq === planSeq) setStatus(err.message);
    }
  }

  async function applyPlan() {
    if (!planId || busy) return;
    busy = true;
    setApply(false);
    setStatus("Belgeler yerleştiriliyor, rapor yeniden üretiliyor…");
    try {
      const r = await postJSON("/api/uygula", { plan: planId });
      const parts = [`${r.filed} belge yerleştirildi`];
      if (r.trashed) parts.push(`${r.trashed} dosya çöp kutusuna taşındı`);
      if (r.unreadable) parts.push(`${r.unreadable} okunamayan belge "Okunamayan belgeler" klasörüne taşındı`);
      const text = `${parts.join(", ")}. Rapor güncellendi.`;
      setStatus(`${text} Sayfa yenileniyor…`);
      try { sessionStorage.setItem("iplikci-panel-sonuc", text); } catch (e) { /* storage unavailable: no notice after reload */ }
      setTimeout(() => location.reload(), 1200);
    } catch (err) {
      busy = false;
      setStatus(err.message);
      await refreshPlan();
    }
  }
  $("uygula").addEventListener("click", applyPlan);

  // ----------------------------------------------------------------- e-mail
  // The panel process reads the mailbox (IMAP); this page only talks to the panel.
  const dtLabel = (iso) => `${dLabel(iso.slice(0, 10))} ${iso.slice(11, 16)}`;

  function mailInfo(mail) {
    const info = $("eposta-bilgi");
    if (!mail.configured) {
      info.replaceChildren("Bankaların e-postayla gönderdiği belgeleri almak için bir kez terminalde çalıştırın: ",
        h("code", { text: "uv run iplikci eposta --kur" }));
      return;
    }
    const parts = [`E-posta: ${mail.address}`];
    if (mail.lastRun) parts.push(`son alım ${dtLabel(mail.lastRun)}`);
    info.replaceChildren(parts.join(" · "));
    if (mail.lastError) info.append(" ", mark("warn", `son deneme başarısız: ${mail.lastError.message}`));
  }

  async function fetchMail() {
    if (busy) return;
    busy = true;
    setApply(false);
    const button = $("eposta-al");
    button.disabled = true;
    const line = h("div", { class: "up-summary" }, h("span", { text: "E-postalar okunuyor…" }));
    const list = h("ul", { class: "up-list" });
    $("yuklemeler").replaceChildren(line);
    let lastRun = PANEL.mail.lastRun;
    try {
      let r = { more: true };
      for (let round = 0; r.more && round < 20; round += 1) {  // one answer covers a few hundred e-mails at most
        r = await postJSON("/api/eposta", {});
        lastRun = r.lastRun;
        line.firstChild.textContent = r.message;
        for (const name of r.copied) {
          list.append(h("li", {}, h("span", { class: "up-name", text: name }), mark("ok", "e-postadan alındı")));
        }
      }
      if (list.childNodes.length) $("yuklemeler").append(list);
    } catch (err) {
      line.firstChild.replaceWith(mark("fail", err.message));
    }
    mailInfo({ ...PANEL.mail, lastRun, lastError: null });  // this attempt's outcome is shown below it
    button.disabled = false;
    busy = false;
    await refreshPlan();
  }

  // ------------------------------------------------------- missing documents
  function renderGaps() {
    const gaps = PANEL.gaps || [];
    if (!gaps.length) return;
    $("eksikler").hidden = false;
    $("eksikler").querySelector("summary").textContent = `Eksik ya da güncel olmayan görünen belgeler (${gaps.length})`;
    $("eksik-liste").replaceChildren(...gaps.map((g) => {
      const what = g.kind === "ekstre" ? "ekstre" : "hesap dökümü";
      const parts = [`son ${what} ${dLabel(g.last)}` + (g.behind > 35 ? ` (${nf0.format(g.behind)} gün önce)` : "")];
      if (g.months.length) parts.push(`eksik aylar: ${g.months.map(mLong).join(", ")}`);
      return h("li", {}, h("strong", { text: g.account }), ` — ${parts.join("; ")}`);
    }));
  }

  // ------------------------------------------------------------ drag & drop
  const hasFiles = (ev) => Array.from((ev.dataTransfer && ev.dataTransfer.types) || []).includes("Files");
  let depth = 0;
  const leave = () => { depth = 0; overlay.hidden = true; zone.classList.remove("over"); };
  document.addEventListener("dragenter", (ev) => {
    if (!hasFiles(ev)) return;
    ev.preventDefault();
    depth += 1;
    if (dialog.open) zone.classList.add("over");
    else overlay.hidden = false;
  });
  document.addEventListener("dragover", (ev) => {
    if (!hasFiles(ev)) return;
    ev.preventDefault();
    ev.dataTransfer.dropEffect = "copy";
  });
  document.addEventListener("dragleave", (ev) => {
    if (!hasFiles(ev)) return;
    depth = Math.max(0, depth - 1);
    if (!depth) leave();
  });
  document.addEventListener("drop", (ev) => {
    if (!hasFiles(ev)) return;
    ev.preventDefault();
    leave();
    if (busy) {
      setStatus("Önceki işlem sürüyor; bitince yeniden bırakın.");
      return;
    }
    const files = fromDrop(ev.dataTransfer);
    open();
    files.then(add).catch((err) => setStatus(`Dosyalar okunamadı: ${err.message}`));
  });

  // ------------------------------------------------------------------- init
  function init() {
    $("gelen-adi").textContent = PANEL.inboxName;
    $("gelen-adi").title = PANEL.inbox;
    $("kabul").textContent = `Kabul edilenler: ${PANEL.accept.map((e) => e.slice(1).toUpperCase()).join(", ")}. ` +
      "Bir klasör seçerseniz yalnızca bu türdeki dosyalar yüklenir.";
    $("dosya-girdi").setAttribute("accept", PANEL.accept.join(","));
    $("dosya-sec").addEventListener("click", () => $("dosya-girdi").click());
    $("klasor-sec").addEventListener("click", () => $("klasor-girdi").click());
    const mail = PANEL.mail || { configured: false };
    $("eposta-al").hidden = !mail.configured;
    $("eposta-al").addEventListener("click", fetchMail);
    mailInfo(mail);
    for (const id of ["dosya-girdi", "klasor-girdi"]) {
      $(id).addEventListener("change", (ev) => {
        const chosen = fromInput(ev.target);
        if (busy) setStatus("Önceki işlem sürüyor; bitince yeniden seçin.");
        else add(chosen);
      });
    }
    headerButtons();
    renderGaps();
    $("footer").append(" Panelde kategoriler.yaml'ı değiştirdikten sonra sayfayı yenilemeniz yeterli.");
    let notice = null;
    try {
      notice = sessionStorage.getItem("iplikci-panel-sonuc");
      sessionStorage.removeItem("iplikci-panel-sonuc");
    } catch (e) { /* storage unavailable */ }
    if (notice) {
      const toast = $("bildirim");
      toast.textContent = notice;
      toast.hidden = false;
      setTimeout(() => { toast.hidden = true; }, 7000);
    }
  }

  init();
})();
