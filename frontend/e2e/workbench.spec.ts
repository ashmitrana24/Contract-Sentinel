import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.describe("ClauseGuard Workbench E2E & Visual Verification", () => {
  test.beforeEach(async ({ page }) => {
    page.on("console", (msg) => console.log("BROWSER LOG:", msg.type(), msg.text()));
    page.on("pageerror", (err) => console.log("BROWSER ERROR:", err.message));
    page.on("request", (req) => console.log("REQ:", req.method(), req.url()));
    page.on("response", (res) => console.log("RES:", res.status(), res.url()));
    // Set viewport or default
    await page.goto("/");
  });

  test("Home screen accessibility and visual presentation", async ({ page }) => {
    // Verify wordmark and theme toggle
    await expect(page.getByText("ClauseGuard", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("heading", {
        name: "Review contracts for tampering, contradictions and key terms",
      })
    ).toBeVisible();

    // Verify sample cards are displayed
    await expect(page.getByText("Clean Contract")).toBeVisible();
    await expect(page.getByText("Amount & Date Discrepancy")).toBeVisible();
    await expect(page.getByText("Edited PDF Contract")).toBeVisible();

    // Run Axe accessibility check (0 serious violations)
    const axeResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .disableRules(["color-contrast"]) // evaluate separately
      .analyze();

    const seriousViolations = axeResults.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(seriousViolations).toEqual([]);
  });

  test("End-to-end sample workflows: clean, discrepancy, and edited contracts", async ({
    page,
  }) => {
    // 1. Upload Clean Sample
    await page.getByText("Clean Contract").click();

    // Wait for redirection to document report
    await page.waitForURL(/\/documents\/.+/);

    // Wait for processing to complete and summary card to appear
    await expect(page.getByTestId("risk-badge")).toBeVisible({ timeout: 25000 });
    await expect(page.getByTestId("risk-badge")).toContainText("LOW");

    // Return to home
    await page.goto("/");

    // 2. Upload Amount & Date Discrepancy Sample
    await page.getByText("Amount & Date Discrepancy").click();
    await page.waitForURL(/\/documents\/.+/);

    // Wait for analysis completion
    await expect(page.getByTestId("risk-badge")).toBeVisible({ timeout: 25000 });

    // Assert band is at least Medium or High
    const badgeText = await page.getByTestId("risk-badge").textContent();
    expect(badgeText?.includes("MEDIUM") || badgeText?.includes("HIGH")).toBe(true);

    // Assert title "Amount in words doesn't match the figure" exists
    await expect(
      page.getByText("Amount in words doesn't match the figure").first()
    ).toBeVisible();

    // 3. Highlight selection and bounding box verification
    const analysisTabBtn = page.getByRole("button", { name: "Analysis & Tabs" });
    if (await analysisTabBtn.isVisible()) {
      await analysisTabBtn.click();
    }

    const findingCard = page.locator('[data-testid="finding-card"]').first();
    await findingCard.click();

    // Assert highlight exists in the PDF viewer
    const highlight = page.locator('[data-testid="finding-highlight"]').first();
    await expect(highlight).toBeVisible({ timeout: 10000 });

    const highlightBox = await highlight.boundingBox();
    expect(highlightBox).not.toBeNull();
    if (highlightBox) {
      expect(highlightBox.width).toBeGreaterThan(0);
      expect(highlightBox.height).toBeGreaterThan(0);
    }

    // 4. Toggle feedback, reload, and verify persistence
    if (await analysisTabBtn.isVisible()) {
      await analysisTabBtn.click();
    }

    const confirmButton = page.getByRole("button", { name: "Confirm issue" }).first();
    const isAlreadyConfirmed = await page
      .getByText("Issue confirmed", { exact: false })
      .first()
      .isVisible()
      .catch(() => false);
    if (isAlreadyConfirmed) {
      await Promise.all([
        page.waitForResponse((res) => res.url().includes("/feedback") && res.status() === 204),
        confirmButton.click(),
      ]);
      await page.waitForTimeout(300);
    }

    await Promise.all([
      page.waitForResponse((res) => res.url().includes("/feedback") && res.status() === 200),
      confirmButton.click(),
    ]);

    // Verify status indicator or toast
    await expect(page.getByText("Confirmed", { exact: false }).first()).toBeVisible();

    // Reload page and assert confirmed verdict persists
    await page.reload();
    await page.waitForLoadState("networkidle");
    const reloadAnalysisBtn = page.getByRole("button", { name: "Analysis & Tabs" });
    if (await reloadAnalysisBtn.isVisible()) {
      await reloadAnalysisBtn.click();
    }
    await expect(page.getByText("Issue confirmed", { exact: false }).first()).toBeVisible({
      timeout: 15000,
    });

    // Return to home
    await page.goto("/");

    // 5. Upload Edited PDF Sample
    await page.getByText("Edited PDF Contract").click();
    await page.waitForURL(/\/documents\/.+/);
    await expect(page.getByTestId("risk-badge")).toBeVisible({ timeout: 25000 });

    // Assert High band and revision / edit finding
    await expect(page.getByTestId("risk-badge")).toContainText("HIGH");
    await expect(
      page.getByText("Post-creation revision or alteration").first()
    ).toBeVisible();

    // 6. Delete document workflow
    await page.getByRole("button", { name: /Delete/i }).first().click();
    await expect(page.getByText("Delete document")).toBeVisible();
    await Promise.all([
      page.waitForResponse((res) => res.request().method() === "DELETE" && res.status() === 204),
      page.getByTestId("confirm-delete-btn").click(),
    ]);

    // Assert returned to home
    await expect(page).toHaveURL("/");
  });
});
