import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { App } from "./App";
import { emptySummary, mockApi } from "./test/mockApi";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("Overview", () => {
  it("shows a loading state, then KPIs from the API", async () => {
    mockApi();
    renderAt("/");
    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
    const tile = (await screen.findByText("Active listings")).parentElement!;
    expect(within(tile).getByText("40")).toBeInTheDocument();
    expect(screen.getByText("Fresh")).toBeInTheDocument();
    expect(screen.getByText("2/2")).toBeInTheDocument();
  });

  it("shows an honest empty state when the database has no listings", async () => {
    mockApi({ "/api/v1/summary": () => emptySummary });
    renderAt("/");
    expect(await screen.findByText("No listings collected yet")).toBeInTheDocument();
    expect(screen.queryByText("Active listings")).not.toBeInTheDocument();
  });

  it("shows an error with retry instead of figures when the API fails", async () => {
    let calls = 0;
    const fetchMock = mockApi({
      "/api/v1/summary": () => {
        calls += 1;
        return calls === 1 ? new Response("{}", { status: 503 }) : emptySummary;
      },
    });
    renderAt("/");
    const alert = await screen.findAllByRole("alert");
    expect(alert[0]).toHaveTextContent("temporarily unavailable");
    await userEvent.click(within(alert[0]).getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No listings collected yet")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/summary"))).toBe(true);
  });

  it("only issues GET requests", async () => {
    const fetchMock = mockApi();
    renderAt("/");
    await screen.findByText("Active listings");
    for (const [, init] of fetchMock.mock.calls) expect((init as RequestInit | undefined)?.method ?? "GET").toBe("GET");
  });

  it("passes an automated accessibility scan", async () => {
    mockApi();
    const { container } = renderAt("/");
    await screen.findByText("Active listings");
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});

describe("Navigation", () => {
  it("links to every section and keeps period filters", async () => {
    mockApi();
    renderAt("/?range=7&role=Data%20Analyst");
    const nav = screen.getAllByRole("navigation", { name: "Main" })[0];
    for (const name of ["Overview", "Job Listings", "Skill Intelligence", "Salary Insights", "Locations & Roles", "Data Sources", "Methodology"]) {
      expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
    }
    expect(within(nav).getByRole("link", { name: "Skill Intelligence" }).getAttribute("href")).toContain("range=7");
    await userEvent.click(within(nav).getByRole("link", { name: "Data Sources" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Data sources" })).toBeInTheDocument();
    expect(await screen.findByText("Job listings courtesy of Jobicy")).toBeInTheDocument();
  });

  it("renders a not-found page", () => {
    mockApi();
    renderAt("/nope");
    expect(screen.getByText("Page not found")).toBeInTheDocument();
  });
});

describe("Job listings", () => {
  it("paginates, filters via the API and links to the source", async () => {
    const fetchMock = mockApi();
    renderAt("/jobs");
    expect(await screen.findByText(/listings · page 1 of 3/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /View original listing/ })[0]).toHaveAttribute("href", "https://jobicy.com/jobs/1");
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));
    expect(await screen.findByText("Page 2 / 3")).toBeInTheDocument();
    await userEvent.selectOptions(await screen.findByLabelText("Role"), "Data Engineer");
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes("role=Data+Engineer") && String(u).includes("page=1"))).toBe(true),
    );
    expect(screen.getByRole("link", { name: "Export CSV" }).getAttribute("href")).toContain("/api/v1/exports/jobs.csv?role=Data+Engineer");
  });

  it("labels unknown salary as not stated, never zero", async () => {
    mockApi();
    renderAt("/jobs");
    await screen.findByText(/listings · page 1 of 3/);
    expect(screen.getAllByText("Not stated").length).toBeGreaterThan(0);
    expect(screen.queryByText("$0")).not.toBeInTheDocument();
  });

  it("shows an empty state when nothing matches", async () => {
    mockApi({ "/api/v1/jobs": () => ({ items: [], total: 0, page: 1, page_size: 20, pages: 0 }) });
    renderAt("/jobs?q=zzz");
    expect(await screen.findByText("No listings match these filters")).toBeInTheDocument();
  });
});

describe("Skill intelligence", () => {
  it("shows counts, shares and explicit zeros for the analyst toolkit", async () => {
    mockApi();
    renderAt("/skills");
    const toolkit = (await screen.findByRole("heading", { name: "Analyst toolkit" })).closest("section")!;
    expect(within(toolkit).getByText("47.6%")).toBeInTheDocument();
    expect(within(toolkit).getAllByText(/Not found in this population/).length).toBeGreaterThanOrEqual(3);
    const table = screen.getByRole("table", { name: "Skill counts and shares" });
    expect(within(table).getByText("SQL")).toBeInTheDocument();
    expect(within(table).getAllByText("No prior data").length).toBe(3);
  });
});
