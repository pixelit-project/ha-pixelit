import { registerCardTests } from "./card-runtime-helper.mjs";

registerCardTests(new URL("../../src/pixelit-card.js", import.meta.url));
