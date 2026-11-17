// Copyright (c) 2026 Pissbirne and PixelIt project contributors. MIT license.
import { LitElement, html } from "lit";
import { ACTION_DEFAULTS, normalizeConfig } from "./config.js";
import { PIXELIT_ENTITY_SELECTOR, liveviewEntities } from "./entities.js";
import { getLang, tr } from "./i18n/index.js";
import { editorStyles } from "./styles.js";

// The editor uses native HA form controls while keeping language-aware labels.
export class PixelItCardEditor extends LitElement {
  static styles = editorStyles;
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
