// Copyright (c) 2026 Pissbirne and PixelIt project contributors. MIT license.
import { LitElement, html, css, nothing } from "lit";

const CARD_NAME = "pixelit-card";
const CARD_TYPE = "custom:" + CARD_NAME;
const EDITOR_TAG = CARD_NAME + "-editor";
const PIXELIT_ENTITY_SELECTOR = {
  entity: { filter: [{ domain: "sensor", integration: "pixelit" }] },
};
function isLiveviewSensor(hass, id) {
  const attributes = hass?.states?.[id]?.attributes;
  return (
    id.startsWith("sensor.") &&
    hass?.entities?.[id]?.platform === "pixelit" &&
    attributes &&
    ("hex" in attributes || "pixels" in attributes) &&
    Number.isInteger(attributes.width) &&
    Number.isInteger(attributes.height)
  );
}
function liveviewEntities(hass) {
  return Object.keys(hass?.entities ?? {}).filter((id) =>
    isLiveviewSensor(hass, id),
  );
}

// ===== i18n =====
const I18N = {
  de: {
    controls: "Display-Steuerung",
    light_entity: "Display-Licht",
    show_power: "Ein/Aus anzeigen",
    show_brightness: "Helligkeit anzeigen",
    power: "Display ein/aus",
    brightness: "Helligkeit",
    control_unavailable: "Display-Licht nicht verfügbar oder nicht ausgewählt",
    control_failed: "Display-Steuerung fehlgeschlagen",
    actions: "Aktionen",
    tap_action: "Tippen",
    hold_action: "Gedrückt halten",
    double_tap_action: "Doppeltippen",
    title: "Titel",
    entity: "PixelIt-Sensor",
    width: "Matrix-Breite (Pixel)",
    height: "Matrix-Höhe (Pixel)",
    gap: "Abstand zwischen Pixeln (px)",
    show_header: "Titel anzeigen",
    transparent: "Transparenter Hintergrund",
    advanced: "Erweitert",
    show_status: "Verbindungsstatus anzeigen",
    show_pixels: "Pixel anzeigen",
    general: "Allgemein",
    display: "Anzeige",
    connected: "Verbunden",
    disconnected: "Getrennt",
    no_data: "Warte auf Bilddaten",
    no_entity: "Kein PixelIt-Sensor ausgewählt",
    missing_entity: "PixelIt-Sensor nicht verfügbar",
    card_title: "PixelIt",
    pixelit_settings: "PixelIt-Einstellungen",
    display_options: "Anzeige-Optionen",
  },
  en: {
    controls: "Display controls",
    light_entity: "Display light",
    show_power: "Show power control",
    show_brightness: "Show brightness control",
    power: "Display power",
    brightness: "Brightness",
    control_unavailable: "Display light unavailable or not selected",
    control_failed: "Display control failed",
    actions: "Actions",
    tap_action: "Tap",
    hold_action: "Hold",
    double_tap_action: "Double tap",
    title: "Title",
    entity: "PixelIt sensor",
    width: "Matrix width (pixels)",
    height: "Matrix height (pixels)",
    gap: "Gap between pixels (px)",
    show_header: "Show title",
    transparent: "Transparent background",
    advanced: "Advanced",
    show_status: "Show connection status",
    show_pixels: "Show pixels",
    general: "General",
    display: "Display",
    connected: "Connected",
    disconnected: "Disconnected",
    no_data: "Waiting for a frame",
    no_entity: "No PixelIt sensor selected",
    missing_entity: "PixelIt sensor unavailable",
    card_title: "PixelIt",
    pixelit_settings: "PixelIt settings",
    display_options: "Display options",
  },
};
function getLang(hass) {
  const lang = (hass.locale?.language || hass.language || "en").split("-")[0];
  return I18N[lang] ? lang : "en";
}
function tr(hass, key) {
  if (!hass) return I18N.en[key] || key;
  const lang = getLang(hass);
  return (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;
}

const ACTION_DEFAULTS = {
  tap_action: "more-info",
  hold_action: "none",
  double_tap_action: "none",
};
const CARD_DEFAULTS = {
  title: "",
  entity: "",
  gap: 1,
  show_header: true,
  show_status: true,
  show_pixels: true,
  transparent: false,
  light_entity: "",
  show_power: false,
  show_brightness: false,
};
function normalizeConfig(config) {
  if (!config || typeof config !== "object" || Array.isArray(config))
    throw new Error("Invalid PixelIt card configuration");
  const provided = Object.fromEntries(
    Object.entries(config).filter(([, value]) => value !== undefined),
  );
  const result = {
    ...CARD_DEFAULTS,
    ...provided,
    type: config.type || CARD_TYPE,
  };
  if (
    typeof result.entity !== "string" ||
    (result.entity && !result.entity.startsWith("sensor."))
  )
    throw new Error("PixelIt requires a sensor entity");
  if (
    typeof result.light_entity !== "string" ||
    (result.light_entity && !result.light_entity.startsWith("light."))
  )
    throw new Error("Display controls require a light entity");
  if (typeof result.title !== "string")
    throw new Error("PixelIt title must be text");
  if (!Number.isInteger(result.gap) || result.gap < 0 || result.gap > 16)
    throw new Error("Pixel gap must be an integer from 0 to 16");
  for (const key of [
    "show_header",
    "show_status",
    "show_pixels",
    "transparent",
    "show_power",
    "show_brightness",
  ]) {
    if (typeof result[key] !== "boolean")
      throw new Error(key + " must be true or false");
  }
  for (const key of ["tap_action", "hold_action", "double_tap_action"]) {
    const action = result[key] ?? { action: ACTION_DEFAULTS[key] };
    if (
      typeof action !== "object" ||
      Array.isArray(action) ||
      typeof action.action !== "string"
    )
      throw new Error(key + " must be an action configuration");
    result[key] = { ...action };
  }
  return result;
}

// The editor uses native HA form controls while keeping language-aware labels.
class PixelItCardEditor extends LitElement {
  static properties = { hass: { attribute: false }, _config: { state: true } };
  constructor() {
    super();
    this._computeLabel = this._computeLabel.bind(this);
  }
  setConfig(config) {
    this._config = normalizeConfig(config);
  }
  _valueChanged(event) {
    event.stopPropagation();
    this._config = normalizeConfig({ ...this._config, ...event.detail.value });
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      }),
    );
  }
  _computeLabel(schema) {
    return tr(this.hass, schema.name || "advanced");
  }
  render() {
    if (!this._config || !this.hass) return html``;
    const language = getLang(this.hass);
    const ids = liveviewEntities(this.hass);
    const entityKey = ids.join(";");
    const schema =
      this._schemaLanguage === language && this._schemaEntities === entityKey
        ? this._schema
        : [
            {
              name: "entity",
              required: true,
              selector: {
                entity: {
                  ...PIXELIT_ENTITY_SELECTOR.entity,
                  include_entities: ids,
                },
              },
            },
            { name: "title", selector: { text: {} } },
            { name: "show_header", selector: { boolean: {} } },
            { name: "show_status", selector: { boolean: {} } },
            { name: "show_pixels", selector: { boolean: {} } },
            { name: "transparent", selector: { boolean: {} } },
            {
              name: "",
              type: "expandable",
              title: tr(this.hass, "controls"),
              flatten: true,
              schema: [
                {
                  name: "light_entity",
                  selector: {
                    entity: {
                      filter: [{ domain: "light", integration: "pixelit" }],
                    },
                  },
                },
                { name: "show_power", selector: { boolean: {} } },
                { name: "show_brightness", selector: { boolean: {} } },
              ],
            },
            {
              name: "",
              type: "expandable",
              title: tr(this.hass, "actions"),
              flatten: true,
              schema: [
                ...["tap_action", "hold_action", "double_tap_action"].map(
                  (name) => ({
                    name,
                    selector: {
                      ui_action: { default_action: ACTION_DEFAULTS[name] },
                    },
                  }),
                ),
              ],
            },
            {
              name: "",
              type: "expandable",
              title: tr(this.hass, "advanced"),
              flatten: true,
              schema: [
                {
                  name: "gap",
                  selector: {
                    number: { min: 0, max: 16, step: 1, mode: "box" },
                  },
                },
              ],
            },
          ];
    this._schema = schema;
    this._schemaLanguage = language;
    this._schemaEntities = entityKey;
    return html`<ha-form
      .hass=${this.hass}
      .data=${this._config}
      .schema=${schema}
      .computeLabel=${this._computeLabel}
      @value-changed=${this._valueChanged}
    ></ha-form>`;
  }
}
PixelItCardEditor.styles = css`
  :host {
    display: block;
  }
  ha-form {
    display: block;
  }
`;
customElements.define(EDITOR_TAG, PixelItCardEditor);

