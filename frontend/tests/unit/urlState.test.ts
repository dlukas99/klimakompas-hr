import { describe, expect, it } from "vitest";
import { cardLink, searchResultParams } from "../../src/features/map/mapLink";
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
  it("shows the index and JLS boundaries by default", () => {
    const state = parseMapUrl(new URLSearchParams());
    expect(state.layer).toBe("ikr");
    expect(state.overlays).toEqual(["jls"]);
  });

  it("reads a layer and ignores unknown names", () => {
    expect(parseMapUrl(new URLSearchParams("sloj=flood")).layer).toBe("flood");
    expect(parseMapUrl(new URLSearchParams("sloj=nepoznato")).layer).toBe(
      "ikr",
    );
    const state = parseMapUrl(new URLSearchParams("slojevi=hv,nepoznato"));
    expect(state.overlays).toEqual(["hv"]);
  });

  it("keeps an empty overlay list empty", () => {
    const state = parseMapUrl(new URLSearchParams("slojevi="));
    expect(state.overlays).toEqual([]);
    expect(serializeMapUrl(state).get("slojevi")).toBe("");
  });

  it("round-trips the view", () => {
    const state = parseMapUrl(
      new URLSearchParams("pogled=45.50000,18.70000,9.00"),
    );
    expect(state.view).toEqual({ lat: 45.5, lon: 18.7, zoom: 9 });
    expect(serializeMapUrl(state).get("pogled")).toBe("45.50000,18.70000,9.00");
  });

  it("ignores malformed coordinates", () => {
    expect(parseMapUrl(new URLSearchParams("pogled=a,b,c")).view).toBeNull();
    expect(parseMapUrl(new URLSearchParams("okvir=1,2")).bbox).toBeNull();
  });
});

describe("links", () => {
  it("fits an area and opens its card", () => {
    const state = parseMapUrl(searchResultParams(AREA, new URLSearchParams()));
    expect(state.bbox).toEqual([18.5, 45.4, 18.9, 45.6]);
    expect(state.pin).toEqual({ lat: 45.5, lon: 18.7 });
    expect(state.label).toBe("Osijek");
  });

  it("keeps the chosen layer when searching", () => {
    const state = parseMapUrl(
      searchResultParams(AREA, new URLSearchParams("sloj=heat")),
    );
    expect(state.layer).toBe("heat");
  });

  it("builds a card link", () => {
    expect(cardLink(45.5, 18.7, "Osijek")).toBe(
      "/iskaznica?lat=45.5&lon=18.7&naziv=Osijek",
    );
  });
});
