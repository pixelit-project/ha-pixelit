// Copyright (c) 2026 Pissbirne and PixelIt project contributors. MIT license.
export const PIXELIT_ENTITY_SELECTOR = {
  entity: { filter: [{ domain: "sensor", integration: "pixelit" }] },
};
export function isLiveviewSensor(hass, id) {
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
export function liveviewEntities(hass) {
  return Object.keys(hass?.entities ?? {}).filter((id) =>
    isLiveviewSensor(hass, id),
  );
}
