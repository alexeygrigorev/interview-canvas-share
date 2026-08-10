import { randomBytes } from "node:crypto";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

/**
 * Interviewer → candidate realtime round-trip against the docker-compose stack.
 *
 * Two isolated browser contexts stand in for two people at two machines:
 * session 1 is the interviewer (a seeded account), session 2 is a guest who
 * only ever holds the join link.
 */

/** Seeded demo interviewer — see the seed data in `backend/app/store.py`. */
const INTERVIEWER = { email: "avery@northwind.dev", password: "demo-password" };

/** Where the SPA keeps its bearer token (`frontend/src/lib/api/api.ts`). */
const ACCESS_TOKEN_KEY = "sdip.access-token";

const unique = () => randomBytes(4).toString("hex");

/**
 * Logs a browser context in as the interviewer by exchanging the credentials
 * for a token over the API and seeding it where the SPA looks for it, so the
 * context is authenticated from its very first render.
 */
async function logInAsInterviewer(context: BrowserContext, baseURL: string) {
  const response = await context.request.post(`${baseURL}/v1/auth/login`, {
    data: INTERVIEWER,
  });
  expect(response.ok(), `login failed: ${response.status()} ${await response.text()}`).toBe(true);

  const { access_token: accessToken } = (await response.json()) as { access_token: string };
  await context.addInitScript(
    ([key, token]) => window.sessionStorage.setItem(key, token),
    [ACCESS_TOKEN_KEY, accessToken] as const,
  );
}

/** A node label as drawn on the canvas — the palette lives outside the SVG. */
const canvasLabel = (page: Page, text: string) =>
  page.locator("svg foreignObject").getByText(text, { exact: true });

test("a candidate's canvas edit reaches the interviewer in realtime", async ({
  browser,
  baseURL,
}) => {
  const runId = unique();
  const title = `E2E interview ${runId}`;
  // Unique so the assertion cannot pass on seeded or leftover canvas content.
  const marker = `Candidate node ${runId}`;

  const interviewerContext = await browser.newContext();
  const candidateContext = await browser.newContext();

  try {
    const interviewer = await interviewerContext.newPage();
    const candidate = await candidateContext.newPage();

    await test.step("1. log in as the interviewer", async () => {
      await logInAsInterviewer(interviewerContext, baseURL!);
      await interviewer.goto("/");
      await expect(interviewer.getByRole("heading", { name: "Interviews" })).toBeVisible();
      await expect(interviewer.getByText(INTERVIEWER.email)).toBeVisible();
    });

    await test.step("2. create an interview session", async () => {
      await interviewer.getByRole("button", { name: "New interview" }).click();
      await interviewer.getByLabel("Title").fill(title);
      await interviewer
        .getByLabel("Problem statement")
        .fill("Design a URL shortener that serves 10k requests per second.");
      await interviewer.getByRole("button", { name: "Create and open canvas" }).click();

      await expect(interviewer).toHaveURL(/\/room\/[^/]+$/);
      await expect(interviewer.getByRole("heading", { name: title })).toBeVisible();
      // The room only renders the canvas once the owner participant exists.
      await expect(interviewer.getByRole("button", { name: "Share" })).toBeVisible();
    });

    const joinToken = await test.step("3. share the join link", async () => {
      await interviewer.getByRole("button", { name: "Share" }).click();

      const toast = interviewer
        .locator("[data-sonner-toast]")
        .filter({ hasText: "Candidate link copied" });
      await expect(toast).toBeVisible();

      // The toast carries the link; the clipboard itself is not readable
      // without extra browser permissions.
      const text = await toast.innerText();
      const token = text.match(/\/join\/([A-Za-z0-9_-]+)/)?.[1];
      expect(token, `no join token in the share toast: ${text}`).toBeTruthy();
      return token!;
    });

    await test.step("4. join as the candidate from a second client", async () => {
      await candidate.goto(`/join/${joinToken}`);
      await expect(candidate.getByRole("heading", { name: title })).toBeVisible();

      await candidate.getByLabel("Display name").fill(`Casey ${runId}`);
      await candidate.getByRole("button", { name: "Join interview" }).click();

      await expect(candidate).toHaveURL(/\/room\/[^/]+$/);
      // Guests never authenticate, so the owner-only controls stay hidden.
      await expect(candidate.getByRole("button", { name: "Share" })).toBeHidden();
    });

    await test.step("5. change the canvas as the candidate", async () => {
      await candidate.getByRole("button", { name: "Cache", exact: true }).click();

      // Placing a component selects it, so the properties panel renames it.
      const labelField = candidate.locator("#el-label");
      await expect(labelField).toBeVisible();
      await labelField.fill(marker);

      await expect(canvasLabel(candidate, marker)).toBeVisible();
    });

    await test.step("6. verify the interviewer sees the change", async () => {
      await expect(canvasLabel(interviewer, marker)).toBeVisible();

      // The edit is also persisted, not just broadcast: it survives a reload.
      await interviewer.reload();
      await expect(canvasLabel(interviewer, marker)).toBeVisible();
    });
  } finally {
    await candidateContext.close();
    await interviewerContext.close();
  }
});
