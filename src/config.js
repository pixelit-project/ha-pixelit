// Copyright (c) 2026 Pissbirne and PixelIt project contributors. MIT license.
export const CARD_NAME = "pixelit-card";
export const CARD_TYPE = "custom:" + CARD_NAME;
export const EDITOR_TAG = CARD_NAME + "-editor";
export const ACTION_DEFAULTS = {
  tap_action: "more-info",
  hold_action: "none",
  double_tap_action: "none",
};
export const CARD_DEFAULTS = {
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
export function normalizeConfig(config) {
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
