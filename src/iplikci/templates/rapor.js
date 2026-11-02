(() => {
  "use strict";

  const DATA = JSON.parse(document.getElementById("veri").textContent);
  const NS = "http://www.w3.org/2000/svg";
  const ROOT = document.querySelector(".viz-root");

  // ---------------------------------------------------------------- helpers
  const $ = (id) => document.getElementById(id);

  // All text from statements is untrusted: it only ever enters the DOM as text nodes.
  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k === "style") Object.assign(e.style, v);
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid == null || kid === false) continue;
      e.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return e;
  }

  function s(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v != null) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  }

  function stext(parent, x, y, str, attrs) {
    const t = s("text", { x, y, ...(attrs || {}) }, parent);
    t.textContent = str;
    return t;
  }

  const nf0 = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });
  const nf2 = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const nfc = new Intl.NumberFormat("tr-TR", { notation: "compact", maximumFractionDigits: 1 });
  const nfp = new Intl.NumberFormat("tr-TR", { style: "percent", maximumFractionDigits: 1 });
  const minus = (v) => (v < 0 ? "−" : "");
  const tl = (v) => minus(Math.round(v)) + nf0.format(Math.abs(v)) + " TL";
  const tl2 = (v) => minus(v) + nf2.format(Math.abs(v)) + " TL";
  const tlc = (v) => minus(v) + nfc.format(Math.abs(v)) + " TL";
  const MON = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
  const MONL = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
  const mShort = (m) => `${MON[+m.slice(5) - 1]} ${m.slice(2, 4)}`;
  const mLong = (m) => `${MONL[+m.slice(5) - 1]} ${m.slice(0, 4)}`;
  const dLabel = (d) => `${d.slice(8)}.${d.slice(5, 7)}.${d.slice(0, 4)}`;
  const addMonths = (m, n) => {
    const total = +m.slice(0, 4) * 12 + (+m.slice(5) - 1) + n;
    return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
  };
  const monthDiff = (a, b) => (+b.slice(0, 4) - +a.slice(0, 4)) * 12 + (+b.slice(5) - +a.slice(5));
  const monthsBetween = (a, b) => {
    const out = [];
    for (let m = a; m <= b; m = addMonths(m, 1)) out.push(m);
    return out;
  };
  const sum = (arr, f = (x) => x) => arr.reduce((a, x) => a + f(x), 0);
  const lower = (str) => str.toLocaleLowerCase("tr");

  // ------------------------------------------------------------------ data
  const ACC = DATA.accounts;
  const CAT = DATA.categories;
  const GRP = DATA.groups;
  const KIND = DATA.kinds;
  const LEVELS = DATA.levels;
  const KIND_ID = KIND.map((k) => k.id);
  const OTHER_GROUP = GRP.length - 1;
  const LEVEL_IDX = Object.fromEntries(LEVELS.map((l, i) => [l.name, i]));
  const UNSURE = LEVEL_IDX["Belirsiz"];
  // lv: necessity level used by charts and filters; rows without one count as "Belirsiz".
  const TX = DATA.tx.map((r) => ({
    ...r, mo: r.d.slice(0, 7), g: CAT[r.c].group, kid: KIND_ID[r.k], lv: r.n >= 0 ? r.n : UNSURE,
    hay: lower(`${r.m} ${r.t}`),
  }));
  const slotColor = (slot) => (slot ? `var(--s${slot})` : "var(--other)");
  const groupColor = (gi) => slotColor(GRP[gi].slot);
  const levelColor = (li) => slotColor(LEVELS[li].slot);
  const DEFAULT_KINDS = KIND.filter((k) => k.on).map((k) => k.id);
  // Income is only known for months that bank account movement lists cover: not cards, loans or a brokerage account.
  const NOT_BANK_ACCOUNTS = new Set(["Kredi kartı", "Banka kartı", "Kredi", "Yatırım hesabı"]);
  const INCOME_MONTHS = new Set();
  ACC.forEach((a, i) => {
    if (NOT_BANK_ACCOUNTS.has(a.type)) return;
    for (const [m, v] of Object.entries(DATA.coverage[i] || {})) if (v >= 0.5) INCOME_MONTHS.add(m);
  });
  // Interpretation computed by the program (insights.py): complete months, regular payments,
  // habits, balances, findings and steps.
  const INS = DATA.insights;
  const LAST_COMPLETE = INS.lastComplete;
  const WINDOW = INS.window;
  const SERIES = INS.series;
  const windowText = () => `${mShort(WINDOW[0])} – ${mShort(WINDOW.at(-1))}`;

  // ----------------------------------------------------------------- state
  const DEFAULT_PRESET = "12";
  const state = {
    preset: DEFAULT_PRESET, from: null, to: null,
    accounts: null, kinds: new Set(DEFAULT_KINDS), cats: null, levels: null, merchant: null, q: "",
    provisional: false, // only the rows receipts brought before their statement
    sort: { key: "d", dir: -1 }, page: 0,
  };
  const views = {};

  const inScope = (t) => !state.accounts || state.accounts.has(t.a);

  function extent() {
    let lo = null, hi = null;
    for (const t of TX) {
      if (!inScope(t)) continue;
      if (!lo || t.mo < lo) lo = t.mo;
      if (!hi || t.mo > hi) hi = t.mo;
    }
    return [lo, hi];
  }

  function period() {
    const [lo, hi] = extent();
    if (!lo) return [null, null];
    const clamp = (m) => (m < lo ? lo : m);
    switch (state.preset) {
      case "all": return [lo, hi];
      case "3": case "6": case "12": return [clamp(addMonths(hi, 1 - +state.preset)), hi];
      case "ytd": return [clamp(`${hi.slice(0, 4)}-01`), hi];
      case "lastyear": { const y = +hi.slice(0, 4) - 1; return [`${y}-01`, `${y}-12`]; }
      default: return [state.from || lo, state.to || hi];
    }
  }

  /* Filtered transactions. opts.kinds overrides the kind filter (income for the
     cash-flow card); opts.allCats ignores the category and necessity filters. */
  function select(opts = {}) {
    const P = opts.period || period();
    const out = [];
    if (!P[0]) return out;
    for (const t of TX) {
      if (!inScope(t)) continue;
      if (t.mo < P[0] || t.mo > P[1]) continue;
      if (opts.kinds ? !opts.kinds.includes(t.kid) : !state.kinds.has(t.kid)) continue;
      if (!opts.allCats && state.cats && !state.cats.has(t.c)) continue;
      if (!opts.allCats && state.levels && !state.levels.has(t.lv)) continue;
      if (state.merchant && t.m !== state.merchant) continue;
      if (state.provisional && !t.p) continue;
      if (state.q && !t.hay.includes(state.q)) continue;
      out.push(t);
    }
    return out;
  }

  // --------------------------------------------------------------- tooltip
  const tip = $("tooltip");
  function showTip(content, x, y) {
    tip.replaceChildren(...content);
    tip.hidden = false;
    const r = tip.getBoundingClientRect();
    let left = x + 14, top = y + 14;
    if (left + r.width > window.innerWidth - 8) left = x - r.width - 14;
    if (top + r.height > window.innerHeight - 8) top = y - r.height - 14;
    tip.style.left = `${Math.max(8, left)}px`;
    tip.style.top = `${Math.max(8, top)}px`;
  }
  const hideTip = () => { tip.hidden = true; };
  const tipAt = (el, content) => {
    const r = el.getBoundingClientRect();
    showTip(content, r.left + r.width / 2, r.top + Math.min(r.height, 40));
  };
  const ttTitle = (str) => h("div", { class: "tt-title", text: str });
  const ttRow = (value, label, color) =>
    h("div", { class: "tt-row" },
      color ? h("i", { class: "key", style: { background: color } }) : null,
      h("strong", { text: value }), h("span", { text: label }));
  const ttNote = (str) => h("div", { class: "tt-note", text: str });

  function hoverable(el, content, onActivate) {
    el.addEventListener("pointermove", (ev) => showTip(content(), ev.clientX, ev.clientY));
    el.addEventListener("pointerleave", hideTip);
    el.addEventListener("focus", () => tipAt(el, content()));
    el.addEventListener("blur", hideTip);
    if (onActivate) {
      el.addEventListener("click", onActivate);
      el.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); onActivate(); }
      });
    }
  }

  const swatch = (color) => h("span", { class: "swatch", style: { background: color } });

  // -------------------------------------------------------------- filters
  const PRESETS = [["3", "Son 3 ay"], ["6", "Son 6 ay"], ["12", "Son 12 ay"], ["ytd", "Bu yıl"], ["lastyear", "Geçen yıl"], ["all", "Tümü"]];

  function buildStaticFilters() {
    $("presets").replaceChildren(...PRESETS.map(([id, label]) =>
      h("button", { type: "button", "data-id": id, onclick: () => { state.preset = id; update(); } }, label)));
    for (const id of ["from", "to"]) {
      $(id).addEventListener("change", () => {
        const [lo, hi] = period();
        state.from = $("from").value || lo;
        state.to = $("to").value || hi;
        if (state.from > state.to) [state.from, state.to] = [state.to, state.from];
        state.preset = null;
        update();
      });
    }
    let timer;
    $("q").addEventListener("input", (ev) => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.q = lower(ev.target.value.trim()); update(); }, 200);
    });
    $("reset").addEventListener("click", () => {
      Object.assign(state, {
        preset: DEFAULT_PRESET, from: null, to: null, accounts: null, kinds: new Set(DEFAULT_KINDS),
        cats: null, levels: null, merchant: null, q: "", provisional: false,
      });
      $("q").value = "";
      update();
    });
    document.addEventListener("click", (ev) => {
      for (const d of document.querySelectorAll("details.dd[open]")) if (!d.contains(ev.target)) d.open = false;
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") for (const d of document.querySelectorAll("details.dd[open]")) d.open = false;
    });
    for (const seg of document.querySelectorAll("[data-view-for]")) {
      const card = $(seg.dataset.viewFor);
      for (const b of seg.querySelectorAll("button")) {
        b.addEventListener("click", () => {
          views[card.id] = b.dataset.view;
          for (const x of seg.querySelectorAll("button")) x.setAttribute("aria-pressed", String(x === b));
          for (const v of card.querySelectorAll(".view")) v.hidden = v.dataset.view !== b.dataset.view;
          if (b.dataset.view === "chart") update();
        });
      }
    }
  }

  function menuHead(title, actions) {
    return h("div", { class: "mhead" }, h("span", { class: "muted", text: title }),
      h("span", {}, ...actions.map(([label, fn], i) => [i ? " · " : "", h("button", { type: "button", onclick: fn }, label)])));
  }

  function toggleIn(current, all, ids, on) {
    const set = current ? new Set(current) : new Set(all);
    for (const id of ids) on ? set.add(id) : set.delete(id);
    return set.size === all.length ? null : set;
  }

  function renderPeriod(P) {
    for (const b of $("presets").children) b.setAttribute("aria-pressed", String(b.dataset.id === state.preset));
    const [lo, hi] = extent();
    const months = lo ? monthsBetween(lo, hi) : [];
    for (const [id, value] of [["from", P[0]], ["to", P[1]]]) {
      const sel = $(id);
      sel.replaceChildren(...months.map((m) => h("option", { value: m, text: mLong(m) })));
      if (value && !months.includes(value)) sel.append(h("option", { value, text: mLong(value) }));
      sel.value = value || "";
    }
  }

  function renderAccountMenu() {
    const all = ACC.map((_, i) => i);
    const checked = (i) => !state.accounts || state.accounts.has(i);
    const items = [menuHead("Hesaplar ve kartlar", [["Tümü", () => { state.accounts = null; update(); }], ["Hiçbiri", () => { state.accounts = new Set(); update(); }]])];
    let bank = null;
    ACC.forEach((a, i) => {
      if (a.bank !== bank) { bank = a.bank; items.push(h("div", { class: "gname", style: { padding: "6px 8px 2px" }, text: bank })); }
      items.push(h("label", { class: "indent" },
        h("input", { type: "checkbox", checked: checked(i), onchange: (ev) => { state.accounts = toggleIn(state.accounts, all, [i], ev.target.checked); update(); } }),
        h("span", { text: a.label.replace(`${a.bank} `, "") }), h("span", { class: "note", text: a.type })));
    });
    $("dd-accounts").querySelector(".menu").replaceChildren(...items);
    const n = all.filter(checked).length;
    $("dd-accounts").querySelector("summary").textContent = `Hesaplar: ${n === ACC.length ? "Tümü" : `${n}/${ACC.length}`}`;
  }

  function renderKindMenu() {
    $("dd-kinds").querySelector(".menu").replaceChildren(
      menuHead("İşlem türleri", [
        ["Varsayılan", () => { state.kinds = new Set(DEFAULT_KINDS); update(); }],
        ["Tümü", () => { state.kinds = new Set(KIND_ID); update(); }],
      ]),
      ...KIND.map((k) => h("label", {},
        h("input", { type: "checkbox", checked: state.kinds.has(k.id), onchange: (ev) => {
          ev.target.checked ? state.kinds.add(k.id) : state.kinds.delete(k.id);
          update();
        } }),
        h("span", { text: k.label }), k.on ? h("span", { class: "note", text: "gider" }) : null)),
      h("p", { class: "muted", style: { margin: "6px 8px 2px", maxWidth: "320px", fontSize: "12px" },
        text: "Varsayılan olarak yalnızca harcama, iade ve faiz/ücretler gider sayılır. Kişilere gönderilen para, borç anaparası, nakit avans, kart ödemeleri ve kendi hesaplarınız arası transferler ayrı tutulur; eklerseniz bazı tutarlar iki kez sayılabilir." }),
    );
    const isDefault = state.kinds.size === DEFAULT_KINDS.length && DEFAULT_KINDS.every((k) => state.kinds.has(k));
    $("dd-kinds").querySelector("summary").textContent = `İşlem türü: ${isDefault ? "Giderler" : `${state.kinds.size}/${KIND.length}`}`;
  }

  function renderCategoryMenu() {
    const all = CAT.map((_, i) => i);
    const checked = (ci) => !state.cats || state.cats.has(ci);
    const toggle = (ids, on) => { state.cats = toggleIn(state.cats, all, ids, on); update(); };
    const items = [menuHead("Kategoriler", [["Tümü", () => { state.cats = null; update(); }], ["Hiçbiri", () => { state.cats = new Set(); update(); }]])];
    GRP.forEach((g, gi) => {
      const ids = all.filter((ci) => CAT[ci].group === gi);
      if (!ids.length) return;
      const on = ids.filter(checked).length;
      const box = h("input", { type: "checkbox", checked: on === ids.length, onchange: (ev) => toggle(ids, ev.target.checked) });
      box.indeterminate = on > 0 && on < ids.length;
      items.push(h("label", { class: "gname" }, box, swatch(groupColor(gi)), h("span", { text: g.name })));
      for (const ci of ids) {
        items.push(h("label", { class: "indent" },
          h("input", { type: "checkbox", checked: checked(ci), onchange: (ev) => toggle([ci], ev.target.checked) }),
          h("span", { text: CAT[ci].name })));
      }
    });
    $("dd-categories").querySelector(".menu").replaceChildren(...items);
    $("dd-categories").querySelector("summary").textContent =
      `Kategori: ${!state.cats ? "Tümü" : state.cats.size === 1 ? CAT[[...state.cats][0]].name : `${state.cats.size} seçili`}`;
  }

  const levelNames = () => [...state.levels].sort().map((l) => LEVELS[l].name).join(", ") || "—";

  function renderLevelMenu() {
    const all = LEVELS.map((_, i) => i);
    $("dd-levels").querySelector(".menu").replaceChildren(
      menuHead("Gereklilik", [["Tümü", () => { state.levels = null; update(); }]]),
      ...LEVELS.map((l, li) => h("label", {},
        h("input", { type: "checkbox", checked: !state.levels || state.levels.has(li), onchange: (ev) => {
          state.levels = toggleIn(state.levels, all, [li], ev.target.checked);
          update();
        } }), swatch(levelColor(li)), h("span", { text: l.name }))),
    );
    $("dd-levels").querySelector("summary").textContent = `Gereklilik: ${state.levels ? levelNames() : "Tümü"}`;
  }

  // Chips for filters that were set by clicking the charts.
  function renderChips(P) {
    const chips = [];
    if (state.merchant) chips.push(["İşyeri", state.merchant, () => { state.merchant = null; update(); }]);
    if (state.cats && state.cats.size && state.cats.size <= 3) {
      chips.push(["Kategori", [...state.cats].map((ci) => CAT[ci].name).join(", "), () => { state.cats = null; update(); }]);
    }
    if (state.levels) chips.push(["Gereklilik", levelNames(), () => { state.levels = null; update(); }]);
    if (state.provisional) chips.push(["Durum", "Geçici kayıtlar", () => { state.provisional = false; update(); }]);
    if (!state.preset && P[0] && P[0] === P[1]) chips.push(["Ay", mLong(P[0]), () => { state.preset = DEFAULT_PRESET; update(); }]);
    $("chips").replaceChildren(...chips.map(([k, v, fn]) => h("span", { class: "chip" },
      h("span", { class: "muted", text: `${k}:` }), h("span", { text: v }),
      h("button", { type: "button", "aria-label": `${k} filtresini kaldır`, onclick: fn }, "×"))));
  }

  function renderFilters(P) {
    renderPeriod(P);
    renderAccountMenu();
    renderKindMenu();
    renderCategoryMenu();
    renderLevelMenu();
    renderChips(P);
  }

  // ----------------------------------------------------------------- KPIs
  function monthlyTotals(F) {
    const map = new Map();
    for (const t of F) map.set(t.mo, (map.get(t.mo) || 0) + t.v);
    return map;
  }

  function sparkline(values) {
    const W = 160, H = 30, svg = s("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, "aria-hidden": "true" });
    if (values.length < 2) return svg;
    const max = Math.max(...values), min = Math.min(0, ...values);
    const x = (i) => 2 + (i / (values.length - 1)) * (W - 8);
    const y = (v) => H - 4 - ((v - min) / (max - min || 1)) * (H - 8);
    s("polyline", { points: values.map((v, i) => `${x(i)},${y(v)}`).join(" "), fill: "none", style: "stroke:var(--muted)", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    s("circle", { cx: x(values.length - 1), cy: y(values.at(-1)), r: 4, style: "fill:var(--accent);stroke:var(--surface)", "stroke-width": 2 }, svg);
    return svg;
  }

  function tile(label, value, meta, extra, hero) {
    return h("div", { class: `tile${hero ? " hero" : ""}` },
      h("div", { class: "label", text: label }), h("div", { class: "value", text: value }),
      meta ? h("div", { class: "meta", text: meta }) : null, extra || null);
  }

  // Income in the months of P that account movement lists cover.
  function incomeIn(P) {
    const months = P[0] ? monthsBetween(P[0], P[1]).filter((m) => INCOME_MONTHS.has(m)) : [];
    const rows = months.length ? select({ period: [months[0], months.at(-1)], kinds: ["gelir"], allCats: true }) : [];
    return { months, income: -sum(rows.filter((t) => INCOME_MONTHS.has(t.mo)), (t) => t.v) };
  }

  function renderKPIs(F, P) {
    const total = sum(F, (t) => t.v);
    const byMonth = monthlyTotals(F);
    const months = [...byMonth.keys()].sort();
    // Months after the last complete one are cut short by card statement dates; averages skip them.
    const full = months.filter((m) => m <= LAST_COMPLETE);
    const avgMonths = full.length ? full : months;
    const n = avgMonths.length;
    const avgTotal = sum(avgMonths, (m) => byMonth.get(m));
    const skipped = months.length - avgMonths.length;
    const isDefault = state.kinds.size === DEFAULT_KINDS.length && DEFAULT_KINDS.every((k) => state.kinds.has(k));
    const avoidable = sum(F.filter((t) => t.lv === LEVEL_IDX["Gereksiz"]), (t) => t.v);
    const { months: incMonths, income } = incomeIn(P);
    const spentThen = sum(F.filter((t) => incMonths.includes(t.mo)), (t) => t.v);
    const tiles = [
      tile(isDefault ? "Toplam gider" : "Toplam (seçili işlem türleri)", tl(total),
        P[0] ? `${mShort(P[0])} – ${mShort(P[1])} · ${nf0.format(F.length)} işlem` : "Veri yok", null, true),
      tile("Aylık ortalama gider", tl(n ? avgTotal / n : 0),
        n ? `${n} tam ay üzerinden${skipped ? ` · eksik ${skipped === 1 ? "son ay" : `son ${skipped} ay`} dahil değil` : ""}` : "—",
        sparkline(months.slice(-24).map((m) => byMonth.get(m)))),
      tile("Aylık ortalama gelir", incMonths.length ? tl(income / incMonths.length) : "—",
        !incMonths.length ? "Bu dönemde hesap hareketi yok"
          : income > 0 ? `hesap hareketi olan ${incMonths.length} ay · giderler gelirin ${nfp.format(spentThen / income)} kadarı` : `hesap hareketi olan ${incMonths.length} ay`),
      tile("Gereksiz harcamalar", tl(avoidable), total > 0 ? `faiz, gecikme ve banka ücretleri · giderlerin ${nfp.format(avoidable / total)} kadarı` : "faiz, gecikme ve banka ücretleri"),
    ];
    if (n) {
      const last = months.at(-1);
      const prev = months.slice(-4, -1);
      const lastV = byMonth.get(last);
      let delta = null;
      if (prev.length) {
        const base = sum(prev, (m) => byMonth.get(m)) / prev.length;
        if (base > 0) {
          const d = (lastV - base) / base;
          const up = d >= 0;
          delta = h("div", { class: `delta ${up ? "up" : "down"}` },
            h("span", { class: "icon", text: up ? "▲ " : "▼ " }),
            `önceki ${prev.length} ayın ortalamasından ${nfp.format(Math.abs(d))} ${up ? "fazla" : "az"}`);
        }
      }
      const partial = last === extent()[1] ? " · ekstreler kesim tarihinde bittiği için eksik olabilir" : "";
      tiles.push(tile("Son ay", tl(lastV), `${mLong(last)}${partial}`, delta));
    }
    $("kpis").replaceChildren(...tiles);
  }

  function renderExcluded(P) {
    const optional = ["kisiye_transfer", "kredi_anapara", "nakit_avans", "ekstresiz_kart"].filter((k) => !state.kinds.has(k));
    const rows = optional.length ? select({ kinds: optional, period: P }) : [];
    const parts = [];
    for (const k of optional) {
      const v = sum(rows.filter((t) => t.kid === k), (t) => t.v);
      if (Math.abs(v) < 1) continue;
      parts.push(h("button", { type: "button", title: "Toplama ekle", onclick: () => { state.kinds.add(k); update(); } },
        `+ ${KIND[KIND_ID.indexOf(k)].label}: ${tl(v)}`));
    }
    $("excluded").replaceChildren(...(parts.length ? [h("span", { text: "Toplama dahil değil:" }), ...parts] : []));
  }

  // -------------------------------------------------------- interpretation
  /* Findings, steps, the monthly plan and balances come ready from the program (insights.py);
     they describe the whole picture, so the filters do not change them. A finding can open the
     transactions behind it. */
  const TONES = { dikkat: ["!", "Dikkat"], iyi: ["✓", "İyi"], bilgi: ["i", "Bilgi"] };
  const signed = (v) => (v > 0.5 ? "+" : "") + tl(v);

  function showTransactions(filter) {
    Object.assign(state, {
      preset: DEFAULT_PRESET, from: null, to: null, accounts: null, kinds: new Set(DEFAULT_KINDS),
      cats: null, levels: null, merchant: null, q: "", provisional: false,
    });
    $("q").value = "";
    if (filter.kind) state.kinds = new Set([filter.kind]);
    // Provisional rows are mostly transfers, income and card payments: every kind is shown.
    if (filter.provisional) Object.assign(state, { provisional: true, kinds: new Set(KIND_ID) });
    if (filter.merchant) state.merchant = filter.merchant;
    if (filter.category) {
      const ci = CAT.findIndex((c) => c.name === filter.category);
      if (ci >= 0) state.cats = new Set([ci]);
    }
    update();
    $("card-transactions").scrollIntoView({ block: "start" });
  }

  function renderInsights() {
    const partial = addMonths(LAST_COMPLETE, 1);
    $("insights-hint").textContent = `${WINDOW.length} tam ay (${windowText()}) üzerinden. ${mLong(partial)} kart ekstreleri ` +
      `kesim tarihlerinde bittiği için eksik ve ortalamalara katılmadı. Bakiyeler ${dLabel(INS.asOf)} itibarıyla. Filtrelerden bağımsızdır.`;
    $("findings").replaceChildren(...INS.findings.map((f) => h("li", { class: "finding" },
      h("span", { class: `tone ${f.tone}` }, h("span", { class: "icon", "aria-hidden": "true", text: TONES[f.tone][0] }), TONES[f.tone][1]),
      h("div", {}, h("strong", { text: f.title }), h("p", { text: f.text }),
        Object.keys(f.filter).length
          ? h("button", { type: "button", class: "link", onclick: () => showTransactions(f.filter) }, "İşlemleri göster")
          : null))));
    $("steps").replaceChildren(...INS.steps.map((st) => h("li", {},
      h("div", { class: "step-head" }, h("strong", { text: st.title }),
        st.monthly >= 1 ? h("span", { class: "gain", text: `ayda ~${tl(st.monthly)}` }) : null),
      h("p", { text: st.text }))));
    renderBudget();
  }

  function renderBudget() {
    const lines = INS.budget;
    if (!lines.length) { $("budget").replaceChildren(h("p", { class: "empty", text: "Bütçe için düzenli gelir bulunamadı." })); return; }
    $("budget-hint").textContent = "Bugün: sabit ödemeler son tutarlarıyla, değişken harcamalar son 6 tam ayın orta (medyan) ayıyla; " +
      "yani bugünkü fiyatlarla tipik bir ay. Öneri: faiz ve ücretler sıfır, isteğe bağlı harcamada aylık sınır. Kişilere ve borca " +
      "giden para düzensiz olduğu için ortalamasıyla aynen bırakıldı.";
    const income = lines[0].now;
    const columns = [
      { key: "label", label: "Kalem" }, { key: "now", label: "Bugün", num: true }, { key: "share", label: "Gelire oranı", num: true },
      { key: "plan", label: "Öneri", num: true }, { key: "diff", label: "Fark", num: true }, { key: "note", label: "Not" },
    ];
    const cells = (b, i) => ({
      label: b.label, now: tl(b.now), share: i && income > 0 ? minus(b.now) + nfp.format(Math.abs(b.now / income)) : "–", plan: tl(b.plan),
      diff: Math.abs(b.plan - b.now) >= 1 ? signed(b.plan - b.now) : "–", note: h("span", { class: "muted small", text: b.note }),
    });
    const last = lines.at(-1);
    const lastCells = cells(last, lines.length - 1);
    const foot = h("tr", {}, ...columns.map((c) => h("td", { class: c.num ? "num" : null }, lastCells[c.key])));
    $("budget").replaceChildren(sortableTable(columns, lines.slice(0, -1).map((b, i) => ({ cells: cells(b, i) })), { foot }));
  }

  const HOLD_KIND = {
    nakit: "Vadesiz hesap", vadeli: "Vadeli hesap", doviz: "Döviz", yatirim: "Hisse senedi", altin: "Altın",
    kmh: "Ek hesap (KMH)", kart: "Kredi kartı",
  };

  function renderHoldings() {
    const H = INS.holdings;
    if (!H.length) { $("card-holdings").hidden = true; return; }
    const value = (kinds) => sum(H.filter((x) => kinds.includes(x.kind)), (x) => x.value || 0);
    const cash = value(["nakit", "vadeli", "doviz"]), term = value(["vadeli"]), stocks = value(["yatirim"]);
    const overdraft = -value(["kmh"]), cards = -value(["kart"]);
    const gold = H.filter((x) => x.kind === "altin" && x.amount > 0.001);
    const grams = sum(gold, (x) => x.amount), goldCost = sum(gold, (x) => x.cost);
    const goldText = grams ? `altın ${nf2.format(grams)} gr${goldCost ? ` (alışta ${tl(goldCost)})` : ""}` : "altın hesabı yok";
    const shown = H.filter((x) => Math.abs(x.amount) >= 0.5);
    $("holdings-hint").textContent = "Hesap dökümlerinin son günündeki bakiyeler; kartlarda son ekstre borcu, sonrasında hesaplardan " +
      "yapılan ödemeler düşülerek. Döviz, belgelerde bulunan en son kurla TL'ye çevrildi; hisse senetleri yatırım hesabı " +
      "ekstresinin yazdığı piyasa değeriyle; altının güncel fiyatı belgelerde olmadığı için alışta ödenen tutar gösterildi. " +
      "Son belgesi altı aydan eski bir hesabın bakiyesi toplamlara katılmadı." +
      `${H.length > shown.length ? ` Bakiyesi sıfır olan ${H.length - shown.length} hesap listede yok.` : ""}`;
    $("holdings-tiles").replaceChildren(
      tile("Nakit ve döviz", tl(cash),
        `vadesiz TL ${tl(value(["nakit"]))}${term ? ` · vadeli ${tl(term)}` : ""} · döviz ${tl(value(["doviz"]))}`),
      stocks
        ? tile("Hisse senedi ve altın", tl(stocks), `hisseler piyasa değeriyle · ${goldText}`)
        : tile("Altın", grams ? `${nf2.format(grams)} gr` : "—", goldCost ? `alışta ödenen ${tl(goldCost)}` : "altın hesabı yok"),
      tile("Ek hesap ve kart borcu", tl(overdraft + cards), `ek hesap ${tl(overdraft)} · kart ${tl(cards)}`),
      tile("Net durum", tl(cash + stocks + goldCost - overdraft - cards),
        stocks ? "hisseler piyasa değeriyle, altın alış tutarıyla, BES hariç" : "altın alış tutarıyla, BES hariç"),
    );
    const columns = [
      { key: "label", label: "Hesap" }, { key: "kind", label: "Tür" }, { key: "amount", label: "Bakiye", num: true },
      { key: "value", label: "TL karşılığı", num: true }, { key: "asOf", label: "Tarih", num: true }, { key: "note", label: "Not" },
    ];
    $("holdings").replaceChildren(sortableTable(columns, shown.map((x) => ({
      cells: {
        label: x.label, kind: HOLD_KIND[x.kind],
        amount: x.cur === "TL" ? tl2(x.amount) : `${minus(x.amount)}${nf2.format(Math.abs(x.amount))} ${x.cur}`,
        value: x.value == null ? "–" : tl(x.value), asOf: dLabel(x.asOf), note: h("span", { class: "muted small", text: x.note }),
      },
    }))));
  }

  // --------------------------------------------------------------- closing
  /* Month-end closing (month_end.py): which months the statements closed and what an open one waits
     for. Like the interpretation it describes the whole picture, so the filters do not change it. */
  const CLOSING_TONE = {
    kapandi: ["iyi", "✓"], bekleniyor: ["bekle", "…"], suruyor: ["bekle", "…"],
    eksik: ["dikkat", "!"], kontrol: ["dikkat", "!"],
  };

  function renderClosing() {
    const rows = DATA.closing || [];
    if (!rows.length) { $("card-closing").hidden = true; return; }
    $("closing-hint").textContent = "Bir ay, bütün hesapların ekstresi ya da hesap dökümü ayın tamamını " +
      "kapsayıp tutarlı çıkınca ve dekontlar ekstrelerde bulununca kapanır. Ekstresi henüz gelmemiş " +
      "günlerin dekontları geçici olarak işlenir. Filtrelerden bağımsızdır.";
    const columns = [
      { key: "m", label: "Ay" }, { key: "status", label: "Durum" }, { key: "expense", label: "Gider", num: true },
      { key: "income", label: "Gelir", num: true }, { key: "left", label: "Kalan", num: true },
      { key: "open", label: "Bekleyen ya da kontrol edilecek" }, { key: "file", label: "Ay sonu raporu" },
    ];
    const money = (v) => (v == null ? "–" : tl(v));
    $("closing").replaceChildren(sortableTable(columns, rows.slice().reverse().map((r) => {
      const [tone, icon] = CLOSING_TONE[r.status];
      const extra = [r.provisional ? `${r.provisional} geçici kayıt` : null,
        r.unmatched ? `${r.unmatched} dekont ekstrede yok` : null].filter(Boolean);
      const open = r.open.length ? r.open.map((o) => h("div", { text: o }))
        : [h("span", { class: "muted", text: r.status === "kapandi" ? "—" : r.summary })];
      return {
        cells: {
          m: mLong(r.m),
          status: h("span", { class: `tone ${tone}` },
            h("span", { class: "icon", "aria-hidden": "true", text: icon }), r.label),
          expense: tl(r.expense), income: money(r.income), left: money(r.left),
          open: h("div", { class: "small" }, ...open,
            extra.length ? h("div", { class: "muted", text: extra.join(" · ") }) : null),
          file: h("a", { href: r.file, text: "Aç", "aria-label": `${mLong(r.m)} ay sonu raporunu aç` }),
        },
      };
    })));
  }

  // ------------------------------------------------------- column charts
  function niceTicks(lo, hi, count) {
    if (hi <= lo) hi = lo + 1;
    const raw = (hi - lo) / count;
    const mag = 10 ** Math.floor(Math.log10(raw));
    const err = raw / mag;
    const step = (err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1) * mag;
    const out = [];
    for (let v = Math.floor(lo / step) * step; v <= Math.ceil(hi / step) * step + step / 2; v += step) {
      out.push(Math.round(v * 100) / 100);
    }
    return out;
  }

  // Bar with a 4px rounded data end and a square baseline end.
  function barPath(x, y, w, hgt, r, roundTop) {
    r = Math.max(0, Math.min(r, w / 2, hgt));
    if (roundTop) return `M${x},${y + hgt}V${y + r}A${r},${r} 0 0 1 ${x + r},${y}H${x + w - r}A${r},${r} 0 0 1 ${x + w},${y + r}V${y + hgt}Z`;
    return `M${x},${y}V${y + hgt - r}A${r},${r} 0 0 0 ${x + r},${y + hgt}H${x + w - r}A${r},${r} 0 0 0 ${x + w},${y + hgt - r}V${y}Z`;
  }

  // Shared axes for the monthly column charts.
  function frame(box, months, lo, hi, H, aria) {
    const W = Math.max(320, box.clientWidth || 800);
    const M = { l: 62, r: 14, t: 26, b: 30 };
    const iw = W - M.l - M.r, ih = H - M.t - M.b;
    const ticks = niceTicks(lo, hi, 5);
    const y0 = ticks[0], y1 = ticks.at(-1);
    const y = (v) => M.t + ih - ((v - y0) / (y1 - y0)) * ih;
    const band = iw / months.length;
    const svg = s("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": aria }, box);
    for (const tv of ticks) {
      s("line", { x1: M.l, x2: W - M.r, y1: y(tv), y2: y(tv), "shape-rendering": "crispEdges",
        style: `stroke:var(${tv === 0 ? "--axis" : "--grid"})`, "stroke-width": 1 }, svg);
      stext(svg, M.l - 8, y(tv) + 4, tlc(tv), { "text-anchor": "end" });
    }
    const label = (i, m) => {
      if (band >= 46) return mShort(m);
      if (band >= 15) return +m.slice(5) % 3 === 1 ? mShort(m) : null;
      return m.endsWith("-01") || i === 0 ? m.slice(0, 4) : null;
    };
    let lastLabelX = -Infinity;
    months.forEach((m, i) => {
      const text = label(i, m);
      const cx = M.l + band * i + band / 2;
      if (text && cx - lastLabelX > 34) {
        stext(svg, cx, H - 10, text, { "text-anchor": "middle" });
        lastLabelX = cx;
      }
    });
    return { svg, W, M, ih, y, band, bw: Math.max(2, Math.min(24, band * 0.62)) };
  }

  /* Stacked columns. series: [{name, color}] from the baseline outwards; values[i][j]
     is month i, series j. Columns from forecastFrom on are drawn lighter as forecast. */
  function stackedChart(box, { months, series, values, onMonth, noData, forecastFrom, aria, height }) {
    box.replaceChildren();
    box.classList.remove("hovering");
    if (!months.length || !values.some((row) => row.some((v) => v))) {
      box.append(h("p", { class: "empty", text: "Seçili filtrelerle gösterilecek işlem yok." }));
      return;
    }
    const totals = values.map((row) => sum(row));
    let maxPos = 0, minNeg = 0;
    for (const row of values) {
      maxPos = Math.max(maxPos, sum(row.filter((v) => v > 0)));
      minNeg = Math.min(minNeg, sum(row.filter((v) => v < 0)));
    }
    const { svg, W, M, ih, y, band, bw } = frame(box, months, minNeg, maxPos, height || 300, aria);
    const fc = forecastFrom == null ? months.length : forecastFrom;
    const cols = months.map((m, i) => {
      const cx = M.l + band * i + band / 2, x = cx - bw / 2;
      const g = s("g", { class: "col" }, svg);
      for (const sign of [1, -1]) {
        const segs = series.map((_, j) => j).filter((j) => sign * values[i][j] > 0);
        let acc = 0;
        segs.forEach((j, k) => {
          const v = values[i][j];
          const top = Math.min(y(acc), y(acc + v)), bottom = Math.max(y(acc), y(acc + v));
          const isEnd = k === segs.length - 1;
          // 2px surface gap between touching segments
          const yTop = top + (sign > 0 ? (isEnd ? 0 : 1) : (k ? 1 : 0));
          const yBot = bottom - (sign > 0 ? (k ? 1 : 0) : (isEnd ? 0 : 1));
          if (yBot - yTop >= 0.5) {
            s("path", { d: isEnd ? barPath(x, yTop, bw, yBot - yTop, 4, sign > 0) : `M${x},${yTop}h${bw}V${yBot}H${x}Z`,
              style: `fill:${series[j].color}`, "fill-opacity": i >= fc ? 0.42 : null }, g);
          }
          acc += v;
        });
      }
      if (noData && noData.has(m) && !totals[i]) stext(svg, cx, y(0) - 5, "–", { "text-anchor": "middle" });
      return g;
    });
    if (fc < months.length) {
      const x = M.l + band * fc;
      s("line", { x1: x, x2: x, y1: M.t - 8, y2: M.t + ih, class: "sep", "stroke-width": 1, "stroke-dasharray": "3 3", "shape-rendering": "crispEdges" }, svg);
      stext(svg, x + 6, M.t - 10, "tahmin", { class: "direct" });
    }
    const actual = totals.slice(0, fc).filter((v) => v !== 0);
    const avg = actual.length ? sum(actual) / actual.length : 0;
    if (actual.length > 1 && avg > 0) {
      s("line", { x1: M.l, x2: W - M.r, y1: y(avg), y2: y(avg), style: "stroke:var(--ink-2)", "stroke-width": 1, opacity: 0.55, "shape-rendering": "crispEdges" }, svg);
      stext(svg, fc < months.length ? M.l + 4 : W - M.r, y(avg) - 5, `ortalama ${tlc(avg)}`,
        { "text-anchor": fc < months.length ? "start" : "end", class: "direct" });
    }
    if (band >= 26) {
      const head = totals.slice(0, fc);
      const maxI = head.indexOf(Math.max(...head));
      const lastI = fc - 1 - [...head].reverse().findIndex((v) => v !== 0);
      const labelled = new Set([maxI, lastI]);
      if (fc < months.length) labelled.add(fc);
      for (const i of labelled) {
        if (i < 0 || i >= months.length || totals[i] <= 0) continue;
        stext(svg, M.l + band * i + band / 2, y(sum(values[i].filter((v) => v > 0))) - 6, tlc(totals[i]), { "text-anchor": "middle", class: "direct" });
      }
    }
    months.forEach((m, i) => {
      const clickable = onMonth && i < fc;
      const hit = s("rect", { x: M.l + band * i, y: M.t, width: band, height: ih, class: "band", tabindex: 0,
        role: clickable ? "button" : "img", "aria-label": `${mLong(m)}${i >= fc ? " tahmini" : ""}: ${tl(totals[i])}` }, svg);
      const content = () => {
        const rows = series.map((ser, j) => [ser, values[i][j]]).filter(([, v]) => Math.abs(v) >= 0.5).sort((a, b) => b[1] - a[1])
          .map(([ser, v]) => ttRow(tl(v), ser.name, ser.color));
        const out = [ttTitle(`${mLong(m)}${i >= fc ? " · tahmin" : ""}`), ...rows, h("div", { class: "tt-total" }, ttRow(tl(totals[i]), "Toplam"))];
        if (noData && noData.has(m) && !totals[i]) out.push(ttNote("Bu ay için ekstre veya hesap hareketi yok."));
        else if (clickable) out.push(ttNote("Tıklayınca bu aya odaklanır."));
        return out;
      };
      hoverable(hit, content, clickable ? () => { hideTip(); onMonth(m); } : null);
      hit.addEventListener("pointerenter", () => { box.classList.add("hovering"); cols[i].classList.add("active"); });
      hit.addEventListener("pointerleave", () => { box.classList.remove("hovering"); cols[i].classList.remove("active"); });
    });
  }

  const focusMonth = (m) => { state.preset = null; state.from = m; state.to = m; update(); };

  function legend(box, items) {
    box.replaceChildren(...items.map(({ name, color, on, onclick, title }) => onclick
      ? h("button", { type: "button", "aria-pressed": String(on !== false), title, onclick }, swatch(color), name)
      : h("span", { class: "lg" }, swatch(color), name)));
  }

  const groupCats = (gi) => CAT.map((c, ci) => (c.group === gi ? ci : -1)).filter((ci) => ci >= 0);

  // ------------------------------------------------------- monthly chart
  function renderMonthly(F, P) {
    const months = P[0] ? monthsBetween(P[0], P[1]) : [];
    const idx = new Map(months.map((m, i) => [m, i]));
    const sums = months.map(() => new Array(GRP.length).fill(0));
    for (const t of F) sums[idx.get(t.mo)][t.g] += t.v;
    const present = GRP.map((_, gi) => gi).filter((gi) => sums.some((row) => row[gi] !== 0));
    const isolated = (ids) => state.cats && state.cats.size === ids.length && ids.every((ci) => state.cats.has(ci));
    legend($("legend"), present.map((gi) => {
      const ids = groupCats(gi);
      return {
        name: GRP[gi].name, color: groupColor(gi), on: !state.cats || ids.some((ci) => state.cats.has(ci)),
        title: "Yalnızca bu grubu göster / tümüne dön",
        onclick: () => { state.cats = isolated(ids) ? null : new Set(ids); update(); },
      };
    }));
    const withData = new Set();
    for (const t of TX) if (inScope(t)) withData.add(t.mo);
    const series = present.map((gi) => ({ name: GRP[gi].name, color: groupColor(gi) }));
    const values = sums.map((row) => present.map((gi) => row[gi]));
    if (views["card-monthly"] !== "table") {
      stackedChart($("monthly"), {
        months, series, values, onMonth: focusMonth, noData: new Set(months.filter((m) => !withData.has(m))),
        aria: "Aylık giderler, ana gruplara göre yığılmış sütun grafiği. Değerler Tablo görünümünde.",
      });
    }
    heatTable($("monthly-table"), months, series.map((ser, j) => ({
      ...ser,
      onclick: (m) => { state.preset = null; state.from = m; state.to = m; state.cats = new Set(groupCats(present[j])); update(); },
    })), values);
  }

  // Sequential ramp; dark mode anchors low values on the dark surface instead.
  function heatStyle(v, max) {
    if (!(v > 0) || !(max > 0)) return {};
    const step = 1 + Math.round((v / max) * 6);
    const dark = getComputedStyle(ROOT).colorScheme === "dark";
    const shade = dark ? 8 - step : step;
    const lightText = dark ? shade >= 4 : shade >= 5;
    return { background: `var(--seq-${shade}00)`, color: lightText ? "#ffffff" : "#0b0b0b" };
  }

  function heatTable(box, months, columns, values) {
    if (!months.length || !columns.length) { box.replaceChildren(h("p", { class: "empty", text: "Veri yok." })); return; }
    const colMax = columns.map((_, j) => Math.max(...values.map((row) => row[j])));
    const totals = values.map((row) => sum(row));
    const totMax = Math.max(...totals);
    const head = h("tr", {}, h("th", { scope: "col" }, "Ay"),
      ...columns.map((c) => h("th", { class: "num", scope: "col" }, h("span", { class: "cat-cell" }, swatch(c.color), c.name))),
      h("th", { class: "num", scope: "col" }, "Toplam"));
    const rows = months.map((_, i) => i).reverse().map((i) => h("tr", {},
      h("td", { text: mLong(months[i]) }),
      ...columns.map((c, j) => {
        const v = values[i][j];
        const td = h("td", { class: "heat", style: heatStyle(v, colMax[j]), text: v ? tl(v) : "–", title: `${c.name} · ${mLong(months[i])}` });
        if (c.onclick) td.addEventListener("click", () => c.onclick(months[i]));
        return td;
      }),
      h("td", { class: "heat", style: heatStyle(totals[i], totMax), text: totals[i] ? tl(totals[i]) : "–" })));
    const n = totals.filter((v) => v !== 0).length || 1;
    const colSum = (j) => sum(values, (row) => row[j]);
    const foot = [
      h("tr", {}, h("td", { text: "Toplam" }), ...columns.map((_, j) => h("td", { class: "num", text: tl(colSum(j)) })),
        h("td", { class: "num", text: tl(sum(totals)) })),
      h("tr", {}, h("td", { text: "Aylık ortalama" }), ...columns.map((_, j) => h("td", { class: "num", text: tl(colSum(j) / n) })),
        h("td", { class: "num", text: tl(sum(totals) / n) })),
    ];
    const ramp = h("span", { class: "ramp" }, ...[1, 2, 3, 4, 5, 6, 7].map((k) => h("i", { style: { background: `var(--seq-${k}00)` } })));
    box.replaceChildren(
      h("table", {}, h("thead", {}, head), h("tbody", {}, ...rows), h("tfoot", {}, ...foot)),
      h("div", { class: "scale" }, "Az", ramp,
        `Çok — renk koyuluğu her sütunun kendi en yüksek ayına göredir.${columns.some((c) => c.onclick) ? " Hücreye tıklayınca o ay ve sütunla filtreler." : ""}`),
    );
  }

  // ------------------------------------------------------ necessity card
  function renderNecessity(F, P) {
    const total = sum(F, (t) => t.v);
    const byLevel = LEVELS.map((_, li) => sum(F.filter((t) => t.lv === li), (t) => t.v));
    const nMonths = new Set(F.map((t) => t.mo)).size || 1;
    $("level-tiles").replaceChildren(...LEVELS.map((l, li) => {
      const on = !!state.levels && state.levels.size === 1 && state.levels.has(li);
      return h("button", { type: "button", class: "level-tile", "aria-pressed": String(on), title: "Yalnızca bu seviyeyi göster / tümüne dön",
        onclick: () => { state.levels = on ? null : new Set([li]); update(); } },
        h("div", { class: "label" }, swatch(levelColor(li)), l.name),
        h("div", { class: "value", text: tl(byLevel[li]) }),
        h("div", { class: "meta", text: `${total > 0 ? nfp.format(byLevel[li] / total) : "–"} · ayda ${tl(byLevel[li] / nMonths)}` }));
    }));
    const months = P[0] ? monthsBetween(P[0], P[1]) : [];
    const idx = new Map(months.map((m, i) => [m, i]));
    const values = months.map(() => new Array(LEVELS.length).fill(0));
    for (const t of F) values[idx.get(t.mo)][t.lv] += t.v;
    const series = LEVELS.map((l, li) => ({ name: l.name, color: levelColor(li) }));
    if (views["card-necessity"] !== "table") {
      stackedChart($("necessity"), { months, series, values, onMonth: focusMonth,
        aria: "Aylık giderler, gereklilik seviyesine göre yığılmış sütun grafiği. Değerler Tablo görünümünde." });
    }
    heatTable($("necessity-table"), months, series, values);
  }

  /* Habits from the interpretation: a monthly or new habit costs its last three months'
     average from now on, an occasional one its total spread over the window; one-offs and
     habits that stopped cost nothing from now on, so they are never turned into a yearly
     figure. Global: the window is the last complete months, not the period filter. */
  const HABIT_ICON = { duzenli: "●", yeni: "▲", ara_sira: "◐", durdu: "■", tek: "○" };
  const habitBadge = (status) => h("span", { class: "habit" },
    h("span", { class: "icon", "aria-hidden": "true", text: HABIT_ICON[status] }), INS.habitLabels[status]);

  function renderHabits() {
    const box = $("habits");
    const list = INS.habits.filter((x) => x.monthly >= 1);
    const past = INS.habits.filter((x) => x.monthly < 1 && x.total >= 500).slice(0, 8);
    $("habits-hint").textContent = `${WINDOW.length} tam ay (${windowText()}). Her ay ya da yeni başlayan alışkanlıklar son 3 ayın ` +
      "ortalamasıyla, ara sıra olanlar dönem boyunca yayılarak aylığa çevrilir. Tek seferlik alışverişler ve durmuş alışkanlıklar " +
      "bundan sonraki aylara yansıtılmaz. Faiz ve ücretler kategoriye, isteğe bağlı harcamalar işyerine göre toplanır; düzenli " +
      "ödemeler (abonelikler) aşağıda ayrı listelenir. Satıra tıklayınca filtreler.";
    if (!list.length && !past.length) { box.replaceChildren(h("p", { class: "empty", text: "Bu dönemde isteğe bağlı veya gereksiz harcama yok." })); return; }
    const columns = [
      { key: "label", label: "Kalem" }, { key: "status", label: "Durum" }, { key: "pattern", label: "Ne sıklıkla" },
      { key: "recent", label: "Son 3 ayda aylık", num: true }, { key: "total", label: `${WINDOW.length} ayda toplam`, num: true },
      { key: "monthly", label: "Bundan sonra aylık", num: true },
    ];
    const row = (x) => ({
      onclick: () => { if (x.byCat) state.cats = new Set([x.c]); else state.merchant = x.name; update(); },
      cells: {
        label: h("div", {}, x.name, h("div", { class: "muted small" },
          h("span", { class: "level-badge" }, swatch(levelColor(x.lv >= 0 ? x.lv : UNSURE)), x.byCat ? LEVELS[x.lv].name : CAT[x.c].name))),
        status: habitBadge(x.status), pattern: h("span", { class: "small", text: x.pattern }),
        recent: x.recent >= 1 ? tl(x.recent) : "–", total: tl(x.total), monthly: x.monthly >= 1 ? tl(x.monthly) : "–",
      },
    });
    const body = list.map(row);
    if (past.length) {
      body.push({ group: true, cells: { label: "Durmuş veya tek seferlik (bundan sonraya yansıtılmaz)", status: "", pattern: "", recent: "", total: "", monthly: "" } });
      body.push(...past.map(row));
    }
    const foot = h("tr", {}, h("td", { colspan: 5, text: "Bundan sonra aylık toplam" }), h("td", { class: "num", text: tl(sum(list, (x) => x.monthly)) }));
    box.replaceChildren(sortableTable(columns, body, { foot }));
  }

  // ------------------------------------------------------- cash flow card
  function cashflowRows(F, months) {
    const extras = select({ period: [months[0], months.at(-1)], kinds: ["gelir", "kisiye_transfer", "kredi_anapara", "yatirim"], allCats: true });
    const of = (list, m, kind) => sum(list.filter((t) => t.mo === m && (!kind || t.kid === kind)), (t) => t.v);
    return months.map((m) => {
      const inc = -of(extras, m, "gelir"), exp = of(F, m);
      const people = of(extras, m, "kisiye_transfer"), debt = of(extras, m, "kredi_anapara"), invest = of(extras, m, "yatirim");
      return { m, inc, exp, net: inc - exp, people, debt, invest, left: inc - exp - people - debt - invest };
    });
  }

  function renderCashflow(F, P) {
    const box = $("cashflow");
    const months = P[0] ? monthsBetween(P[0], P[1]).filter((m) => INCOME_MONTHS.has(m)) : [];
    legend($("cashflow-legend"), [
      { name: "Gelir", color: "var(--s1)" }, { name: "Gider", color: "var(--s8)" }, { name: "Net (gelir − gider)", color: "var(--ink)" },
    ]);
    if (!months.length) {
      $("cashflow-hint").textContent = "Gelir yalnızca hesap hareketi dökümü olan aylar için bilinir; seçili dönemde yok.";
      box.replaceChildren(h("p", { class: "empty", text: "Seçili dönemde hesap hareketi yok." }));
      $("cashflow-table").replaceChildren();
      return;
    }
    $("cashflow-hint").textContent = `Hesap hareketi dökümü olan ${months.length} ay (${mShort(months[0])} – ${mShort(months.at(-1))}). ` +
      "Gelir: maaş, iş geliri ve kişilerden gelen para. Kendi hesaplarınız arasındaki transferler ve kart ödemeleri sayılmaz.";
    const rows = cashflowRows(F, months);
    if (views["card-cashflow"] !== "table") mirrorChart(box, rows);
    const keys = ["inc", "exp", "net", "people", "debt", "invest", "left"];
    const columns = [
      { key: "m", label: "Ay" }, { key: "inc", label: "Gelir", num: true }, { key: "exp", label: "Gider", num: true },
      { key: "net", label: "Net", num: true }, { key: "people", label: "Kişilere gönderilen", num: true },
      { key: "debt", label: "Borç anaparası", num: true }, { key: "invest", label: "Birikim / yatırım", num: true },
      { key: "left", label: "Hepsinden sonra kalan", num: true },
    ];
    const foot = h("tr", {}, h("td", { text: "Toplam" }), ...keys.map((k) => h("td", { class: "num", text: tl(sum(rows, (r) => r[k])) })));
    $("cashflow-table").replaceChildren(sortableTable(columns, [...rows].reverse().map((r) => ({
      cells: { m: mLong(r.m), ...Object.fromEntries(keys.map((k) => [k, tl(r[k])])) },
    })), { foot }));
  }

  // Income rises above the baseline, expenses hang below it, net is the dot.
  function mirrorChart(box, rows) {
    box.replaceChildren();
    box.classList.remove("hovering");
    const maxInc = Math.max(0, ...rows.map((r) => r.inc));
    const maxExp = Math.max(0, ...rows.map((r) => r.exp));
    const minNet = Math.min(0, ...rows.map((r) => r.net));
    const { svg, M, ih, y, band, bw } = frame(box, rows.map((r) => r.m), Math.min(-maxExp, minNet), maxInc, 300,
      "Aylık gelir (yukarı) ve gider (aşağı), net nokta ile. Değerler Tablo görünümünde.");
    const cols = rows.map((r, i) => {
      const cx = M.l + band * i + band / 2, x = cx - bw / 2;
      const g = s("g", { class: "col" }, svg);
      if (r.inc > 0) s("path", { d: barPath(x, y(r.inc), bw, y(0) - y(r.inc), 4, true), style: "fill:var(--s1)" }, g);
      if (r.exp > 0) s("path", { d: barPath(x, y(0) + 1, bw, y(-r.exp) - y(0) - 1, 4, false), style: "fill:var(--s8)" }, g);
      s("circle", { cx, cy: y(r.net), r: 4.5, style: "fill:var(--ink);stroke:var(--surface)", "stroke-width": 2 }, g);
      return g;
    });
    rows.forEach((r, i) => {
      const hit = s("rect", { x: M.l + band * i, y: M.t, width: band, height: ih, class: "band", tabindex: 0, role: "img",
        "aria-label": `${mLong(r.m)}: gelir ${tl(r.inc)}, gider ${tl(r.exp)}, net ${tl(r.net)}` }, svg);
      hoverable(hit, () => [ttTitle(mLong(r.m)), ttRow(tl(r.inc), "Gelir", "var(--s1)"), ttRow(tl(r.exp), "Gider", "var(--s8)"),
        h("div", { class: "tt-total" }, ttRow(tl(r.net), "Net (gelir − gider)", "var(--ink)")),
        ttNote(`Kişilere ${tl(r.people)} · borç ${tl(r.debt)} · birikim ${tl(r.invest)} → kalan ${tl(r.left)}`)]);
      hit.addEventListener("pointerenter", () => { box.classList.add("hovering"); cols[i].classList.add("active"); });
      hit.addEventListener("pointerleave", () => { box.classList.remove("hovering"); cols[i].classList.remove("active"); });
    });
  }

  // ---------------------------------------------------- recurring payments
  /* Regular payments and their status come from the interpretation: a series is over when the
     statements of its card or account go on past the next expected payment without it, and
     cancelled when the user's rules list it under _biten. They follow every filter except the
     period: the status is about today. */
  const RUNNING = new Set(["devam", "iptal_sonrasi"]);
  const STATUS_ICON = { devam: "●", bitti: "■", iptal: "✕", iptal_sonrasi: "!" };
  // A needed bill that stopped showing up may simply be paid from an account without documents.
  const missingBill = (r) => r.status === "bitti" && r.lv === LEVEL_IDX["Gerekli"];
  const statusBadge = (r) => h("span", { class: `status st-${r.status}` },
    h("span", { class: "icon", "aria-hidden": "true", text: STATUS_ICON[r.status] }),
    missingBill(r) ? "Belgelerde yok" : INS.statusLabels[r.status]);

  function seriesVisible(r) {
    if (state.accounts && !r.a.some((a) => state.accounts.has(a))) return false;
    if (!state.kinds.has(r.k) && r.k === "harcama") return false;
    if (state.cats && !state.cats.has(r.c)) return false;
    if (state.levels && !state.levels.has(r.lv >= 0 ? r.lv : UNSURE)) return false;
    if (state.merchant && r.m !== state.merchant) return false;
    return !state.q || lower(r.m).includes(state.q);
  }

  // Purchases paid in installments: the latest installment seen of each.
  function installmentItems(list) {
    const groups = new Map();
    for (const t of list) {
      const m = /^(\d+)\/(\d+)$/.exec(t.i || "");
      if (!m || t.v <= 0) continue;
      const k = +m[1], n = +m[2];
      const key = `${t.a}|${t.m}|${n}|${Math.round(t.v)}`;
      const g = groups.get(key);
      if (!g || k > g.k) groups.set(key, { t, k, n });
    }
    return [...groups.values()].sort((a, b) => (a.t.d < b.t.d ? 1 : -1));
  }

  function seriesRows(list) {
    return list.map((r) => ({
      onclick: () => { state.merchant = r.m; update(); },
      cells: {
        m: h("div", {}, r.m,
          h("div", { class: "muted small" }, h("span", { class: "level-badge" }, swatch(levelColor(r.lv >= 0 ? r.lv : UNSURE)), r.lv >= 0 ? LEVELS[r.lv].name : KIND[KIND_ID.indexOf(r.k)].label)),
          r.change && r.change[1] > r.change[0] ? h("div", { class: "muted small", text: `${tl(r.change[0])} → ${tl(r.change[1])} (${mLong(r.change[2].slice(0, 7))})` }) : null),
        cat: h("span", { class: "cat-cell" }, swatch(groupColor(CAT[r.c].group)), CAT[r.c].name),
        status: statusBadge(r),
        v: tl(r.v),
        last: h("div", {}, dLabel(r.last), h("div", { class: "muted small", text: tl2(r.lastv) })),
        next: RUNNING.has(r.status) && r.next ? dLabel(r.next) : h("span", { class: "muted", text: "–" }),
        acc: h("span", { class: "small", text: r.a.map((a) => ACC[a].label).join(", ") }),
      },
    }));
  }

  function renderRecurring(F) {
    $("recurring-hint").textContent = "Yaklaşık ayda bir tekrarlanan ödemeler: kira, aidat, faturalar, abonelikler ve BES. " +
      "Kartın ya da hesabın belgeleri beklenen ödeme tarihini geçtiği hâlde ödeme yoksa \"Bitti\", kişisel kurallardaki _biten " +
      "listesindeyse \"İptal edildi\" yazar. Aylık tutar faturalarda son üç ödemenin ortası, aboneliklerde son tutardır. " +
      "Dönem filtresinden bağımsızdır; durum bugüne göredir.";
    const visible = SERIES.filter((r) => r.show && seriesVisible(r));
    const running = visible.filter((r) => RUNNING.has(r.status)).sort((a, b) => b.v - a.v);
    const ended = visible.filter((r) => !RUNNING.has(r.status)).sort((a, b) => (a.last < b.last ? 1 : -1));
    const columns = [
      { key: "m", label: "İşyeri / kişi" }, { key: "cat", label: "Kategori" }, { key: "status", label: "Durum" },
      { key: "v", label: "Aylık", num: true }, { key: "last", label: "Son ödeme", num: true },
      { key: "next", label: "Sonraki (beklenen)", num: true }, { key: "acc", label: "Hesap" },
    ];
    const parts = [];
    if (running.length) {
      const foot = h("tr", {}, h("td", { colspan: 3, text: `Devam eden ${running.length} ödemenin aylık toplamı` }),
        h("td", { class: "num", text: tl(sum(running, (r) => r.v)) }), h("td", { colspan: 3 }));
      parts.push(sortableTable(columns, seriesRows(running), { foot }));
    } else {
      parts.push(h("p", { class: "empty", text: "Seçili filtrelerle devam eden düzenli ödeme yok." }));
    }
    if (ended.length) {
      const stopped = ended.filter((r) => !missingBill(r));
      const missing = ended.filter(missingBill);
      parts.push(h("h3", { class: "subhead", text: `Son ${WINDOW.length} ayda biten ve iptal edilenler` }),
        h("p", { class: "hint", text: "Bunlar tahmine girmez." +
          (stopped.length ? ` Biten ve iptal edilen ödemeler ayda ${tl(sum(stopped, (r) => r.v))} tutuyordu.` : "") +
          (missing.length ? ` "Belgelerde yok" yazan faturalar başka bir hesaptan ödeniyor olabilir; o hesabın dökümünü ekleyin ya da bittiyse _biten listesine yazın.` : "") }),
        sortableTable(columns, seriesRows(ended)));
    }
    const inst = installmentItems(F.filter((t) => t.kid === "harcama")).slice(0, 15);
    if (inst.length) {
      const icols = [
        { key: "m", label: "İşyeri" }, { key: "acc", label: "Hesap" }, { key: "step", label: "Taksit", num: true },
        { key: "amt", label: "Aylık taksit", num: true }, { key: "last", label: "Son görülen taksit", num: true },
        { key: "left", label: "Kalan", num: true },
      ];
      parts.push(h("h3", { class: "subhead", text: "Taksitli alışverişler" }),
        h("p", { class: "hint", text: "Seçili dönemde görülen son taksite göre. Kalan tutar: kalan taksit sayısı × aylık taksit." }),
        sortableTable(icols, inst.map((r) => ({
          onclick: () => { state.merchant = r.t.m; update(); },
          cells: {
            m: r.t.m, acc: h("span", { class: "small", text: ACC[r.t.a].label }), step: `${r.k}/${r.n}`,
            amt: tl2(r.t.v), last: dLabel(r.t.d),
            left: r.k >= r.n ? h("span", { class: "muted", text: "Bitti" }) : tl((r.n - r.k) * r.t.v),
          },
        }))));
    }
    $("recurring").replaceChildren(...parts);
  }

  // ------------------------------------------------------------- forecast
  const median = (values) => {
    const v = values.slice().sort((a, b) => a - b);
    const mid = Math.floor(v.length / 2);
    return v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2;
  };

  /* Next three months, in three parts:
     - regular payments still running (rent, dues, bills, subscriptions) at their monthly amount;
       ended and cancelled ones are left out;
     - installments still due;
     - everything else per necessity level: the median of the six complete months up to the last
       complete one, without regular payments, installments and merchants listed under _biten.
       Taking the level and not each merchant keeps an irregular shop (a few visits some months,
       none in others) from turning into a fixed monthly cost; the median keeps one big purchase
       from inflating the month.
     Expected income = the regular income (salary) still running. */
  function forecastModel() {
    const [lo, hi] = extent();
    if (!lo) return null;
    const all = select({ period: [lo, hi] });
    const base = WINDOW.slice(-6).filter((m) => m >= lo);
    const next = [1, 2, 3].map((k) => addMonths(hi, k));
    if (!base.length) return null;
    const fixed = SERIES.filter((r) => RUNNING.has(r.status) && r.k === "harcama" && seriesVisible(r));
    const rows = fixed.map((r) => ({
      type: "Düzenli ödemeler", label: r.m,
      sub: `${CAT[r.c].name} · son ödeme ${dLabel(r.last)}${r.status === "iptal_sonrasi" ? " · iptalden sonra da çekildi" : ""}`,
      lv: r.lv >= 0 ? r.lv : UNSURE, g: CAT[r.c].group, per: next.map(() => r.v), merchant: r.m,
    }));
    for (const r of installmentItems(all.filter((t) => t.mo >= addMonths(hi, -2)))) {
      const per = next.map((m) => (r.k + monthDiff(r.t.mo, m) <= r.n ? r.t.v : 0));
      if (!per.some((v) => v)) continue;
      rows.push({ type: "Kalan taksitler", label: r.t.m, sub: `${ACC[r.t.a].label} · ${r.n} taksit, son görülen ${r.k}.`,
        lv: r.t.lv, g: r.t.g, per, merchant: r.t.m });
    }
    const variable = all.filter((t) => base.includes(t.mo) && t.r == null && !t.i && !t.x);
    LEVELS.forEach((l, li) => {
      const inLevel = variable.filter((t) => t.lv === li);
      const months = base.map((m) => sum(inLevel.filter((t) => t.mo === m), (t) => t.v));
      const typical = median(months);
      if (typical < 1) return;
      // The largest merchants seen in at least two of the months; a one-off is not what the month is made of.
      const byMerchant = new Map();
      for (const t of inLevel) {
        const e = byMerchant.get(t.m) || { v: 0, months: new Set() };
        e.v += t.v;
        e.months.add(t.mo);
        byMerchant.set(t.m, e);
      }
      const top = [...byMerchant].filter(([, e]) => e.months.size >= 2).sort((x, y) => y[1].v - x[1].v).slice(0, 4).map(([m]) => m);
      rows.push({ type: `Değişken harcamalar (son ${base.length} tam ayın medyanı)`, label: l.name,
        sub: `aylık ${tl(Math.min(...months))} ile ${tl(Math.max(...months))} arasında${top.length ? ` · en çok: ${top.join(", ")}` : ""}`,
        lv: li, g: null, per: next.map(() => typical), merchant: null, level: li });
    });
    const income = INS.income;
    const saving = SERIES.filter((r) => RUNNING.has(r.status) && r.k === "yatirim");
    const totals = next.map((_, i) => sum(rows, (r) => r.per[i]));
    const byLevel = next.map((_, i) => LEVELS.map((_, li) => sum(rows.filter((r) => r.lv === li), (r) => r.per[i])));
    return { base, next, rows, totals, byLevel, income, incomeMonthly: sum(income, (r) => r.v),
      savingMonthly: sum(saving, (r) => r.v), saving, last: hi, all };
  }

  function renderForecast() {
    const model = forecastModel();
    if (!model || !model.rows.length) {
      $("forecast-hint").textContent = "Tahmin için yeterli veri yok.";
      for (const id of ["forecast-tiles", "forecast-chart", "forecast-table", "forecast-legend"]) $(id).replaceChildren();
      return;
    }
    const { base, next, rows, totals, byLevel, income, incomeMonthly, savingMonthly, saving, last, all } = model;
    $("forecast-hint").textContent = "Dönem filtresinden bağımsızdır, diğer filtrelere uyar. " +
      "Devam eden düzenli ödemeler aylık tutarlarıyla, kalan taksitler vadesiyle girer; biten ve iptal edilen abonelikler girmez. " +
      `Geri kalan harcamalar gereklilik seviyesine göre ${mShort(base[0])} – ${mShort(base.at(-1))} arasındaki orta (medyan) ayla tahmin edilir: ` +
      "ara sıra yapılan alışverişler sabit gider gibi her aya yazılmaz, tek seferlik büyük alışverişler tahmini şişirmez. " +
      `${mLong(last)} ekstreleri kesim tarihlerinde bittiği için hesaba katılmadı. ` +
      "Gelir düzenli tekrarlanan ödemeden (maaş) tahmin edilir. Kişilere gönderilen para ve borç ödemeleri gider sayılmaz; " +
      "düzensiz oldukları için tablonun en altında son altı ayın orta (medyan) tutarıyla ayrıca düşülür.";
    const need = LEVEL_IDX["Gerekli"], opt = LEVEL_IDX["İsteğe bağlı"], avoid = LEVEL_IDX["Gereksiz"];
    const other = INS.flow ? INS.flow.otherTypical : 0;
    const left = incomeMonthly - totals[0] - savingMonthly - other;
    $("forecast-tiles").replaceChildren(
      tile(`${mLong(next[0])} tahmini gider`, tl(totals[0]),
        `Gerekli ${tl(byLevel[0][need])} · İsteğe bağlı ${tl(byLevel[0][opt])} · Gereksiz ${tl(byLevel[0][avoid])}`),
      tile("3 aylık tahmini gider", tl(sum(totals)), `${mShort(next[0])} – ${mShort(next.at(-1))}`),
      tile("Beklenen aylık gelir", incomeMonthly > 0 ? tl(incomeMonthly) : "—",
        income.length ? income.map((r) => r.m).join(", ") : "Düzenli gelir bulunamadı"),
      tile(`${mLong(next[0])} tahmini kalan`, incomeMonthly > 0 ? tl(left) : "—",
        incomeMonthly > 0 ? `gelir − gider${savingMonthly ? ` − BES ${tl(savingMonthly)}` : ""}${other >= 1 ? ` − kişilere ve borca tipik ${tl(other)}` : ""}` : "gelir tahmini yok"),
    );
    // The last six actual months next to the forecast, stacked by necessity.
    const actualMonths = monthsBetween(addMonths(last, -5), last);
    const values = [
      ...actualMonths.map((m) => {
        const row = new Array(LEVELS.length).fill(0);
        for (const t of all) if (t.mo === m) row[t.lv] += t.v;
        return row;
      }),
      ...byLevel,
    ];
    const series = LEVELS.map((l, li) => ({ name: l.name, color: levelColor(li) }));
    legend($("forecast-legend"), [...series, { name: "Açık renkli sütunlar: tahmin", color: "color-mix(in srgb, var(--ink-2) 42%, transparent)" }]);
    stackedChart($("forecast-chart"), { months: [...actualMonths, ...next], series, values, forecastFrom: actualMonths.length, height: 260,
      aria: "Son altı ayın giderleri ve önümüzdeki üç ayın tahmini, gereklilik seviyesine göre yığılmış sütunlar. Değerler aşağıdaki tabloda." });
    const columns = [{ key: "label", label: "Kalem" }, { key: "lvl", label: "Gereklilik" },
      ...next.map((m, i) => ({ key: `n${i}`, label: mLong(m), num: true }))];
    const body = [];
    for (const type of new Set(rows.map((r) => r.type))) {
      const group = rows.filter((r) => r.type === type).sort((a, b) => b.per[0] - a.per[0]);
      body.push({ group: true, cells: { label: type, lvl: "", ...Object.fromEntries(next.map((_, i) => [`n${i}`, tl(sum(group, (r) => r.per[i]))])) } });
      for (const r of group) {
        body.push({
          onclick: r.merchant ? () => { state.merchant = r.merchant; update(); }
            : r.level != null ? () => { state.levels = new Set([r.level]); update(); } : null,
          cells: {
            label: h("div", {}, h("span", { class: "cat-cell" }, swatch(r.g != null ? groupColor(r.g) : levelColor(r.lv)), r.label),
              r.sub ? h("div", { class: "muted small", text: r.sub }) : null),
            lvl: h("span", { class: "level-badge" }, swatch(levelColor(r.lv)), LEVELS[r.lv].name),
            ...Object.fromEntries(next.map((_, i) => [`n${i}`, r.per[i] ? tl(r.per[i]) : "–"])),
          },
        });
      }
    }
    const footRow = (label, vals) => h("tr", {}, h("td", { colspan: 2, text: label }), ...vals.map((v) => h("td", { class: "num", text: v })));
    const foot = [footRow("Tahmini toplam gider", totals.map(tl))];
    if (incomeMonthly > 0) {
      foot.push(footRow("Beklenen gelir", next.map(() => tl(incomeMonthly))));
      if (savingMonthly) foot.push(footRow(`BES ve düzenli birikim (${saving.map((r) => r.m).join(", ")})`, next.map(() => tl(savingMonthly))));
      foot.push(footRow("Gelir − gider − birikim", totals.map((v) => tl(incomeMonthly - v - savingMonthly))));
      if (other >= 1) {
        foot.push(footRow(`Kişilere ve borç ödemelerine giden (son ${base.length} ayın medyanı; düzensiz)`, next.map(() => tl(other))));
        foot.push(footRow("Hepsinden sonra kalan", totals.map((v) => tl(incomeMonthly - v - savingMonthly - other))));
      }
    }
    $("forecast-table").replaceChildren(sortableTable(columns, body, { foot }));
  }

  // ------------------------------------------------- horizontal bar lists
  function renderHBars(box, rows, opts) {
    box.replaceChildren();
    if (!rows.length) { box.append(h("p", { class: "empty", text: "Veri yok." })); return; }
    const max = Math.max(...rows.map((r) => r.value), 0);
    for (const r of rows) {
      const frac = max > 0 ? Math.max(0, r.value) / max : 0;
      const track = h("div", { class: "htrack", tabindex: 0, role: "button", "aria-label": `${r.label}: ${tl(r.value)}` },
        h("div", { class: "hbar", style: { width: `calc((100% - 84px) * ${frac.toFixed(4)})`, background: groupColor(r.gi) } }),
        h("span", { class: "hval", text: tl(r.value) }));
      const label = h("div", { class: "hlabel" }, swatch(groupColor(r.gi)), h("span", { text: r.label }));
      const row = h("div", { class: `hrow${opts.selected(r) ? " selected" : ""}` }, label, track);
      for (const el of [label, track]) hoverable(el, () => opts.tip(r), r.onclick ? () => { hideTip(); r.onclick(); } : null);
      box.append(row);
    }
  }

  function aggregate(F, keyFn) {
    const map = new Map();
    for (const t of F) {
      const k = keyFn(t);
      let a = map.get(k);
      if (!a) map.set(k, (a = { key: k, value: 0, count: 0, last: null, sample: t }));
      a.value += t.v;
      a.count += 1;
      if (!a.last || t.d > a.last.d) a.last = t;
    }
    return [...map.values()].sort((a, b) => b.value - a.value);
  }

  function sortableTable(columns, rows, opts = {}) {
    const key = opts.sort || {};
    const head = h("tr", {}, ...columns.map((c) => {
      const th = h("th", { class: `${c.num ? "num " : ""}${c.sort ? "sortable" : ""}`.trim() || null, scope: "col" }, c.label);
      if (c.sort) {
        if (key.key === c.key) th.append(h("span", { class: "arrow", text: key.dir > 0 ? "▲" : "▼" }));
        th.addEventListener("click", () => opts.onSort && opts.onSort(c.key));
      }
      return th;
    }));
    const body = rows.map((r) => h("tr", { class: r.onclick ? "clickable" : null, onclick: r.onclick || null },
      ...columns.map((c) => h("td", { class: `${c.num ? "num" : ""}${r.group ? " group-row" : ""}`.trim() || null }, r.cells[c.key]))));
    return h("table", {}, h("thead", {}, head), h("tbody", {}, ...body), opts.foot ? h("tfoot", {}, opts.foot) : null);
  }

  function renderCategories(F) {
    const total = sum(F, (t) => t.v);
    const nMonths = new Set(F.map((t) => t.mo)).size || 1;
    const agg = aggregate(F, (t) => t.c);
    const rows = agg.slice(0, 12).map((a) => ({
      label: CAT[a.key].name, value: a.value, gi: CAT[a.key].group, a,
      onclick: () => { state.cats = state.cats && state.cats.size === 1 && state.cats.has(a.key) ? null : new Set([a.key]); update(); },
    }));
    const rest = agg.slice(12);
    if (rest.length) rows.push({ label: `Diğer ${rest.length} kategori`, value: sum(rest, (a) => a.value), gi: OTHER_GROUP, a: { count: sum(rest, (a) => a.count) } });
    renderHBars($("categories"), rows, {
      selected: (r) => r.a.key != null && state.cats && state.cats.has(r.a.key) && state.cats.size === 1,
      tip: (r) => [ttTitle(r.label), ttRow(tl(r.value), "toplam", groupColor(r.gi)),
        ttRow(total ? nfp.format(r.value / total) : "–", "toplam içindeki pay"),
        ttRow(tl(r.value / nMonths), "aylık ortalama"), ttRow(nf0.format(r.a.count), "işlem"),
        r.a.key != null ? ttNote(`${GRP[CAT[r.a.key].group].name} · tıklayınca filtreler`) : ttNote("Küçük kategoriler birleştirildi")],
    });
    const columns = [
      { key: "cat", label: "Kategori" }, { key: "grp", label: "Ana grup" }, { key: "value", label: "Toplam", num: true },
      { key: "share", label: "Pay", num: true }, { key: "avg", label: "Aylık ort.", num: true }, { key: "count", label: "İşlem", num: true },
    ];
    $("categories-table").replaceChildren(sortableTable(columns, agg.map((a) => ({
      onclick: () => { state.cats = new Set([a.key]); update(); },
      cells: {
        cat: h("span", { class: "cat-cell" }, swatch(groupColor(CAT[a.key].group)), CAT[a.key].name),
        grp: GRP[CAT[a.key].group].name, value: tl(a.value), share: total ? nfp.format(a.value / total) : "–",
        avg: tl(a.value / nMonths), count: nf0.format(a.count),
      },
    }))));
  }

  function renderMerchants(F) {
    const agg = aggregate(F, (t) => t.m);
    renderHBars($("merchants"), agg.slice(0, 12).map((a) => ({
      label: a.key, value: a.value, gi: CAT[a.sample.c].group, a,
      onclick: () => { state.merchant = state.merchant === a.key ? null : a.key; update(); },
    })), {
      selected: (r) => state.merchant === r.label,
      tip: (r) => [ttTitle(r.label), ttRow(tl(r.value), "toplam", groupColor(r.gi)), ttRow(nf0.format(r.a.count), "işlem"),
        ttRow(tl(r.value / r.a.count), "işlem başına"), ttRow(dLabel(r.a.last.d), "son işlem"),
        ttNote(`${CAT[r.a.sample.c].name} · tıklayınca filtreler`)],
    });
    const columns = [
      { key: "m", label: "İşyeri / kişi" }, { key: "cat", label: "Kategori" }, { key: "count", label: "İşlem", num: true },
      { key: "value", label: "Toplam", num: true }, { key: "avg", label: "İşlem başına", num: true }, { key: "last", label: "Son işlem", num: true },
    ];
    $("merchants-table").replaceChildren(sortableTable(columns, agg.slice(0, 100).map((a) => ({
      onclick: () => { state.merchant = a.key; update(); },
      cells: { m: a.key, cat: CAT[a.sample.c].name, count: nf0.format(a.count), value: tl(a.value), avg: tl(a.value / a.count), last: dLabel(a.last.d) },
    }))));
  }

  // ---------------------------------------------------------- transactions
  const PAGE = 50;
  const PROVISIONAL_TIP = "Dekonttan; hesabın ekstresi ya da dökümü gelince satırıyla eşleşip kesinleşecek";
  const SORTERS = { d: (t) => t.d, m: (t) => lower(t.m), c: (t) => lower(CAT[t.c].name), a: (t) => lower(ACC[t.a].label), v: (t) => t.v };

  function renderTransactions(F) {
    const { key, dir } = state.sort;
    const rows = F.slice().sort((a, b) => {
      const x = SORTERS[key](a), y = SORTERS[key](b);
      return (x < y ? -1 : x > y ? 1 : 0) * dir || (a.d < b.d ? 1 : -1);
    });
    const pages = Math.max(1, Math.ceil(rows.length / PAGE));
    state.page = Math.min(state.page, pages - 1);
    const view = rows.slice(state.page * PAGE, state.page * PAGE + PAGE);
    $("tx-summary").textContent = `${nf0.format(rows.length)} işlem · toplam ${tl2(sum(rows, (t) => t.v))}`;
    const columns = [
      { key: "d", label: "Tarih", sort: true }, { key: "m", label: "İşyeri / açıklama", sort: true },
      { key: "c", label: "Kategori", sort: true }, { key: "a", label: "Hesap", sort: true },
      { key: "k", label: "Tür" }, { key: "v", label: "Tutar", num: true, sort: true },
    ];
    const table = sortableTable(columns, view.map((t) => ({
      cells: {
        d: h("span", { style: { whiteSpace: "nowrap" } }, dLabel(t.d)),
        m: h("div", {},
          h("div", {}, t.m, t.i ? h("span", { class: "tag", title: "Taksit", text: t.i }) : null,
            t.o ? h("span", { class: "tag", title: "Döviz tutarı", text: t.o }) : null,
            t.p ? h("span", { class: "tag", title: PROVISIONAL_TIP, text: "geçici" }) : null),
          t.t && t.t !== t.m ? h("div", { class: "muted small", text: t.t, title: `Kaynak: ${DATA.sources[t.s] || ""}` }) : null),
        c: h("div", {}, h("span", { class: "cat-cell" }, swatch(groupColor(t.g)), CAT[t.c].name),
          t.n >= 0 ? h("div", { class: "muted small" }, h("span", { class: "level-badge" }, swatch(levelColor(t.n)), LEVELS[t.n].name)) : null),
        a: h("span", { class: "small" }, ACC[t.a].label),
        k: h("span", { class: "muted small", text: KIND[t.k].label }),
        v: h("span", { class: t.v < 0 ? "neg" : null, text: tl2(t.v) }),
      },
    })), {
      sort: state.sort,
      onSort: (k) => {
        state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : k === "d" || k === "v" ? -1 : 1 };
        state.page = 0;
        renderTransactions(select());
      },
    });
    $("transactions").replaceChildren(rows.length ? table : h("p", { class: "empty", text: "Seçili filtrelerle işlem yok." }));
    const go = (p) => { state.page = p; renderTransactions(select()); $("card-transactions").scrollIntoView({ block: "start" }); };
    $("pager").replaceChildren(
      h("button", { type: "button", disabled: state.page === 0, onclick: () => go(state.page - 1) }, "‹ Önceki"),
      h("span", { text: `Sayfa ${state.page + 1} / ${pages}` }),
      h("button", { type: "button", disabled: state.page >= pages - 1, onclick: () => go(state.page + 1) }, "Sonraki ›"),
    );
  }

  function exportCSV() {
    const rows = select().sort((a, b) => (a.d < b.d ? -1 : 1));
    const esc = (v) => {
      const str = String(v ?? "");
      return /[";\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
    };
    const lines = [["Tarih", "İşyeri", "Açıklama", "Kategori", "Ana grup", "Gereklilik", "Hesap", "Tür", "Tutar", "Taksit", "Döviz"].join(";")];
    for (const t of rows) {
      lines.push([dLabel(t.d), t.m, t.t, CAT[t.c].name, GRP[t.g].name, t.n >= 0 ? LEVELS[t.n].name : "", ACC[t.a].label, KIND[t.k].label,
        nf2.format(t.v).replace(/\s/g, ""), t.i, t.o].map(esc).join(";"));
    }
    const blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const a = h("a", { href: URL.createObjectURL(blob), download: "islemler-filtreli.csv" });
    document.body.append(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  // --------------------------------------------------------------- sources
  function renderCoverage(scoped) {
    const box = $("coverage");
    box.replaceChildren();
    const covAccounts = scoped.filter((a) => DATA.coverage[a.i]);
    if (!covAccounts.length) return;
    const all = covAccounts.flatMap((a) => Object.keys(DATA.coverage[a.i])).sort();
    const months = monthsBetween(all[0], all.at(-1));
    const grid = h("div", { class: "cov", style: { gridTemplateColumns: "max-content 1fr" } });
    let lastLabel = -99;
    const years = h("div", { class: "years" }, ...months.map((m, i) => {
      const show = (m.endsWith("-01") || i === 0) && i - lastLabel >= 5;
      if (show) lastLabel = i;
      return h("span", { style: { width: "9px" }, text: show ? m.slice(0, 4) : "" });
    }));
    grid.append(h("span", {}), years);
    for (const a of covAccounts) {
      const cov = DATA.coverage[a.i];
      grid.append(h("span", { class: "clabel", text: a.label }), h("div", { class: "cells" }, ...months.map((m) => {
        const v = cov[m] || 0;
        const status = v >= 0.97 ? "belge var" : v > 0 ? "kısmen" : "belge yok";
        const cell = h("i", { class: v >= 0.97 ? "full" : v > 0 ? "part" : null, tabindex: 0, "aria-label": `${a.label} ${mLong(m)}: ${status}` });
        hoverable(cell, () => [ttTitle(`${a.label} · ${mLong(m)}`),
          ttNote(v >= 0.97 ? "Ayın tamamı ekstre veya hesap dökümüyle kapsanıyor." : v > 0 ? `Kapsanan gün oranı: %${Math.round(v * 100)}.` : "Bu ay için belge yok.")]);
        return cell;
      })));
    }
    box.append(h("div", { class: "cov-legend" },
      h("span", {}, h("i", { style: { background: "var(--seq-500)" } }), "Belge var"),
      h("span", {}, h("i", { style: { background: "var(--seq-200)" } }), "Kısmen"),
      h("span", {}, h("i", { style: { background: "var(--grid)" } }), "Belge yok")), grid);
  }

  function renderSources() {
    const meta = DATA.meta;
    $("sources-summary").textContent =
      `${nf0.format(meta.documents)} benzersiz belge tarandı (${nf0.format(meta.duplicates)} kopya atlandı): ` +
      `${meta.statements} kart ekstresi, ${meta.accountStatements} hesap hareketi dökümü ve ${meta.receipts} dekont işlendi` +
      (meta.business ? `, ${meta.business} şirket belgesi kapsam dışı bırakıldı` : "") +
      (meta.skipped ? `, ${meta.skipped} belge ekstre olmadığı için atlandı` : "") +
      (meta.errors ? `, ${meta.errors} belge okunamadı.` : ".");

    const scoped = ACC.map((a, i) => ({ ...a, i })).filter((a) => !state.accounts || state.accounts.has(a.i));
    renderCoverage(scoped);
    const notes = scoped.filter((a) => !DATA.coverage[a.i]).map((a) => {
      const list = TX.filter((t) => t.a === a.i);
      if (!list.length) return null;
      const first = list.reduce((x, t) => (t.d < x ? t.d : x), list[0].d);
      const last = list.reduce((x, t) => (t.d > x ? t.d : x), list[0].d);
      const out = sum(list.filter((t) => t.v > 0), (t) => t.v);
      return h("li", {}, h("strong", { text: a.label }), ` — ${a.note || "Ekstresi yok; yalnızca dekontlardan okunan işlemler."} ` +
        `${nf0.format(list.length)} işlem (${dLabel(first)} – ${dLabel(last)}), para çıkışı toplamı ${tl(out)}.`);
    }).filter(Boolean);
    const extra = [];
    if (notes.length) extra.push(h("p", { class: "hint", text: "Ekstresi olmayan hesaplar (yalnızca dekontlardan):" }), h("ul", { class: "notes" }, ...notes));
    if (meta.warnings && meta.warnings.length) {
      extra.push(h("p", { class: "hint", text: "Uyarılar:" }), h("ul", { class: "notes" }, ...meta.warnings.map((w) => h("li", { text: w }))));
    }
    $("no-statements").replaceChildren(...extra);

    const st = DATA.statements.filter((x) => scoped.some((a) => a.i === x.a));
    const ok = st.filter((x) => x.ok).length;
    $("statements-details").querySelector("summary").textContent =
      `Belge kontrolü: ${ok}/${st.length} belge tutarlı (kart ekstrelerinde toplam, hesap dökümlerinde satır satır bakiye)`;
    $("statements").replaceChildren(sortableTable([
      { key: "a", label: "Hesap" }, { key: "cut", label: "Dönem", num: true }, { key: "cur", label: "PB" },
      { key: "n", label: "İşlem", num: true }, { key: "total", label: "Belgedeki toplam", num: true },
      { key: "ok", label: "Kontrol" }, { key: "src", label: "Dosya" },
    ], st.map((x) => ({
      cells: {
        a: ACC[x.a].label, cut: x.start ? `${dLabel(x.start)} – ${dLabel(x.cut)}` : dLabel(x.cut), cur: x.cur, n: nf0.format(x.n),
        total: x.total == null ? "–" : nf2.format(x.total),
        ok: h("span", { class: `status ${x.ok ? "ok" : "fail"}` }, h("span", { class: "icon", text: x.ok ? "✓" : "✗" }),
          x.checks ? `Bakiye ${x.checks[0]}/${x.checks[1]}` : x.ok ? "Tutarlı" : `Fark ${x.total == null ? "?" : nf2.format(x.calc - x.total)}`),
        src: h("span", { class: "muted small", text: x.src }),
      },
    }))));
    const docs = DATA.documents.filter((d) => ["atlandi", "hata", "is"].includes(d.status));
    const statusLabel = { hata: "Okunamadı", is: "Şirket belgesi", atlandi: "Atlandı" };
    $("documents-details").querySelector("summary").textContent = `İşlenmeyen belgeler (${docs.length})`;
    $("documents").replaceChildren(sortableTable([{ key: "s", label: "Durum" }, { key: "n", label: "Dosya" }, { key: "d", label: "Açıklama" }],
      docs.map((d) => ({ cells: { s: statusLabel[d.status], n: d.name, d: h("span", { class: "muted", text: d.detail }) } }))));
  }

  // ------------------------------------------------------------- theming
  const THEMES = [["", "Tema: Sistem"], ["light", "Tema: Açık"], ["dark", "Tema: Koyu"]];
  function applyTheme(t) {
    if (t) document.documentElement.dataset.theme = t;
    else delete document.documentElement.dataset.theme;
    $("theme").textContent = THEMES.find(([k]) => k === t)[1];
  }
  function setupTheme() {
    let current = "";
    try { current = localStorage.getItem("gider-tema") || ""; } catch (e) { /* file:// may block storage */ }
    applyTheme(current);
    $("theme").addEventListener("click", () => {
      const i = THEMES.findIndex(([k]) => k === (document.documentElement.dataset.theme || ""));
      const next = THEMES[(i + 1) % THEMES.length][0];
      try { localStorage.setItem("gider-tema", next); } catch (e) { /* storage unavailable: theme lasts this visit */ }
      applyTheme(next);
      update();
    });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", update);
  }

  // ---------------------------------------------------------------- render
  function update() {
    const P = period();
    const F = select({ period: P });
    hideTip();
    renderFilters(P);
    renderKPIs(F, P);
    renderExcluded(P);
    renderMonthly(F, P);
    renderNecessity(F, P);
    renderCashflow(F, P);
    renderForecast();
    renderCategories(F);
    renderMerchants(F);
    renderRecurring(F);
    state.page = 0;
    renderTransactions(F);
    renderSources();
  }

  function init() {
    const months = TX.map((t) => t.mo).sort();
    const meta = DATA.meta;
    $("subtitle").textContent = TX.length
      ? `${mLong(months[0])} – ${mLong(months.at(-1))} · ${nf0.format(TX.length)} işlem · ${meta.statements} kart ekstresi, ${meta.accountStatements} hesap dökümü, ${meta.receipts} dekont`
      : "Veri bulunamadı";
    $("footer").textContent = `Oluşturulma: ${meta.generated}. Rapor tamamen bu dosyanın içindedir; hiçbir veri internete gönderilmez. ` +
      "Kategorileri ve gereklilik seviyelerini kişisel kurallarınızda değiştirebilirsiniz; Claude'dan da isteyebilirsiniz.";
    buildStaticFilters();
    $("export").addEventListener("click", exportCSV);
    setupTheme();
    renderInsights();
    renderHoldings();
    renderClosing();
    renderHabits();
    update();
    let timer;
    new ResizeObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(update, 150);
    }).observe(document.querySelector("main"));
  }

  init();
})();
