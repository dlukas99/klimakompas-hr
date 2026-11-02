import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SearchBox } from "../../src/components/SearchBox";
import hr from "../../src/i18n/hr.json";

const RESULT = {
  kind: "municipality",
  code: "03514",
  label: "Požega",
  detail: "Grad, Požeško-slavonska županija",
  lat: 45.3,
  lon: 17.7,
  bbox: [17.6, 45.2, 17.8, 45.4],
  population: 22294,
};

function mockFetch(response: Response) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
}

function renderBox(onSelect = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SearchBox onSelect={onSelect} />
    </QueryClientProvider>,
  );
  return onSelect;
}

afterEach(() => vi.unstubAllGlobals());

describe("SearchBox", () => {
  it("lists results with kind and formatted population", async () => {
    mockFetch(Response.json({ results: [RESULT], addresses_searched: true }));
    renderBox();
    await userEvent.type(screen.getByRole("combobox"), "pozega");
    const option = await screen.findByRole("option");
    expect(option).toHaveTextContent("Požega");
    expect(option).toHaveTextContent("22.294 st.");
  });

  it("selects with the keyboard", async () => {
    mockFetch(Response.json({ results: [RESULT], addresses_searched: true }));
    const onSelect = renderBox();
    const input = screen.getByRole("combobox");
    await userEvent.type(input, "pozega");
    await screen.findByRole("option");
    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(onSelect).toHaveBeenCalledWith(RESULT);
    expect(input).toHaveAttribute("aria-expanded", "false");
  });

  it("asks only for the allowed kinds inside the chosen municipality", async () => {
    mockFetch(Response.json({ results: [], addresses_searched: true }));
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SearchBox
          onSelect={vi.fn()}
          options={{ kinds: ["address", "settlement"], jls: "00582" }}
        />
      </QueryClientProvider>,
    );
    await userEvent.type(screen.getByRole("combobox"), "ulica");
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const url = String(vi.mocked(fetch).mock.calls.at(-1)?.[0]);
    expect(url).toContain("kinds=address");
    expect(url).toContain("kinds=settlement");
    expect(url).toContain("jls=00582");
  });

  it("shows the empty state", async () => {
    mockFetch(Response.json({ results: [], addresses_searched: true }));
    renderBox();
    await userEvent.type(screen.getByRole("combobox"), "xqz");
    expect(await screen.findByText(hr.search.empty)).toBeInTheDocument();
  });

  it("shows the error state instead of failing", async () => {
    mockFetch(new Response(null, { status: 503 }));
    renderBox();
    await userEvent.type(screen.getByRole("combobox"), "osijek");
    expect(await screen.findByText(hr.search.error)).toBeInTheDocument();
  });

  it("does not call the API for a single character", async () => {
    mockFetch(Response.json({ results: [], addresses_searched: true }));
    renderBox();
    await userEvent.type(screen.getByRole("combobox"), "o");
    expect(await screen.findByText(hr.search.minLength)).toBeInTheDocument();
    await waitFor(() => expect(fetch).not.toHaveBeenCalled());
  });
});
