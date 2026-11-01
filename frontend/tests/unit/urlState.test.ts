import { describe, expect, it } from "vitest";
import { searchResultParams } from "../../src/features/map/mapLink";
import { parseMapUrl, serializeMapUrl } from "../../src/features/map/urlState";
import type { GeocodeResult } from "../../src/lib/api/client";

const AREA: GeocodeResult = {
  kind: "municipality",
  code: "03123",
  label: "Osijek",
  detail: null,
  lat: 45.5,
  lon: 18.7,
  bbox: [18.5, 45.4, 18.9, 45.6],
  population: 96313,
};

describe("map URL state", () => {
  it("shows all layers by default", () => {
    expect(parseMapUrl(new URLSearchParams()).layers).toEqual([
      "jls",
      "stanovnistvo",
    ]);
  });

  it("reads a chosen layer list and ignores unknown names", () => {
    const state = parseMapUrl(new URLSearchParams("slojevi=jls,nepoznato"));
    expect(state.layers).toEqual(["jls"]);
  });

  it("keeps an empty layer list empty", () => {
    expect(parseMapUrl(new URLSearchParams("slojevi=")).layers).toEqual([]);
  });

  it("round-trips the view", () => {
    const state = parseMapUrl(
      new URLSearchParams("pogled=45.50000,18.70000,9.00"),
    );
    expect(state.view).toEqual({ lat: 45.5, lon: 18.7, zoom: 9 });
    expect(serializeMapUrl(state).get("pogled")).toBe("45.50000,18.70000,9.00");
  });

  it("ignores malformed coordinates", () => {
    expect(
      parseMapUrl(new URLSearchParams("pogled=a,b,c&okvir=1,2")).view,
    ).toBeNull();
    expect(parseMapUrl(new URLSearchParams("okvir=1,2")).bbox).toBeNull();
  });
});

describe("search result link", () => {
  it("fits an area to its bounding box without a pin", () => {
    const state = parseMapUrl(searchResultParams(AREA, new URLSearchParams()));
    expect(state.bbox).toEqual([18.5, 45.4, 18.9, 45.6]);
    expect(state.pin).toBeNull();
  });

  it("pins an address and keeps the chosen layers", () => {
    const address = { ...AREA, kind: "address" as const, bbox: null };
    const state = parseMapUrl(
      searchResultParams(address, new URLSearchParams("slojevi=jls")),
    );
    expect(state.pin).toEqual({ lat: 45.5, lon: 18.7 });
    expect(state.layers).toEqual(["jls"]);
  });
});
