import type {
  ExpressionSpecification,
  LayerSpecification,
  SourceSpecification,
} from "maplibre-gl";
import type { Overlay, RiskLayer } from "./urlState";

export const CROATIA_BOUNDS: [number, number, number, number] = [
  13.489719898096567, 42.37766308699427, 19.447355845530073, 46.55502572105002,
];
export const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
export const CELL_MIN_ZOOM = 6;

/** ColorBrewer YlOrRd with monotonic lightness, readable in colour-blind simulation. */
export const CLASS_COLORS = [
  "#ffffb2",
  "#fecc5c",
  "#fd8d3c",
  "#f03b20",
  "#bd0026",
];
export const CLASS_TEXT = [
  "#000000",
  "#000000",
  "#000000",
  "#000000",
  "#ffffff",
];
/** ColorBrewer PuBu: population is exposure, it must not read as a risk level. */
const POPULATION_COLORS = [
  "#f1eef6",
  "#d0d1e6",
  "#a6bddb",
  "#74a9cf",
  "#2b8cbe",
  "#045a8d",
];
export const EAQI_COLORS = [
  "#50f0e6",
  "#50ccaa",
  "#f0e641",
  "#ff5050",
  "#960032",
  "#7d2181",
];
export const EAQI_TEXT = [
  "#000000",
  "#000000",
  "#000000",
  "#000000",
  "#ffffff",
  "#ffffff",
];

export const HV_WMS = "https://servisi.voda.hr/wms";
export const HV_VIEWER = "https://korp.voda.hr";
const HV_LAYERS = [
  "poplave_opasnosti_2019:hr.fd.opasnost-od-poplave-mala-vjerojatnost_2019",
  "poplave_opasnosti_2019:hr.fd.opasnost-od-poplave-srednja-vjerojatnost_2019",
  "poplave_opasnosti_2019:hr.fd.opasnost-od-poplave-velika-vjerojatnost_2019",
].join(",");

interface LegendStep {
  color: string;
  label: string;
}

interface RiskSpec {
  property: string;
  breaks: number[];
  colors: string[];
  legend: LegendStep[];
}

function steps(colors: string[], labels: string[]): LegendStep[] {
  return colors.map((color, index) => ({ color, label: labels[index] }));
}

const HAZARD_LABELS = [
  "0 – 0,2",
  "0,2 – 0,4",
  "0,4 – 0,6",
  "0,6 – 0,8",
  "0,8 – 1",
];
const HAZARD_BREAKS = [0.2, 0.4, 0.6, 0.8];

export const RISK_SPECS: Record<RiskLayer, RiskSpec> = {
  ikr: {
    property: "ikr_class",
    breaks: [2, 3, 4, 5],
    colors: CLASS_COLORS,
    legend: steps(CLASS_COLORS, [
      "1 Vrlo nizak",
      "2 Nizak",
      "3 Umjeren",
      "4 Visok",
      "5 Vrlo visok",
    ]),
  },
  flood: {
    property: "h_flood",
    breaks: [0.03, 0.25, 0.55],
    colors: CLASS_COLORS.slice(1),
    legend: steps(CLASS_COLORS.slice(1), [
      "do 0,03",
      "0,03 – 0,25",
      "0,25 – 0,55",
      "više od 0,55",
    ]),
  },
  heat: {
    property: "h_heat",
    breaks: HAZARD_BREAKS,
    colors: CLASS_COLORS,
    legend: steps(CLASS_COLORS, HAZARD_LABELS),
  },
  fire: {
    property: "h_fire",
    breaks: HAZARD_BREAKS,
    colors: CLASS_COLORS,
    legend: steps(CLASS_COLORS, HAZARD_LABELS),
  },
  air: {
    property: "pm25_annual",
    breaks: [5, 10, 15, 25],
    colors: CLASS_COLORS,
    legend: steps(CLASS_COLORS, [
      "do 5",
      "5 – 10",
      "10 – 15",
      "15 – 25",
      "više od 25",
    ]),
  },
  pop65: {
    property: "share_ge65",
    breaks: [0.1, 0.2, 0.3, 0.4],
    colors: POPULATION_COLORS.slice(1),
    legend: steps(POPULATION_COLORS.slice(1), [
      "do 10 %",
      "10 – 20 %",
      "20 – 30 %",
      "30 – 40 %",
      "više od 40 %",
    ]),
  },
  population: {
    property: "pop_total",
    breaks: [10, 50, 250, 1000, 5000],
    colors: POPULATION_COLORS,
    legend: steps(POPULATION_COLORS, [
      "1 – 9",
      "10 – 49",
      "50 – 249",
      "250 – 999",
      "1.000 – 4.999",
      "5.000 i više",
    ]),
  },
};

