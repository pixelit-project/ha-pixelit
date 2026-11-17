// Copyright (c) 2026 Pissbirne and PixelIt project contributors. MIT license.
import { LitElement, html, nothing } from "lit";
import { CARD_DEFAULTS, EDITOR_TAG, normalizeConfig } from "./config.js";
import { liveviewEntities } from "./entities.js";
import { getLang, tr } from "./i18n/index.js";
import { cardStyles } from "./styles.js";

export class PixelItLiveviewCard extends LitElement {
  static styles = cardStyles;
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
