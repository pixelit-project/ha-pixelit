import assert from "node:assert/strict";
import { after, afterEach, before, test } from "node:test";
import { JSDOM } from "jsdom";

// Run the same contract against source imports and the shipped standalone bundle.
// Each entry point is a separate Node test process with its own custom-element registry.
export function registerCardTests(moduleURL) {
  let dom;
  let Card;
  const hass = () => ({
    language: "en",
    entities: { "sensor.live": { platform: "pixelit" } },
    states: {
      "sensor.live": {
        state: "connected",
        attributes: { width: 2, height: 1, hex: "FF000000FF00" },
      },
      "light.display": {
        state: "on",
        attributes: { brightness: 128, supported_color_modes: ["brightness"] },
      },
    },
  });

  before(async () => {
    dom = new JSDOM("<!doctype html><html><body></body></html>");
    // Lit must see the DOM before its first import. HA elements remain opaque
    // custom tags; this validates Lit bindings, not Home Assistant internals.
    for (const key of [
      "window",
      "document",
      "customElements",
      "HTMLElement",
      "Element",
      "Document",
      "DocumentFragment",
      "ShadowRoot",
      "CSSStyleSheet",
      "CustomEvent",
      "Event",
      "Node",
    ]) {
      globalThis[key] = dom.window[key];
    }
    ({ PixelItLiveviewCard: Card } = await import(moduleURL));
  });
  afterEach(() => document.body.replaceChildren());
  after(() => dom.window.close());

  async function mount(config = {}, state = hass()) {
    const card = document.createElement("pixelit-card");
    card.setConfig({ entity: "sensor.live", ...config });
    card.hass = state;
    document.body.append(card);
    await card.updateComplete;
    return card;
  }

  test("registers the exported card, legacy alias and editor", async () => {
    assert.equal(customElements.get("pixelit-card"), Card);
    assert.ok(document.createElement("pixelit-liveview-card") instanceof Card);
    customElements.define("ha-form", class extends HTMLElement {});
    assert.equal(
      (await Card.getConfigElement()).localName,
      "pixelit-card-editor",
    );
    assert.equal(
      window.customCards.filter(({ type }) => type === "pixelit-card").length,
      1,
    );
  });

  test("renders pixels and updates from device feedback through real Lit accessors", async () => {
    const card = await mount();
    assert.equal(card.shadowRoot.querySelectorAll(".px").length, 2);
    assert.equal(
      card.shadowRoot.querySelector(".px").style.background,
      "rgb(255, 0, 0)",
    );
    const next = hass();
    next.states["sensor.live"].attributes.hex = "0000FF000000";
    next.states["sensor.live"].state = "disconnected";
    card.hass = next;
    await card.updateComplete;
    assert.equal(
      card.shadowRoot.querySelector(".px").style.background,
      "rgb(0, 0, 255)",
    );
    assert.match(
      card.shadowRoot.querySelector(".plc-status").textContent,
      /Disconnected/,
    );
    card.setConfig({
      entity: "sensor.live",
      show_pixels: false,
      show_header: false,
    });
    await card.updateComplete;
    assert.equal(card.shadowRoot.querySelector(".plc-grid"), null);
    assert.equal(card.shadowRoot.querySelector(".plc-title"), null);
  });

  test("escapes user text and omits optional controls and attributes", async () => {
    const title = '<img src=x onerror="alert(1)">';
    const card = await mount({ title, tap_action: { action: "none" } });
    assert.equal(
      card.shadowRoot.querySelector(".plc-title").textContent,
      title,
    );
    assert.equal(card.shadowRoot.querySelector("img"), null);
    assert.equal(card.shadowRoot.querySelector(".plc-controls"), null);
    assert.equal(
      card.shadowRoot.querySelector(".plc-content").hasAttribute("role"),
      false,
    );
  });

  test("binds controls to HA services and renders pending and error state", async () => {
    let reject;
    const calls = [];
    const state = hass();
    state.callService = (...args) => {
      calls.push(args);
      return new Promise((_, rejectCall) => {
        reject = rejectCall;
      });
    };
    const card = await mount(
      {
        light_entity: "light.display",
        show_power: true,
        show_brightness: true,
      },
      state,
    );
    const button = card.shadowRoot.querySelector("button");
    assert.equal(button.disabled, false);
    assert.equal(card.shadowRoot.querySelector("input").value, "128");
    button.click();
    await card.updateComplete;
    assert.deepEqual(calls, [
      ["light", "turn_off", { entity_id: "light.display" }],
    ]);
    assert.equal(button.disabled, true);
    reject(new Error("Device unavailable"));
    // Let the async service rejection update the reactive error state.
    await new Promise((resolve) => setImmediate(resolve));
    await card.updateComplete;
    assert.equal(button.disabled, false);
    assert.match(
      card.shadowRoot.querySelector('[role="alert"]').textContent,
      /Device unavailable/,
    );
  });

  test("editor binds native form properties and emits composed configuration changes", async () => {
    const editor = document.createElement("pixelit-card-editor");
    editor.setConfig({ entity: "sensor.live", grid_options: { columns: 6 } });
    editor.hass = hass();
    document.body.append(editor);
    await editor.updateComplete;
    const form = editor.shadowRoot.querySelector("ha-form");
    assert.equal(form.hass, editor.hass);
    assert.equal(form.data.entity, "sensor.live");
    assert.ok(form.schema.some(({ name }) => name === "entity"));
    let event;
    document.body.addEventListener(
      "config-changed",
      (value) => {
        event = value;
      },
      { once: true },
    );
    form.dispatchEvent(
      new CustomEvent("value-changed", {
        detail: { value: { show_pixels: false } },
        bubbles: true,
      }),
    );
    await editor.updateComplete;
    assert.equal(event.detail.config.show_pixels, false);
    assert.equal(event.detail.config.grid_options.columns, 6);
    assert.equal(event.composed, true);
    assert.equal(form.data.show_pixels, false);
  });
}