// ===== Main Card =====
class PixelItLiveviewCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _controlBusy: { state: true },
    _controlError: { state: true },
  };
  setConfig(config) {
    this._clearGestures();
    this._controlError = "";
    this._config = normalizeConfig(config);
  }
  disconnectedCallback() {
    this._clearGestures();
    super.disconnectedCallback();
  }
  _clearGestures() {
    clearTimeout(this._holdTimer);
    clearTimeout(this._tapTimer);
    this._holdTimer = this._tapTimer = undefined;
    this._pointer = undefined;
    this._held = false;
  }
  _hasAction(kind) {
    return (
      this._config?.[kind + "_action"]?.action !== "none" &&
      !!this._config?.[kind + "_action"]
    );
  }
  _interactive() {
    return ["tap", "hold", "double_tap"].some((kind) => this._hasAction(kind));
  }
  _runAction(kind) {
    if (!this._hasAction(kind) || !this.hass) return;
    // HA executes the action, including confirmation, targets and custom events.
    this.dispatchEvent(
      new CustomEvent("hass-action", {
        detail: { config: this._config, action: kind },
        bubbles: true,
        composed: true,
      }),
    );
  }
  _pointerDown(event) {
    if (!this._interactive() || event.isPrimary === false || event.button !== 0)
      return;
    clearTimeout(this._holdTimer);
    this._held = false;
    this._pointer = { id: event.pointerId, x: event.clientX, y: event.clientY };
    if (this._hasAction("hold"))
      this._holdTimer = setTimeout(() => {
        clearTimeout(this._tapTimer);
        this._tapTimer = undefined;
        this._held = true;
        this._runAction("hold");
      }, 500);
  }
  _pointerMove(event) {
    if (
      this._pointer &&
      (Math.abs(event.clientX - this._pointer.x) > 10 ||
        Math.abs(event.clientY - this._pointer.y) > 10)
    )
      this._clearGestures();
  }
  _pointerUp(event) {
    if (!this._pointer || event.pointerId !== this._pointer.id) return;
    clearTimeout(this._holdTimer);
    this._pointer = undefined;
    if (this._held) {
      this._held = false;
      return;
    }
    if (!this._hasAction("double_tap")) {
      this._runAction("tap");
      return;
    }
    if (this._tapTimer) {
      clearTimeout(this._tapTimer);
      this._tapTimer = undefined;
      this._runAction("double_tap");
    } else
      this._tapTimer = setTimeout(() => {
        this._tapTimer = undefined;
        this._runAction("tap");
      }, 250);
  }
  _keyDown(event) {
    if (
      event.repeat ||
      !["Enter", " "].includes(event.key) ||
      !this._interactive()
    )
      return;
    event.preventDefault();
    this._clearGestures();
    this._runAction(event.shiftKey ? "hold" : "tap");
  }
  _controlState() {
    const state = this.hass?.states?.[this._config.light_entity];
    return state && ["on", "off"].includes(state.state) ? state : null;
  }
  async _control(service, data = {}) {
    if (this._controlBusy || !this._controlState()) return;
    const entity = this._config.light_entity;
    this._controlBusy = true;
    this._controlError = "";
    try {
      await this.hass.callService("light", service, {
        ...data,
        entity_id: entity,
      });
    } catch (error) {
      this._controlError =
        tr(this.hass, "control_failed") +
        ": " +
        (error?.message || String(error));
    } finally {
      this._controlBusy = false;
    }
  }
  _togglePower() {
    return this._control(
      this._controlState()?.state === "on" ? "turn_off" : "turn_on",
    );
  }
  _brightnessChanged(event) {
    const brightness = Number(event.target.value);
    if (
      this._config.show_brightness &&
      Number.isInteger(brightness) &&
      brightness >= 1 &&
      brightness <= 255
    )
      return this._control("turn_on", { brightness });
  }
  _renderControls() {
    const cfg = this._config;
    if (!cfg.show_power && !cfg.show_brightness) return nothing;
    const state = this._controlState();
    const brightness = state?.attributes?.brightness;
    const modes = state?.attributes?.supported_color_modes || [];
    const supportsBrightness = modes.some((mode) =>
      [
        "brightness",
        "color_temp",
        "hs",
        "xy",
        "rgb",
        "rgbw",
        "rgbww",
        "white",
      ].includes(mode),
    );
    return html`<div class="plc-controls">
      ${
        cfg.show_power
          ? html`<button
              type="button"
              aria-label=${tr(this.hass, "power")}
              aria-pressed=${state?.state === "on" ? "true" : "false"}
              ?disabled=${!state || this._controlBusy}
              @click=${this._togglePower}
            >
              <ha-icon icon="mdi:power"></ha-icon>
            </button>`
          : nothing
      }
      ${
        cfg.show_brightness
          ? html`<label class="plc-brightness"
              >${tr(this.hass, "brightness")}
              <input
                type="range"
                min="1"
                max="255"
                step="1"
                .value=${String(Number.isInteger(brightness) ? Math.max(1, brightness) : 1)}
                aria-label=${tr(this.hass, "brightness")}
                ?disabled=${!state || !supportsBrightness || this._controlBusy}
                @change=${this._brightnessChanged}
              />
            </label>`
          : nothing
      }
      ${!state ? html`<span class="plc-control-error" role="status">${tr(this.hass, "control_unavailable")}</span>` : nothing}
      ${this._controlError ? html`<span class="plc-control-error" role="alert">${this._controlError}</span>` : nothing}
    </div>`;
  }
  _contextMenu(event) {
    if (this._hasAction("hold")) event.preventDefault();
  }
  getCardSize() {
    const measured = this.getBoundingClientRect().height;
    if (measured > 0) return Math.max(1, Math.ceil(measured / 50));
    const data = this._getData();
    const ratio =
      (data?.height || this._config?.height || 8) /
      (data?.width || this._config?.width || 32);
    return Math.max(
      1,
      Math.ceil(
        (32 +
          (this._config?.show_power || this._config?.show_brightness ? 56 : 0) +
          (this._config?.show_header || this._config?.show_status ? 32 : 0) +
          (this._config?.show_pixels ? 336 * ratio : 0)) /
          50,
      ),
    );
  }
  getGridOptions() {
    return { columns: 12, rows: "auto", min_columns: 3, min_rows: 1 };
  }
  static async getConfigElement() {
    if (!customElements.get("ha-form")) {
      const helpers = await window.loadCardHelpers();
      const builtIn = helpers.createCardElement({
        type: "tile",
        entity: "sun.sun",
      });
      await builtIn.constructor.getConfigElement();
    }
    return document.createElement(EDITOR_TAG);
  }
  static getStubConfig(hass) {
    const sensors = liveviewEntities(hass);
    const entity = sensors.length === 1 ? sensors[0] : "";
    return { ...CARD_DEFAULTS, entity };
  }

  shouldUpdate(changedProperties) {
    if (changedProperties.has("_config") || !changedProperties.has("hass"))
      return true;
    const previousHass = changedProperties.get("hass");
    if (!previousHass || !this.hass) return true;
    const entity = this._config?.entity;
    return (
      previousHass.states?.[entity] !== this.hass.states?.[entity] ||
      previousHass.states?.[this._config.light_entity] !==
        this.hass.states?.[this._config.light_entity] ||
      getLang(previousHass) !== getLang(this.hass)
    );
  }

  _getData() {
    const entity = this._config.entity;
    if (!entity || !this.hass || !this.hass.states) return null;
    const state = this.hass.states[entity];
    if (!state) return null;
    const attrs = state.attributes || {};
    const connected = state.state === "connected";
    const hex = attrs.hex || "";
    const width = attrs.width || this._config.width || 32;
    const height = attrs.height || this._config.height || 8;
    const pixels = attrs.pixels || this._parseHex(hex, width, height);
    return {
      connected: connected,
      hex: hex,
      width: width,
      height: height,
      pixels: pixels,
    };
  }
  _parseHex(hex, width, height) {
    const pixels = [];
    const expected = width * height * 6;
    const s = hex.length >= expected ? hex.substring(0, expected) : hex;
    for (let i = 0; i < s.length; i += 6) {
      const chunk = s.substring(i, i + 6);
      if (chunk.length < 6) break;
      const r = parseInt(chunk.substring(0, 2), 16);
      const g = parseInt(chunk.substring(2, 4), 16);
      const b = parseInt(chunk.substring(4, 6), 16);
      pixels.push({ r: r, g: g, b: b });
    }
    return pixels;
  }

  render() {
    if (!this._config) return html``;
    const self = this;
    const T = function (key) {
      return tr(self.hass, key);
    };
    const cfg = this._config;
    const data = this._getData();
    const width = data ? data.width : cfg.width || 32;
    const height = data ? data.height : cfg.height || 8;
    const gap = cfg.gap ?? 1;
    const connected = data ? data.connected : false;
    const statusText = connected ? T("connected") : T("disconnected");
    const statusClass = connected ? "ok" : "err";
    const title = cfg.title || "PixelIt";
    const hasPixels = data && data.pixels && data.pixels.length > 0;
    // Scale excessive gaps down on narrow cards, preserving square pixels.
    const gridStyle =
      "grid-template-columns:repeat(" +
      width +
      ", minmax(0, 1fr));gap:min(" +
      gap +
      "px, " +
      50 / width +
      "cqw);";
    let message;
    if (!cfg.entity) message = T("no_entity");
    else if (!data) message = T("missing_entity");
    else if (!connected && !cfg.show_status) message = T("disconnected");
    else if (connected && !hasPixels) message = T("no_data");
    const cells = [];
    if (cfg.show_pixels && data?.pixels) {
      for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
          const idx = y * width + x;
          const p = data.pixels[idx];
          // Lit pixels get their real color; unlit pixels get a fully OPAQUE
          // dark fill. Semi-transparent (rgba 0.55) still lets the theme's
          // backdrop-filter blur bleed through, making unlit cells alternate
          // between black and purple depending on background position.
          // Opaque black breaks the theme bleed completely while the card
          // border/glass effect remains via the transparent .plc-inner.
          const bg = p ? "rgb(" + p.r + "," + p.g + "," + p.b + ")" : "#000";
          cells.push(html`<div class="px" style="background:${bg};"></div>`);
        }
      }
    }
    return html`<ha-card class=${cfg.transparent ? "plc transparent" : "plc"}
      ><div
        class="plc-content"
        tabindex=${this._interactive() ? "0" : "-1"}
        role=${this._interactive() ? "button" : nothing}
        aria-label=${title}
        @pointerdown=${this._pointerDown}
        @pointermove=${this._pointerMove}
        @pointerup=${this._pointerUp}
        @pointercancel=${this._clearGestures}
        @pointerleave=${this._clearGestures}
        @keydown=${this._keyDown}
        @contextmenu=${this._contextMenu}
      >
        <div class="plc-inner">
          ${cfg.show_header || (cfg.show_status && data) ? html`<div class="plc-header">${cfg.show_header ? html`<span class="plc-title">${title}</span>` : nothing}${cfg.show_status && data ? html`<span class="plc-status ${statusClass}" role="status">${statusText}</span>` : nothing}</div>` : nothing}${cfg.show_pixels && hasPixels ? html`<div class="plc-grid" role="img" aria-label=${title} style="${gridStyle}">${cells}</div>` : nothing}${message ? html`<div class="plc-empty" role="status">${message}</div>` : nothing}
        </div>
      </div>
      ${this._renderControls()}</ha-card
    >`;
  }
}
PixelItLiveviewCard.styles = css`
  :host {
    display: block;
    min-width: 0;
  }
  ha-card {
    overflow: hidden;
  }
  .plc-content[role="button"] {
    cursor: pointer;
  }
  .plc-content:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  ha-card.transparent {
    background: transparent;
    box-shadow: none;
    border: none;
  }
  .plc-controls {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    padding: 0 16px 16px;
  }
  .plc-controls button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: 50%;
    border: 1px solid var(--divider-color);
    background: var(--secondary-background-color);
    color: var(--primary-text-color);
    cursor: pointer;
  }
  .plc-controls button[aria-pressed="true"] {
    color: var(--primary-color);
  }
  .plc-controls button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .plc-brightness {
    display: flex;
    align-items: center;
    flex: 1;
    flex-wrap: wrap;
    gap: 8px;
    font-size: 12px;
    color: var(--secondary-text-color);
  }
  .plc-brightness input {
    min-width: 80px;
    flex: 1;
    accent-color: var(--primary-color);
  }
  .plc-control-error {
    flex-basis: 100%;
    font-size: 12px;
    color: var(--error-color);
    overflow-wrap: anywhere;
  }
  .plc-inner {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    container-type: inline-size;
    min-width: 0;
  }
  .plc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    min-width: 0;
  }
  .plc-title {
    font-size: var(--ha-font-size-l, 16px);
    font-weight: 500;
    color: var(--primary-text-color);
    overflow-wrap: anywhere;
    min-width: 0;
  }
  .plc-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--primary-text-color);
    font-size: 12px;
    line-height: 20px;
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: 500;
    margin-inline-start: auto;
    white-space: nowrap;
  }
  .plc-status.ok {
    background: rgba(76, 175, 80, 0.2);
  }
  .plc-status.err {
    background: rgba(244, 67, 54, 0.2);
  }
  .plc-status::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--success-color, #4caf50);
  }
  .plc-status.err::before {
    background: var(--error-color, #f44336);
  }
  .plc-grid {
    display: grid;
    width: 100%;
    align-self: stretch;
    min-width: 0;
    background: #000;
    border-radius: 4px;
    overflow: hidden;
  }
  .px {
    aspect-ratio: 1/1;
    border-radius: 1px;
  }
  .plc-empty {
    font-size: 12px;
    color: var(--secondary-text-color);
    padding: 8px 0;
  }
`;
customElements.define(CARD_NAME, PixelItLiveviewCard);

// Keep existing dashboard card types working after the integration rename.
if (!customElements.get("pixelit-liveview-card")) {
  customElements.define(
    "pixelit-liveview-card",
    class extends PixelItLiveviewCard {},
  );
}
window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_NAME,
  name: "PixelIt",
  description:
    "Zeigt den aktuellen Inhalt eines PixelIt-Displays (über HA-Sensor)",
  preview: true,
  documentationURL:
    "https://github.com/pixelit-project/ha-pixelit#card-options",
  configurable: true,
  show_form_editors: true,
  getEntitySuggestion(hass, entityId) {
    if (!isLiveviewSensor(hass, entityId)) {
      return null;
    }
    return { config: { type: CARD_TYPE, entity: entityId } };
  },
});
export { PixelItLiveviewCard };
