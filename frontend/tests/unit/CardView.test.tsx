import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CardView } from "../../src/features/card/CardView";
import hr from "../../src/i18n/hr.json";
import type { CardResponse } from "../../src/lib/api/client";

const HAZARD = {
  level: 4,
  label: "Visok",
  h: 0.5,
  r: 0.4,
  key_value: {},
  explanation: [{ factor: "hazard" as const, value: 0.5 }],
  source_ids: ["ecde"],
};

function card(overrides: Partial<CardResponse> = {}): CardResponse {
  return {
    location: {
      lat: 45.5,
      lon: 18.7,
      label: "Trg Ante Starčevića 1",
      naselje: { code: "1", name: "Osijek" },
      jls: { code: "03123", name: "Osijek", kind: "grad" },
      zupanija: { code: "14", name: "Osječko-baranjska županija" },
      cell_id: "CRS3035RES1000mN2500000E4800000",
    },
    ikr: {
      value: 0.2,
      level: 5,
      label: "Vrlo visok",
      percentile: 85.1,
      index_version: "1.0.0",
      populated: true,
    },
    hazards: {
      flood: {
        ...HAZARD,
        key_value: {
          zone_return_period: 100,
          near_rp100: true,
          depth_rp100_m: 1.25,
        },
      },
      heat: {
        ...HAZARD,
        key_value: {
          hot_days: 32.7,
          tropical_nights: 13,
          lst_delta_c: 3.2,
          tree_share: 0.1,
        },
      },
      fire: {
        ...HAZARD,
        key_value: { fwi_days: 9.9, fuel_share: 0.35, burnt_years_2km: 2 },
      },
      air: {
        ...HAZARD,
        key_value: { pm25_annual: 15.8, year: 2023, who_guideline: 5 },
      },
    },
    population: {
      total_rounded: 8060,
      below_threshold: false,
      share_65plus: 0.217,
      share_under15: 0.137,
      age_share_source: "cell",
      suppressed: false,
    },
    live: {
      warnings: [],
      warnings_checked_at: new Date().toISOString(),
      air_now: null,
      air_forecast: [],
      fire_index: null,
      heatwave: null,
      nature_nearby: [],
    },
    advice: {},
    generated_at: new Date().toISOString(),
    partial: false,
    degraded_sources: [],
    areas: {
      naselje: {
        code: "1",
        name: "Čaglin",
        pop: 478,
        pop65: 120,
        ikr_level: 3,
        ikr_label: "Srednji",
      },
      jls: {
        code: "00582",
        name: "Čaglin",
        pop: 2111,
        pop65: 510,
        ikr_level: 4,
        ikr_label: "Visok",
        rank_hr: 120,
        total_hr: 556,
      },
    },
    scope: "point",
    live_status: [
      { source: "dhmz_cap", state: "ok", checked_at: new Date().toISOString() },
      {
        source: "azo_aq_rest",
        state: "ok",
        checked_at: new Date().toISOString(),
      },
    ],
    ...overrides,
  };
}

function show(data: CardResponse) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <CardView card={data} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json([])));
});

describe("CardView", () => {
  it("shows risk as number, word and percentile", () => {
    show(card());
    expect(screen.getAllByText("Vrlo visok").length).toBeGreaterThan(0);
    expect(screen.getByText(/Veći je od 85 %/)).toBeInTheDocument();
    expect(screen.getByText(hr.card.ikrRelative)).toBeInTheDocument();
  });

  it("explains the flood zone and shows hr-HR numbers", () => {
    show(card());
    const flood = within(screen.getByTestId("hazard-flood"));
    expect(flood.getByText(/zoni poplave 1:100/)).toBeInTheDocument();
    expect(flood.getByText(/1,3 m|1,2 m/)).toBeInTheDocument();
    expect(flood.getByText(hr.card.flood.limit)).toBeInTheDocument();
  });

  it("says when there are no warnings and when they were checked", () => {
    show(card());
    expect(screen.getByText(/Trenutno nema upozorenja/)).toBeInTheDocument();
  });

  it("does not claim no warnings when they could not be checked", () => {
    show(card({ live: { ...card().live, warnings_checked_at: null } }));
    expect(screen.getByText(hr.card.warningsUnknown)).toBeInTheDocument();
    expect(
      screen.queryByText(/Trenutno nema upozorenja/),
    ).not.toBeInTheDocument();
  });

  it("labels PM10 shown in place of PM2.5", () => {
    const value = {
      value: 19,
      unit: "µg/m3",
      observed_at: new Date().toISOString(),
      stale: false,
      eaqi_class: 2,
      eaqi_label: "Prihvatljiva",
    };
    show(
      card({
        live: {
          ...card().live,
          air_now: {
            station: { id: "160", name: "Osijek-1", distance_km: 1.2 },
            pollutant: "pm10",
            substitution: "local_pm10",
            value,
            values: { pm10: value },
            observed_at: value.observed_at,
          },
        },
      }),
    );
    expect(
      screen.getByText(/PM10 je druga onečišćujuća tvar/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Osijek-1/)).toBeInTheDocument();
  });

  it("explains an unpopulated cell instead of showing an index", () => {
    show(
      card({
        ikr: {
          value: null,
          level: null,
          label: null,
          percentile: null,
          index_version: null,
          populated: false,
        },
        population: { ...card().population, total_rounded: 0 },
      }),
    );
    expect(screen.getByText(hr.card.ikrUnpopulated)).toBeInTheDocument();
    expect(screen.getByText(hr.card.populationCellNone)).toBeInTheDocument();
  });

  it("always shows settlement and municipality population, even for an empty cell", () => {
    show(
      card({
        scope: "jls",
        population: { ...card().population, total_rounded: 0 },
      }),
    );
    const population = within(screen.getByTestId("card-population"));
    expect(
      population.getByText(/Naselje Čaglin: 478 stanovnika/),
    ).toBeInTheDocument();
    expect(
      population.getByText(/Grad Čaglin: 2\.111 stanovnika/),
    ).toBeInTheDocument();
    const areas = within(screen.getByTestId("card-areas"));
    expect(areas.getByText(/120\. od 556/)).toBeInTheDocument();
  });

  it("names which live source is missing and that the risk is unaffected", () => {
    show(
      card({
        live_status: [
          {
            source: "dhmz_cap",
            state: "stale",
            checked_at: new Date(Date.now() - 18 * 3600 * 1000).toISOString(),
          },
          { source: "azo_aq_rest", state: "none_nearby", checked_at: null },
        ],
      }),
    );
    const notice = within(screen.getByTestId("live-notice"));
    expect(
      notice.getByText(/Upozorenja DHMZ-a zadnji su put/),
    ).toBeInTheDocument();
    expect(notice.getByText(hr.card.liveNote)).toBeInTheDocument();
    expect(notice.queryByText(/kvalitete zraka/)).not.toBeInTheDocument();
  });

  it("shows no live notice when everything is fresh", () => {
    show(card());
    expect(screen.queryByTestId("live-notice")).not.toBeInTheDocument();
  });

  it("never prints the exact count of a very small cell", () => {
    show(
      card({
        population: {
          ...card().population,
          total_rounded: null,
          below_threshold: true,
        },
      }),
    );
    expect(screen.getByText(hr.card.populationCellSmall)).toBeInTheDocument();
  });

  it("always carries the disclaimer", () => {
    show(card());
    expect(screen.getByText(hr.app.disclaimer)).toBeInTheDocument();
  });
});
