import hr from "../i18n/hr.json";
import { CLASS_COLORS, CLASS_TEXT } from "../features/map/layers";

/** Risk is always shown as colour, number and word (SPEC §9.4). */
export function LevelBadge({
  level,
  compact = false,
}: {
  level: number | null;
  compact?: boolean;
}) {
  if (!level) {
    return <span className="text-sm text-slate-700">{hr.card.noLevel}</span>;
  }
  const label = hr.levels[level - 1];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded font-semibold ${compact ? "px-1.5 py-0.5 text-xs" : "px-2 py-1 text-sm"}`}
      style={{
        backgroundColor: CLASS_COLORS[level - 1],
        color: CLASS_TEXT[level - 1],
      }}
    >
      <span>{level}</span>
      <span>{label}</span>
    </span>
  );
}
