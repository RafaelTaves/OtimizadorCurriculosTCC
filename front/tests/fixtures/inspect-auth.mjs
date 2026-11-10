// Supplies a synthetic test-session cookie to Taste Skill's isolated browser.
// The app still validates the session against tests/fixtures/api.mjs.
// No changes to the vendored skill or to application authorization.
import { Browser } from "../../../.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs";
const launch = Browser.launch;
Browser.launch = async function (...args) {
  const browser = await launch.apply(this, args);
  await browser.send("Storage.setCookies", {
    cookies: [
      {
        name: "curriculo_session",
        value:
          process.env.TASTE_TEST_ACCOUNT === "empty"
            ? "empty-test-token"
            : "synthetic-browser-test-token",
        domain: "localhost",
        path: "/",
        httpOnly: true,
        sameSite: "Lax",
      },
    ],
  });
  return browser;
};
await import("../../../.agents/skills/design-taste-frontend/scripts/inspect.mjs");
