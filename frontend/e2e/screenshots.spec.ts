import { test } from "@playwright/test";
import path from "path";

const screenshotsDir = path.resolve(__dirname, "../../docs/screenshots");

test.describe("Full-Page Visual Verification & Screenshots", () => {
  test("Capture all screens at 1440px and 375px in light and dark themes", async ({ page }) => {
    // 1. HOME SCREEN
    // Desktop Light (1440px)
    await page.setViewportSize({ width: 1440, height: 950 });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: path.join(screenshotsDir, "home-desktop-light.png"),
      fullPage: true,
    });

    // Desktop Dark (1440px)
    await page.getByLabel(/Switch to dark mode/i).click();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(screenshotsDir, "home-desktop-dark.png"),
      fullPage: true,
    });

    // Mobile Light (375px)
    await page.setViewportSize({ width: 375, height: 812 });
    await page.getByLabel(/Switch to light mode/i).click();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(screenshotsDir, "home-mobile-light.png"),
      fullPage: true,
    });

    // Mobile Dark (375px)
    await page.getByLabel(/Switch to dark mode/i).click();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(screenshotsDir, "home-mobile-dark.png"),
      fullPage: true,
    });

    // 2. REPORT SCREEN
    // Switch to desktop and upload sample to generate report view
    await page.setViewportSize({ width: 1440, height: 950 });
    await page.goto("/");
    await page.getByText("Amount & Date Discrepancy").click();
    await page.waitForURL(/\/documents\/.+/);

    // Wait for analysis report to settle
    await page.waitForSelector('[data-testid="risk-badge"]', { timeout: 30000 });
    await page.waitForTimeout(1000);

    // Report Desktop Dark (1440px)
    await page.screenshot({
      path: path.join(screenshotsDir, "report-desktop-dark.png"),
      fullPage: true,
    });

    // Report Desktop Light (1440px)
    await page.getByLabel(/Switch to light mode/i).click();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(screenshotsDir, "report-desktop-light.png"),
      fullPage: true,
    });

    // Report Mobile Light (375px)
    await page.setViewportSize({ width: 375, height: 812 });
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(screenshotsDir, "report-mobile-light.png"),
      fullPage: true,
    });

    // Report Mobile Dark (375px)
    await page.getByLabel(/Switch to dark mode/i).click();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(screenshotsDir, "report-mobile-dark.png"),
      fullPage: true,
    });
  });
});
