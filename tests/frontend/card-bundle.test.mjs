import { registerCardTests } from "./card-runtime-helper.mjs";

registerCardTests(
  new URL(
    "../../custom_components/pixelit/www/pixelit-card.js",
    import.meta.url,
  ),
);
