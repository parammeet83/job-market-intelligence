import { expect, test, type Page } from "@playwright/test";

const API = (process.env.E2E_API_URL ?? process.env.E2E_BASE_URL ?? "http://localhost:4173").replace(/\/$/, "");

function trackErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  return errors;
}

async function noHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test("overview shows live KPIs that match the API", async ({ page, request }) => {
  const errors = trackErrors(page);
  const summary = await (await request.get(`${API}/api/v1/summary`)).json();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Job market overview" })).toBeVisible();
  const active = page.getByText("Active listings", { exact: true }).locator("..");
  await expect(active).toContainText(new Intl.NumberFormat("en-US").format(summary.jobs_active));
  await expect(page.getByRole("heading", { name: "Listings observed over time" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Most frequently mentioned skills" })).toBeVisible();
  await noHorizontalOverflow(page);
  expect(errors).toEqual([]);
});

test("navigation reaches every section", async ({ page, isMobile }) => {
  await page.goto("/");
  const pages: [string, string][] = [
    ["Job Listings", "Job listings"],
    ["Skill Intelligence", "Skill intelligence"],
    ["Salary Insights", "Salary insights"],
    ["Locations & Roles", "Locations & roles"],
    ["Data Sources", "Data sources"],
    ["Methodology", "Methodology"],
  ];
  for (const [link, heading] of pages) {
    if (isMobile) await page.getByRole("button", { name: "Menu" }).click();
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: link }).click();
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await noHorizontalOverflow(page);
  }
});

test("job listings: search, filter and paginate", async ({ page }) => {
  await page.goto("/jobs");
  const count = page.getByText(/listings · page 1 of/);
  await expect(count).toBeVisible();
  const total = Number((await count.textContent())!.replace(/[^0-9 ]/g, " ").trim().split(/\s+/)[0]);
  expect(total).toBeGreaterThan(0);
  if (total > 20) {
    await page.getByRole("button", { name: "Next →" }).click();
    await expect(page.getByText(/page 2 of/).first()).toBeVisible();
  }
  await page.getByLabel("Role").selectOption({ index: 1 });
  await expect(page).toHaveURL(/role=/);
  await expect(page.getByText(/listings · page 1 of|No listings match/).first()).toBeVisible();
  await page.getByLabel("Search title or company").fill("zzzz-no-such-job");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("No listings match these filters")).toBeVisible();
  await noHorizontalOverflow(page);
});

test("skill intelligence renders ranking, toolkit and trend", async ({ page }) => {
  await page.goto("/skills");
  await expect(page.getByRole("heading", { name: "Analyst toolkit" })).toBeVisible();
  for (const name of ["SQL", "Python", "Excel", "Power BI", "Tableau"]) {
    await expect(page.locator("li", { hasText: name }).first()).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: "Skill share over time" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Skill counts and shares" })).toBeVisible();
  await page.getByLabel("Skill category").selectOption("Databases & SQL");
  await expect(page).toHaveURL(/category=/);
  await noHorizontalOverflow(page);
});

test("salary insights keep currencies and periods separate", async ({ page, request }) => {
  const data = await (await request.get(`${API}/api/v1/analytics/salaries`)).json();
  await page.goto("/salaries");
  await expect(page.getByRole("heading", { name: "Salary distribution by currency and pay period" })).toBeVisible();
  for (const g of data.groups.slice(0, 3)) {
    await expect(page.locator("figcaption", { hasText: g.currency }).first()).toBeVisible();
  }
  await noHorizontalOverflow(page);
});

test("data sources show attribution and health", async ({ page }) => {
  await page.goto("/sources");
  await expect(page.getByRole("heading", { name: "Jobicy" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Remote OK" })).toBeVisible();
  await expect(page.getByText(/courtesy of Jobicy/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Ingestion runs" })).toBeVisible();
});

test("CSV export downloads data from a permitted source only", async ({ request }) => {
  const res = await request.get(`${API}/api/v1/exports/jobs.csv`);
  expect(res.status()).toBe(200);
  expect(res.headers()["content-type"]).toContain("text/csv");
  const lines = (await res.text()).trim().split("\n");
  expect(lines[0]).toContain("source_name");
  expect(lines.slice(1).every((l) => !l.includes(",Remote OK,"))).toBe(true);
});

test("API: docs available, invalid input rejected, writes refused", async ({ request }) => {
  expect((await request.get(`${API}/api/docs`)).status()).toBe(200);
  expect((await request.get(`${API}/api/openapi.json`)).status()).toBe(200);
  expect((await request.get(`${API}/api/v1/jobs?page_size=1000`)).status()).toBe(422);
  expect((await request.get(`${API}/api/v1/jobs/0`)).status()).toBe(422);
  for (const method of ["post", "put", "delete", "patch"] as const) {
    expect((await request[method](`${API}/api/v1/jobs`)).status()).toBe(405);
  }
});

test("no credentials in the bundle or API responses", async ({ page, request }) => {
  const bodies: string[] = [];
  page.on("response", async (r) => {
    if (/\.(js|css|html)$|\/api\//.test(r.url())) bodies.push(await r.text().catch(() => ""));
  });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  bodies.push(await (await request.get(`${API}/api/v1/sources`)).text());
  const joined = bodies.join("\n");
  for (const pattern of [/postgres(ql)?(\+psycopg)?:\/\//i, /npg_[A-Za-z0-9]{8,}/, /neon\.tech/i, /password\s*[=:]\s*["'][^"']{6,}/i, /jmp_(ingest|api_ro)/, /DATABASE_URL/]) {
    expect(joined).not.toMatch(pattern);
  }
});
