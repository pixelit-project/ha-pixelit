// Copyright (c) 2026 Pissbirne and PixelIt project contributors. MIT license.
// Public entry point: register both elements and preserve the legacy card type.
import { CARD_NAME, CARD_TYPE, EDITOR_TAG } from "./config.js";
import { isLiveviewSensor } from "./entities.js";
import { PixelItCardEditor } from "./editor.js";
import { PixelItLiveviewCard } from "./card.js";

customElements.define(EDITOR_TAG, PixelItCardEditor);
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
