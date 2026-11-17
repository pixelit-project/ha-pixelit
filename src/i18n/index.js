// Copyright (c) 2026 Pissbirne and PixelIt project contributors. MIT license.
import de from "./de.js";
import en from "./en.js";

const I18N = { de, en };
export function getLang(hass) {
  const lang = (hass.locale?.language || hass.language || "en").split("-")[0];
  return I18N[lang] ? lang : "en";
}
export function tr(hass, key) {
  if (!hass) return I18N.en[key] || key;
  const lang = getLang(hass);
  return (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;
}
