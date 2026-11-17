import assert from "node:assert/strict";
import { test } from "node:test";
import de from "../../src/i18n/de.js";
import en from "../../src/i18n/en.js";
import { getLang, tr } from "../../src/i18n/index.js";

test("German and English translations have matching keys and nonempty text", () => {
  assert.deepEqual(Object.keys(de).sort(), Object.keys(en).sort());
  for (const dictionary of [de, en]) {
    for (const value of Object.values(dictionary)) {
      assert.equal(typeof value, "string");
      assert.ok(value.trim().length);
    }
  }
});

test("regional locales use their language and unsupported locales fall back to English", () => {
  const german = { locale: { language: "de-DE" }, language: "en" };
  assert.equal(getLang(german), "de");
  assert.equal(tr(german, "connected"), "Verbunden");
  assert.equal(tr({ language: "en-GB" }, "connected"), "Connected");
  assert.equal(tr({ language: "fr" }, "connected"), "Connected");
  assert.equal(tr(undefined, "connected"), "Connected");
  assert.equal(tr(german, "unknown_key"), "unknown_key");
});
