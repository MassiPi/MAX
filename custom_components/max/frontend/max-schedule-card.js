/*
 * max-schedule-card — visualizza e modifica il programma settimanale di un termostato.
 * Non tocca mai lo stato del climate: legge e scrive solo il programma tramite due azioni.
 *
 * Contratto con la tua integrazione (formato nativo MAX!: fasce con orario di fine e temperatura):
 *
 *   <dominio>.get_program  { entity_id }  ->  risposta:
 *       { mon: [{ until: "06:00", temp: 17.0 }, { until: "08:00", temp: 21.0 }, { until: "24:00", temp: 17.0 }],
 *         tue: [...], wed: [...], thu: [...], fri: [...], sat: [...], sun: [...] }
 *       (anche annidata in "program" o sotto la chiave entity_id)
 *   <dominio>.set_program  { entity_id, program: { ...stessa struttura... } }
 *
 * Le azioni devono usare supports_response=SupportsResponse.ONLY (get) e accettare i dati (set).
 *
 * Uso:
 *   - Con "Modifica" spento il grafico è di sola lettura (tocca una fascia per vederne i dettagli).
 *   - Con "Modifica" acceso: trascina i bordi delle fasce; l'orario compare mentre trascini.
 *     Se spingi un bordo oltre quello vicino, la fascia in mezzo viene eliminata
 *     (riportandolo indietro, la fascia torna). Tocca una fascia per cambiarne la temperatura,
 *     dividerla, eliminarla o regolare gli orari di 5 minuti alla volta.
 *     Una fascia selezionata si può anche trascinare su/giù per alzarne o abbassarne la temperatura.
 *
 * Config:
 *   type: custom:max-schedule-card
 *   entity: climate.soggiorno
 *   domain: my_max            # opzionale, default = piattaforma dell'entità
 *   get_service: get_program  # opzionale
 *   set_service: set_program  # opzionale
 *   min_temp: 5               # opzionale
 *   max_temp: 30              # opzionale
 *   max_slots: 13             # opzionale (fasce per giorno)
 *   name: Soggiorno           # opzionale
 *   editable: true            # opzionale (false = nessun toggle, solo lettura)
 */

const DAYS = [
  ["mon", "Lun", "Lunedì"], ["tue", "Mar", "Martedì"], ["wed", "Mer", "Mercoledì"],
  ["thu", "Gio", "Giovedì"], ["fri", "Ven", "Venerdì"], ["sat", "Sab", "Sabato"], ["sun", "Dom", "Domenica"],
];
const DAY_END = 1440;
const SNAP = 5; // minuti: risoluzione minima delle fasce
const clone = (o) => JSON.parse(JSON.stringify(o));
const dayLabel = (k) => DAYS.find((d) => d[0] === k)[2];
const fmtT = (t) => Number(t).toFixed(1).replace(/\.0$/, "");

const toMin = (s) => {
  const [h, m] = String(s).split(":").map(Number);
  return h * 60 + (m || 0);
};
const toStr = (m) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

class MaxScheduleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._prog = null;
    this._orig = null;
    this._day = this._todayKey();
    this._edit = false;
    this._sel = null;   // { day, i, at }
    this._copy = null;  // { targets: Set }
    this._drag = null;
    this._status = { kind: "loading", msg: "Carico il programma…" };
    this._loadedFor = null;

    const r = this.shadowRoot;
    r.addEventListener("click", (e) => this._onClick(e));
    r.addEventListener("change", (e) => this._onChange(e));
    r.addEventListener("pointerdown", (e) => this._onDown(e));
    this._move = (e) => this._onMove(e);
    this._up = (e) => this._onUp(e);
  }

  // Usata dal selettore delle card per l'anteprima: sceglie un termostato dell'integrazione max
  static getStubConfig(hass) {
    const ids = Object.keys((hass && hass.states) || {}).filter((e) => e.startsWith("climate."));
    const isCube = (e) => /cube/i.test(`${e} ${(hass.states[e].attributes || {}).friendly_name || ""}`);
    const own = ids.filter((e) => hass.entities && hass.entities[e] && hass.entities[e].platform === "max");
    const pool = own.length ? own : ids;
    return { entity: pool.find((e) => !isCube(e)) || pool[0] || "climate.example", max_slots: 7 };
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Specifica 'entity'");
    this._config = {
      editable: true, min_temp: 5, max_temp: 30, max_slots: 13,
      get_service: "get_program", set_service: "set_program", ...config,
    };
    this._config.domain = config.domain || null;  // se assente, lo ricavo dal registro entità in _load()
    this._loadedFor = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config && this._loadedFor !== this._config.entity) {
      this._loadedFor = this._config.entity;
      this._load();
    }
  }

  getCardSize() { return 7; }

  _todayKey() { return DAYS[(new Date().getDay() + 6) % 7][0]; }
  _dirty() { return JSON.stringify(this._prog) !== JSON.stringify(this._orig); }
  _editing() { return !!this._config && this._config.editable !== false && this._edit; }

  /* ------------------------------ comunicazione ------------------------------ */

  async _call(service, data, withResponse = false) {
    const res = await this._hass.connection.sendMessagePromise({
      type: "call_service",
      domain: this._domain,
      service,
      service_data: data,
      return_response: withResponse,
    });
    return res && res.response !== undefined ? res.response : res;
  }

  async _load() {
    this._status = { kind: "loading", msg: "Carico il programma…" };
    this._render();
    try {
      this._domain = this._config.domain;
      if (!this._domain) {
        const reg = await this._hass.callWS({ type: "config/entity_registry/get", entity_id: this._config.entity });
        this._domain = reg.platform;
      }
      let r = await this._call(this._config.get_service, { entity_id: this._config.entity }, true);
      if (r && r[this._config.entity]) r = r[this._config.entity];
      if (r && r.program) r = r.program;
      this._prog = this._normalize(r);
      this._orig = clone(this._prog);
      this._sel = null;
      this._copy = null;
      this._status = { kind: "ok", msg: "" };
    } catch (e) {
      this._status = { kind: "error", msg: `Lettura fallita: ${e.message || e.code || e}` };
    }
    this._render();
  }

  _normalize(raw) {
    const out = {};
    for (const [k] of DAYS) {
      const slots = (raw && raw[k]) || [];
      if (!slots.length) throw new Error(`giorno '${k}' mancante nella risposta`);
      out[k] = slots.map((s) => ({
        until: toMin(s.until ?? s.end ?? s.endtime),
        temp: Number(s.temp ?? s.temperature),
      }));
      out[k][out[k].length - 1].until = DAY_END;
    }
    return out;
  }

  _validate() {
    const { min_temp, max_temp, max_slots } = this._config;
    for (const [k, , label] of DAYS) {
      const s = this._prog[k];
      if (s.length > max_slots) return `${label}: massimo ${max_slots} fasce`;
      let prev = 0;
      for (const slot of s) {
        if (slot.until <= prev) return `${label}: gli orari devono essere crescenti`;
        if (!(slot.temp >= min_temp && slot.temp <= max_temp)) return `${label}: temperatura fuori da ${min_temp}–${max_temp} °C`;
        prev = slot.until;
      }
    }
    return null;
  }

  async _save() {
    const err = this._validate();
    if (err) { this._status = { kind: "error", msg: err }; return this._render(); }
    const program = {};
    for (const [k] of DAYS) program[k] = this._prog[k].map((s) => ({ until: toStr(s.until), temp: s.temp }));
    this._status = { kind: "loading", msg: "Scrivo sul dispositivo…" };
    this._render();
    try {
      await this._call(this._config.set_service, { entity_id: this._config.entity, program });
      this._orig = clone(this._prog);
      this._status = { kind: "ok", msg: "Programma salvato" };
    } catch (e) {
      this._status = { kind: "error", msg: `Salvataggio fallito: ${e.message || e.code || e}` };
    }
    this._render();
  }

  /* ------------------------------ logica fasce ------------------------------ */

  /*
   * Sposta il bordo `i` (la fine della fascia i) a `p` partendo da una copia `snap` delle fasce.
   * Calcolare sempre dallo stato iniziale del trascinamento rende l'operazione reversibile:
   * se riporti indietro il bordo, le fasce eliminate ricompaiono.
   */
  _applyDrag(snap, i, p) {
    const b = snap[i].until;
    const out = [];
    snap.forEach((s, j) => {
      const start = j === 0 ? 0 : snap[j - 1].until;
      if (p < b) {
        if (j <= i) {
          if (start >= p) return;                       // fascia schiacciata: eliminata
          out.push({ until: Math.min(s.until, p), temp: s.temp });
        } else out.push({ ...s });
      } else if (j < i) out.push({ ...s });
      else if (j === i) out.push({ until: p, temp: s.temp });
      else if (s.until > p) out.push({ ...s });         // fasce inghiottite dal bordo: eliminate
    });
    return out;
  }

  _clampMin(m) { return Math.min(DAY_END - SNAP, Math.max(SNAP, Math.round(m / SNAP) * SNAP)); }
  _minAt(bar, x) { const r = bar.getBoundingClientRect(); return ((x - r.left) / r.width) * DAY_END; }
  _start(slots, i) { return i === 0 ? 0 : slots[i - 1].until; }

  /* ------------------------------ interazione ------------------------------ */

  _listen() {
    window.addEventListener("pointermove", this._move);
    window.addEventListener("pointerup", this._up);
    window.addEventListener("pointercancel", this._up);
  }

  _onDown(e) {
    if (!this._editing() || (e.button !== undefined && e.button > 0)) return;
    const h = e.target.closest("[data-handle]");
    if (h) {
      e.preventDefault();
      const day = h.dataset.day;
      const i = Number(h.dataset.i);
      const bar = this.shadowRoot.querySelector(`.bar[data-day="${day}"]`);
      const snap = clone(this._prog[day]);
      this._drag = {
        kind: "time", day, i, bar, snap, count: snap.length, pid: e.pointerId,
        off: snap[i].until - this._minAt(bar, e.clientX),
        pos: snap[i].until,
      };
      this._day = day;
      this._sel = null;
      this._copy = null;
      this._listen();
      bar.innerHTML = this._barInner(day);
      return;
    }
    // trascinamento verticale: solo sulla fascia già selezionata (le altre lasciano scorrere la pagina)
    const seg = e.target.closest('i.on[data-act="seg"]');
    if (seg) {
      e.preventDefault();
      const day = seg.dataset.day;
      const i = Number(seg.dataset.i);
      this._drag = {
        kind: "temp", day, i, pid: e.pointerId, y: e.clientY,
        bar: seg.closest(".bar"), t0: this._prog[day][i].temp,
      };
      this._listen();
      this._drag.bar.innerHTML = this._barInner(day);
    }
  }

  _onMove(e) {
    const d = this._drag;
    if (!d || e.pointerId !== d.pid) return;
    if (d.kind === "temp") {
      const steps = Math.round((d.y - e.clientY) / 8); // 8 px = 0,5 °C
      this._prog[d.day][d.i].temp = this._clampTemp(d.t0 + steps * 0.5);
    } else {
      d.pos = this._clampMin(this._minAt(d.bar, e.clientX) + d.off);
      this._prog[d.day] = this._applyDrag(d.snap, d.i, d.pos);
    }
    d.bar.innerHTML = this._barInner(d.day);
  }

  _onUp(e) {
    const d = this._drag;
    if (!d || e.pointerId !== d.pid) return;
    window.removeEventListener("pointermove", this._move);
    window.removeEventListener("pointerup", this._up);
    window.removeEventListener("pointercancel", this._up);
    this._drag = null;
    this._status = { kind: "ok", msg: "" };
    this._render();
  }

  _onChange(e) {
    const el = e.target.closest("[data-act]");
    if (!el || el.dataset.act !== "tempinput" || !this._sel) return;
    const s = this._prog[this._sel.day][this._sel.i];
    const v = Number(String(el.value).replace(",", "."));
    s.temp = this._clampTemp(isNaN(v) ? s.temp : v);
    this._render();
  }

  _clampTemp(t) {
    const { min_temp, max_temp } = this._config;
    return Math.min(max_temp, Math.max(min_temp, Math.round(t * 2) / 2));
  }

  _onClick(e) {
    const el = e.target.closest("[data-act]");
    if (!el || el.disabled || el.tagName === "INPUT") return;
    const act = el.dataset.act;
    const sel = this._sel;
    const slots = sel && this._prog && this._prog[sel.day];

    switch (act) {
      case "reload": return this._load();
      case "save": return this._save();
      case "revert":
        this._prog = clone(this._orig);
        this._sel = null;
        this._status = { kind: "ok", msg: "" };
        break;
      case "toggleedit":
        this._edit = !this._edit;
        this._copy = null;
        break;
      case "day":
        this._day = el.dataset.day;
        this._sel = null;
        if (this._copy) this._copy.targets.delete(this._day);
        break;
      case "seg": {
        const day = el.dataset.day;
        const bar = el.closest(".bar");
        const at = Math.round(this._minAt(bar, e.clientX) / SNAP) * SNAP;
        this._day = day;
        this._sel = { day, i: Number(el.dataset.i), at };
        if (this._copy) this._copy.targets.delete(day);
        break;
      }
      case "tempstep": {
        const s = slots[sel.i];
        s.temp = this._clampTemp(s.temp + Number(el.dataset.d));
        break;
      }
      case "nudge": {
        const b = Number(el.dataset.b);
        const p = this._clampMin(slots[b].until + Number(el.dataset.d));
        const next = this._applyDrag(clone(slots), b, p);
        if (next.length !== slots.length) this._sel = null;
        this._prog[sel.day] = next;
        break;
      }
      case "split": {
        const s = slots[sel.i];
        const start = this._start(slots, sel.i);
        const at = Math.min(s.until - SNAP, Math.max(start + SNAP, sel.at));
        slots.splice(sel.i, 0, { until: at, temp: s.temp });
        break;
      }
      case "del": {
        slots.splice(sel.i, 1);
        slots[slots.length - 1].until = DAY_END;
        this._sel = null;
        break;
      }
      case "copyopen": this._copy = { targets: new Set() }; break;
      case "copycancel": this._copy = null; break;
      case "copytoggle": {
        const k = el.dataset.day;
        if (this._copy.targets.has(k)) this._copy.targets.delete(k); else this._copy.targets.add(k);
        break;
      }
      case "copyapply": {
        const src = this._prog[this._day];
        const n = this._copy.targets.size;
        for (const k of this._copy.targets) this._prog[k] = clone(src);
        this._copy = null;
        this._sel = null;
        this._status = { kind: "ok", msg: `${dayLabel(this._day)} copiato su ${n} ${n === 1 ? "giorno" : "giorni"}` };
        break;
      }
    }
    if (act !== "copyapply" && ["tempstep", "nudge", "split", "del"].includes(act)) this._status = { kind: "ok", msg: "" };
    this._render();
  }

  /* ------------------------------ rendering ------------------------------ */

  _color(t) {
    const { min_temp, max_temp } = this._config;
    const f = Math.min(1, Math.max(0, (t - min_temp) / (max_temp - min_temp)));
    return `hsl(${Math.round(220 - f * 210)} 65% 52%)`;
  }

  _barInner(day) {
    const slots = this._prog[day];
    const edit = this._editing();
    const drag = this._drag && this._drag.day === day ? this._drag : null;
    let start = 0;
    const segs = slots.map((s, i) => {
      const w = ((s.until - start) / DAY_END) * 100;
      const on = this._sel && this._sel.day === day && this._sel.i === i ? "on" : "";
      const label = w >= 8 || on ? `<span>${fmtT(s.temp)}</span>` : "";
      const html = `<i class="${on}" data-act="seg" data-day="${day}" data-i="${i}" style="width:${w}%;background:${this._color(s.temp)}" title="${toStr(start)}–${toStr(s.until)}  ${fmtT(s.temp)} °C">${label}</i>`;
      start = s.until;
      return html;
    }).join("");

    const handles = edit
      ? slots.slice(0, -1).map((s, i) =>
        `<b class="h ${drag && drag.kind === "time" && s.until === drag.pos ? "on" : ""}" data-handle="1" data-day="${day}" data-i="${i}" style="left:${(s.until / DAY_END) * 100}%"></b>`).join("")
      : "";

    let tip = "";
    if (drag && drag.kind === "temp") {
      const c = (this._start(slots, drag.i) + slots[drag.i].until) / 2;
      tip = `<div class="tip" style="left:clamp(2.6em, ${(c / DAY_END) * 100}%, calc(100% - 2.6em))">${fmtT(slots[drag.i].temp)} °C</div>`;
    } else if (drag) {
      const gone = drag.count - slots.length;
      const extra = gone > 0 ? ` · −${gone} ${gone === 1 ? "fascia" : "fasce"}` : "";
      tip = `<div class="tip ${gone > 0 ? "warn" : ""}" style="left:clamp(2.6em, ${(drag.pos / DAY_END) * 100}%, calc(100% - 2.6em))">${toStr(drag.pos)}${extra}</div>`;
    }

    return `<div class="segs">${segs}</div>${handles}${tip}`;
  }

  _panel() {
    const edit = this._editing();
    const sel = this._sel;
    const slots = sel && this._prog[sel.day];
    if (!sel || !slots || !slots[sel.i]) {
      return `<div class="hint">${edit
        ? "Trascina i bordi per spostarli. Tocca una fascia per modificarla."
        : "Tocca una fascia per vederne i dettagli."}</div>`;
    }
    const s = slots[sel.i];
    const start = this._start(slots, sel.i);
    const { min_temp, max_temp, max_slots } = this._config;
    const info = `<div class="info"><b>${dayLabel(sel.day)}</b>
        <span class="range">${toStr(start)}–${toStr(s.until)}</span>
        <span class="tag" style="background:${this._color(s.temp)}">${fmtT(s.temp)} °C</span></div>`;
    if (!edit) return `<div class="panel">${info}</div>`;

    const at = Math.min(s.until - SNAP, Math.max(start + SNAP, sel.at));
    const canSplit = s.until - start >= SNAP * 2 && slots.length < max_slots;
    const first = sel.i === 0;
    const last = sel.i === slots.length - 1;
    return `<div class="panel">
      ${info}
      <div class="muted">Trascina la fascia su o giù per cambiarne la temperatura.</div>
      <div class="ctrl">
        <span class="muted">Temperatura</span>
        <button class="icon" data-act="tempstep" data-d="-0.5" ${s.temp <= min_temp ? "disabled" : ""} aria-label="Meno 0,5 gradi">−</button>
        <input type="number" inputmode="decimal" min="${min_temp}" max="${max_temp}" step="0.5" value="${s.temp}" data-act="tempinput" aria-label="Temperatura">
        <button class="icon" data-act="tempstep" data-d="0.5" ${s.temp >= max_temp ? "disabled" : ""} aria-label="Più 0,5 gradi">+</button>
      </div>
      <div class="ctrl">
        <span class="muted">Inizio</span>
        ${first ? `<span class="fixed">00:00</span>` : `
          <button class="icon" data-act="nudge" data-b="${sel.i - 1}" data-d="-${SNAP}" aria-label="Inizio ${SNAP} minuti prima">‹</button>
          <span class="fixed">${toStr(start)}</span>
          <button class="icon" data-act="nudge" data-b="${sel.i - 1}" data-d="${SNAP}" aria-label="Inizio ${SNAP} minuti dopo">›</button>`}
        <span class="muted gap">Fine</span>
        ${last ? `<span class="fixed">24:00</span>` : `
          <button class="icon" data-act="nudge" data-b="${sel.i}" data-d="-${SNAP}" aria-label="Fine ${SNAP} minuti prima">‹</button>
          <span class="fixed">${toStr(s.until)}</span>
          <button class="icon" data-act="nudge" data-b="${sel.i}" data-d="${SNAP}" aria-label="Fine ${SNAP} minuti dopo">›</button>`}
      </div>
      <div class="ctrl">
        <button data-act="split" ${canSplit ? "" : "disabled"}>Dividi alle ${toStr(at)}</button>
        <button class="danger" data-act="del" ${slots.length === 1 ? "disabled" : ""}>Elimina fascia</button>
      </div>
    </div>`;
  }

  _copyBlock() {
    if (!this._editing() || !this._prog) return "";
    if (!this._copy) {
      return `<div class="ctrl"><button data-act="copyopen">Copia ${dayLabel(this._day)} su…</button></div>`;
    }
    const chips = DAYS.filter(([k]) => k !== this._day).map(([k, short]) =>
      `<button class="chip ${this._copy.targets.has(k) ? "on" : ""}" data-act="copytoggle" data-day="${k}" aria-pressed="${this._copy.targets.has(k)}">${short}</button>`).join("");
    return `<div class="copy">
      <div class="muted">Copia <b>${dayLabel(this._day)}</b> sui giorni selezionati</div>
      <div class="chips">${chips}</div>
      <div class="ctrl">
        <button class="primary" data-act="copyapply" ${this._copy.targets.size ? "" : "disabled"}>Copia</button>
        <button data-act="copycancel">Annulla</button>
      </div>
    </div>`;
  }

  _render() {
    const root = this.shadowRoot;
    const c = this._config;
    if (!c) return;
    const loading = this._status.kind === "loading";
    const ready = this._prog && !loading;
    const canEdit = c.editable !== false;
    const edit = this._editing();
    const today = this._todayKey();

    const nd = new Date();
    const nowMin = nd.getHours() * 60 + nd.getMinutes();
    const nowPct = (nowMin / DAY_END) * 100;
    const ticks = [0, 3, 6, 9, 12, 15, 18, 21, 24].map((h) => {
      const tf = h === 0 ? "none" : h === 24 ? "translateX(-100%)" : "translateX(-50%)";
      return `<span style="left:${(h / 24) * 100}%;transform:${tf}">${h % 6 === 0 ? h : ""}</span>`;
    }).join("");

    const edge = `clamp(5px, ${nowPct}%, calc(100% - 5px))`; // le frecce non escono dal bordo
    const nowMark = `<s class="nowmark" style="left:${edge}" title="Adesso ${toStr(nowMin)}"></s>`;

    const body = this._prog
      ? `<div class="week ${edit ? "edit" : ""}">
          <div class="nowlayer" aria-hidden="true"><s class="nowtop" style="left:${edge}"></s><u class="nowline" style="left:${nowPct}%"></u></div>
          ${DAYS.map(([k, short]) => `
          <div class="row">
            <button class="dn ${k === this._day ? "sel" : ""} ${k === today ? "today" : ""}" data-act="day" data-day="${k}" title="${dayLabel(k)}">${short}</button>
            <div class="bar" data-day="${k}">${this._barInner(k)}</div>
          </div>`).join("")}
          <div class="row"><span></span><div class="ticks">${ticks}${nowMark}</div></div>
        </div>
        ${this._panel()}
        ${this._copyBlock()}`
      : "";

    const name = c.name || (this._hass && this._hass.states[c.entity] && this._hass.states[c.entity].attributes.friendly_name) || c.entity;
    const showFoot = canEdit && this._prog && (edit || this._dirty());

    root.innerHTML = `
      <style>
        :host { display:block; }
        ha-card { padding:16px; }
        * { box-sizing:border-box; }
        .head { display:flex; align-items:center; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
        .head h2 { margin:0; font-size:1.15rem; font-weight:500; flex:1; min-width:8em; color:var(--primary-text-color); }

        button { font:inherit; font-size:.85rem; cursor:pointer; color:var(--primary-text-color); background:var(--secondary-background-color); border:1px solid var(--divider-color); border-radius:8px; padding:6px 12px; min-height:34px; }
        button:hover:not(:disabled) { border-color:var(--primary-color); }
        button.primary { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:transparent; }
        button.danger { color:var(--error-color,#db4437); }
        button.icon { min-width:34px; padding:6px 0; font-size:1rem; line-height:1; }
        button:disabled { opacity:.4; cursor:default; }
        button:focus-visible, input:focus-visible, .h:focus-visible { outline:2px solid var(--primary-color); outline-offset:2px; }

        .switch { display:inline-flex; align-items:center; gap:8px; padding:4px 12px 4px 5px; border-radius:999px; }
        .switch .knob { width:34px; height:20px; border-radius:999px; background:var(--divider-color); position:relative; transition:background .15s; }
        .switch .knob::after { content:""; position:absolute; top:2px; left:2px; width:16px; height:16px; border-radius:50%; background:var(--card-background-color,#fff); box-shadow:0 1px 2px rgba(0,0,0,.35); transition:transform .15s; }
        .switch.on { border-color:var(--primary-color); }
        .switch.on .knob { background:var(--primary-color); }
        .switch.on .knob::after { transform:translateX(14px); }

        .week { position:relative; display:flex; flex-direction:column; gap:5px; padding-top:28px; }
        .row { display:grid; grid-template-columns:2.8em 1fr; gap:10px; align-items:center; }
        .dn { min-height:0; padding:4px 0; border-color:transparent; background:none; color:var(--secondary-text-color); border-radius:6px; }
        .dn.today { color:var(--primary-text-color); font-weight:600; }
        .dn.sel { background:var(--secondary-background-color); border-color:var(--primary-color); color:var(--primary-text-color); }

        .bar { position:relative; z-index:1; height:20px; user-select:none; -webkit-user-select:none; transition:height .15s; }
        .week.edit .bar { height:28px; }
        .segs { position:relative; display:flex; height:100%; border-radius:7px; overflow:hidden; background:var(--divider-color); }
        .segs i { display:flex; align-items:center; justify-content:center; font-style:normal; font-size:.7rem; color:#fff; min-width:1px; cursor:pointer; box-shadow:inset -1px 0 0 rgba(0,0,0,.25); text-shadow:0 1px 1px rgba(0,0,0,.3); }
        .week.edit .segs i.on { cursor:ns-resize; touch-action:none; }
        .segs i.on { box-shadow:inset 0 0 0 2px #fff, inset 0 0 0 3px rgba(0,0,0,.35); }

        .h { position:absolute; top:-3px; bottom:-3px; width:20px; margin-left:-10px; display:flex; justify-content:center; align-items:center; cursor:ew-resize; touch-action:none; z-index:2; }
        .h::before { content:""; width:5px; height:100%; border-radius:3px; background:#fff; box-shadow:0 0 0 1px rgba(0,0,0,.5); transition:width .1s; }
        .h:hover::before { width:7px; }
        .h.on::before { width:7px; background:var(--primary-color); box-shadow:0 0 0 2px #fff, 0 0 0 3px rgba(0,0,0,.4); }

        .tip { position:absolute; bottom:calc(100% + 8px); transform:translateX(-50%); z-index:5; pointer-events:none; white-space:nowrap; padding:3px 9px; border-radius:7px; font-size:.8rem; font-variant-numeric:tabular-nums; background:var(--primary-text-color); color:var(--card-background-color,#fff); box-shadow:0 2px 6px rgba(0,0,0,.3); }
        .tip.warn { background:var(--error-color,#db4437); color:#fff; }

        .ticks { position:relative; height:1.1em; font-size:.7rem; color:var(--secondary-text-color); font-variant-numeric:tabular-nums; }
        .ticks span { position:absolute; top:0; }
        .nowlayer { position:absolute; top:0; bottom:calc(.77rem + 5px); left:calc(2.8em + 10px); right:0; pointer-events:none; z-index:0; }
        .nowline { position:absolute; top:28px; bottom:0; width:2px; margin-left:-1px; border-radius:1px; background:var(--primary-color); opacity:.55; }
        .nowtop { position:absolute; top:22px; width:0; height:0; transform:translateX(-50%); border-left:5px solid transparent; border-right:5px solid transparent; border-top:6px solid var(--primary-color); }
        .nowmark { position:absolute; top:-5px; width:0; height:0; transform:translateX(-50%); border-left:5px solid transparent; border-right:5px solid transparent; border-bottom:6px solid var(--primary-color); }

        .hint { margin-top:14px; font-size:.85rem; color:var(--secondary-text-color); }
        .panel, .copy { margin-top:14px; padding:12px; border-radius:10px; background:var(--secondary-background-color); display:flex; flex-direction:column; gap:10px; }
        .info { display:flex; align-items:center; gap:10px; flex-wrap:wrap; color:var(--primary-text-color); }
        .range { font-variant-numeric:tabular-nums; color:var(--secondary-text-color); }
        .tag { color:#fff; border-radius:6px; padding:1px 8px; font-size:.85rem; text-shadow:0 1px 1px rgba(0,0,0,.3); }
        .ctrl { display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-top:2px; }
        .panel .ctrl, .copy .ctrl { margin-top:0; }
        .week + .ctrl, .panel + .ctrl, .hint + .ctrl { margin-top:12px; }
        .muted { color:var(--secondary-text-color); font-size:.85rem; }
        .gap { margin-left:12px; }
        .muted b { color:var(--primary-text-color); font-weight:500; }
        .fixed { font-variant-numeric:tabular-nums; min-width:3.2em; text-align:center; color:var(--primary-text-color); }
        input[type=number] { font:inherit; width:4.6em; text-align:center; color:var(--primary-text-color); background:var(--card-background-color); border:1px solid var(--divider-color); border-radius:8px; padding:6px 4px; min-height:34px; }
        .chips { display:flex; flex-wrap:wrap; gap:6px; }
        .chip { border-radius:999px; min-width:3.2em; }
        .chip.on { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:transparent; }

        .foot { display:flex; align-items:center; gap:8px; margin-top:14px; flex-wrap:wrap; }
        .msg { font-size:.85rem; flex:1; min-width:8em; color:var(--secondary-text-color); }
        .msg.error { color:var(--error-color,#db4437); }

        @media (prefers-reduced-motion: reduce) { * { transition:none !important; } }
      </style>
      <ha-card>
        <div class="head"><h2>${name}</h2>
          ${canEdit ? `<button class="switch ${edit ? "on" : ""}" role="switch" aria-checked="${edit}" data-act="toggleedit" ${this._prog ? "" : "disabled"}><span class="knob"></span>Modifica</button>` : ""}
          <button data-act="reload" ${ready ? "" : "disabled"} title="Rileggi dal dispositivo">Aggiorna</button></div>
        ${body}
        <div class="foot">
          <span class="msg ${this._status.kind === "error" ? "error" : ""}">${this._status.msg}</span>
          ${showFoot ? `
            <button data-act="revert" ${ready && this._dirty() ? "" : "disabled"}>Annulla modifiche</button>
            <button class="primary" data-act="save" ${ready && this._dirty() ? "" : "disabled"}>Salva sul dispositivo</button>` : ""}
        </div>
      </ha-card>`;
  }
}

customElements.define("max-schedule-card", MaxScheduleCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "max-schedule-card",
  name: "MAX! Schedule Card",
  preview: true,
  description: "Visualizza e modifica il programma settimanale di un termostato senza toccarne lo stato.",
});
