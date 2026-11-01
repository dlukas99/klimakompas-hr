import type {
  ExpressionSpecification,
  LayerSpecification,
  SourceSpecification,
} from "maplibre-gl";
import type { LayerId } from "./urlState";

export const CROATIA_BOUNDS: [number, number, number, number] = [
  13.489719898096567, 42.37766308699427, 19.447355845530073, 46.55502572105002,
];
export const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
export const CELL_MIN_ZOOM = 7;

/** Blue, not the risk palette: population is exposure, it must not read as a risk level. */
export const POPULATION_CLASSES = [
  { from: 1, color: "#f1eef6" },
  { from: 10, color: "#d0d1e6" },
  { from: 50, color: "#a6bddb" },
  { from: 250, color: "#74a9cf" },
  { from: 1000, color: "#2b8cbe" },
  { from: 5000, color: "#045a8d" },
] as const;

const populationColor: ExpressionSpecification = [
  "step",
  ["get", "pop_total"],
  POPULATION_CLASSES[0].color,
  ...POPULATION_CLASSES.slice(1).flatMap((item) => [item.from, item.color]),
] as ExpressionSpecification;

const tiles = (name: string): string =>
  `${window.location.origin}/tiles/${name}/{z}/{x}/{y}`;

export function dataSources(): Record<string, SourceSpecification> {
  return {
    jls: {
      type: "vector",
      tiles: [tiles("jls")],
      bounds: CROATIA_BOUNDS,
      maxzoom: 14,
    },
    grid_pop: {
      type: "vector",
      tiles: [tiles("grid_pop")],
      bounds: CROATIA_BOUNDS,
      minzoom: CELL_MIN_ZOOM,
      maxzoom: 12,
    },
  };
}

export const MAP_LAYERS: readonly (LayerSpecification & { group: LayerId })[] =
  [
    {
      id: "population-fill",
      group: "stanovnistvo",
      type: "fill",
      source: "grid_pop",
      "source-layer": "grid_pop",
      minzoom: CELL_MIN_ZOOM,
      paint: {
        "fill-color": populationColor,
        // Streets stay readable when zoomed in to a single cell.
        "fill-opacity": ["interpolate", ["linear"], ["zoom"], 9, 0.75, 14, 0.3],
      },
    },
    {
      id: "jls-hit",
      group: "jls",
      type: "fill",
      source: "jls",
      "source-layer": "jls",
      paint: { "fill-color": "#000000", "fill-opacity": 0 },
    },
    {
      id: "jls-line",
      group: "jls",
      type: "line",
      source: "jls",
      "source-layer": "jls",
      paint: {
        "line-color": "#334155",
        "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.4, 12, 1.5],
      },
    },
  ];

export const CLICKABLE_LAYERS = ["population-fill", "jls-hit"];