export function riskColor(layer: RiskLayer): ExpressionSpecification {
  const spec = RISK_SPECS[layer];
  return [
    "step",
    ["to-number", ["get", spec.property]],
    spec.colors[0],
    ...spec.breaks.flatMap((value, index) => [value, spec.colors[index + 1]]),
  ] as ExpressionSpecification;
}

/** Cells without the value, or with no hazard at all, stay transparent. */
export function riskFilter(layer: RiskLayer): ExpressionSpecification {
  const spec = RISK_SPECS[layer];
  const positive = layer === "flood" || layer === "population";
  return [
    "all",
    ["has", spec.property],
    [positive ? ">" : ">=", ["to-number", ["get", spec.property]], 0],
  ] as ExpressionSpecification;
}

const tiles = (name: string): string =>
  `${window.location.origin}/tiles/${name}/{z}/{x}/{y}`;

export function dataSources(): Record<string, SourceSpecification> {
  return {
    jls_risk: {
      type: "vector",
      tiles: [tiles("jls_risk")],
      bounds: CROATIA_BOUNDS,
      maxzoom: 14,
    },
    grid_risk: {
      type: "vector",
      tiles: [tiles("grid_risk")],
      bounds: CROATIA_BOUNDS,
      minzoom: CELL_MIN_ZOOM,
      maxzoom: 12,
    },
    nature: {
      type: "vector",
      tiles: [tiles("nature")],
      bounds: CROATIA_BOUNDS,
      maxzoom: 13,
    },
    hv: {
      type: "raster",
      tiles: [
        `${HV_WMS}?service=WMS&version=1.3.0&request=GetMap&layers=${HV_LAYERS}&styles=` +
          "&crs=EPSG:3857&bbox={bbox-epsg-3857}&width=256&height=256&format=image/png&transparent=true",
      ],
      tileSize: 256,
      bounds: CROATIA_BOUNDS,
      attribution: "Hrvatske vode – Karte opasnosti od poplava 2019.",
    },
    stations: {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    },
  };
}

type GroupedLayer = LayerSpecification & { overlay?: Overlay };

export const MAP_LAYERS: readonly GroupedLayer[] = [
  {
    id: "risk-jls-fill",
    type: "fill",
    source: "jls_risk",
    "source-layer": "jls_risk",
    maxzoom: CELL_MIN_ZOOM,
    filter: ["has", "ikr_class"],
    paint: {
      "fill-color": [
        "step",
        ["to-number", ["get", "ikr_class"]],
        CLASS_COLORS[0],
        2,
        CLASS_COLORS[1],
        3,
        CLASS_COLORS[2],
        4,
        CLASS_COLORS[3],
        5,
        CLASS_COLORS[4],
      ],
      "fill-opacity": 0.7,
    },
  },
  {
    id: "risk-fill",
    type: "fill",
    source: "grid_risk",
    "source-layer": "grid_risk",
    minzoom: CELL_MIN_ZOOM,
    paint: {
      "fill-color": riskColor("ikr"),
      // Streets stay readable when zoomed in to a single cell.
      "fill-opacity": ["interpolate", ["linear"], ["zoom"], 9, 0.75, 14, 0.35],
    },
    filter: riskFilter("ikr"),
  },
  {
    id: "hv-raster",
    overlay: "hv",
    type: "raster",
    source: "hv",
    paint: { "raster-opacity": 0.75 },
  },
  {
    id: "nature-fill",
    overlay: "nature",
    type: "fill",
    source: "nature",
    "source-layer": "nature",
    paint: { "fill-color": "#15803d", "fill-opacity": 0.2 },
  },
  {
    id: "nature-line",
    overlay: "nature",
    type: "line",
    source: "nature",
    "source-layer": "nature",
    paint: { "line-color": "#15803d", "line-width": 1 },
  },
  {
    id: "jls-line",
    overlay: "jls",
    type: "line",
    source: "jls_risk",
    "source-layer": "jls_risk",
    paint: {
      "line-color": "#334155",
      "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.4, 12, 1.5],
    },
  },
  {
    id: "stations-circle",
    overlay: "stations",
    type: "circle",
    source: "stations",
    paint: {
      "circle-radius": 7,
      "circle-color": ["coalesce", ["get", "color"], "#94a3b8"],
      "circle-stroke-color": "#0f172a",
      "circle-stroke-width": 1.5,
    },
  },
];
