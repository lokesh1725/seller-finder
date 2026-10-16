// Run with: npm test
// Verifies the pure sharing helpers (WhatsApp URL generation, profile URLs).
import test from "node:test";
import assert from "node:assert/strict";

// jsdom is not used; provide the minimal globals the helpers touch.
globalThis.window = { location: { origin: "https://seller-finder.vercel.app" } };
globalThis.navigator = {};

const {
  whatsappShareUrl,
  businessUrl,
  websiteUrl,
  buildWebsiteMessage,
  buildBusinessMessage,
} = await import("../src/utils/share.js");

test("whatsappShareUrl encodes the message", () => {
  const url = whatsappShareUrl("Hi there & welcome");
  assert.equal(url, "https://wa.me/?text=Hi%20there%20%26%20welcome");
});

test("websiteUrl falls back to the current origin", () => {
  assert.equal(websiteUrl(), "https://seller-finder.vercel.app");
});

test("businessUrl builds a stable profile URL", () => {
  assert.equal(
    businessUrl("helmetshopee"),
    "https://seller-finder.vercel.app/business/helmetshopee"
  );
});

test("buildWebsiteMessage contains the site URL and is encodable", () => {
  const message = buildWebsiteMessage();
  assert.match(message, /https:\/\/seller-finder\.vercel\.app/);
  assert.ok(whatsappShareUrl(message).startsWith("https://wa.me/?text="));
});

test("buildBusinessMessage includes name, location and profile URL", () => {
  const message = buildBusinessMessage({
    company_name: "Bummer",
    city: "Ahmedabad",
    state: "Gujarat",
    slug: "bummer",
    official_website: "https://bummer.in",
  });
  assert.match(message, /Bummer/);
  assert.match(message, /Ahmedabad, Gujarat/);
  assert.match(message, /https:\/\/seller-finder\.vercel\.app\/business\/bummer/);
  assert.match(message, /https:\/\/bummer\.in/);
});

test("shared messages never contain secret-looking tokens", () => {
  const message = buildBusinessMessage({ company_name: "X", slug: "x" });
  assert.doesNotMatch(message, /api[_-]?key|token|secret|password/i);
});
