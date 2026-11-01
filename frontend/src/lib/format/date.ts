const LOCALE = "hr-HR";
const TIME_ZONE = "Europe/Zagreb";

/** Formats an instant as "1. 11. 2026. u 14:20". */
export function formatDateTime(value: string): string {
  const parts = new Intl.DateTimeFormat(LOCALE, {
    day: "numeric",
    month: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: TIME_ZONE,
  }).formatToParts(new Date(value));
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? "";
  return `${Number(part("day"))}. ${Number(part("month"))}. ${part("year")}. u ${part("hour")}:${part("minute")}`;
}

const MINUTE = 60_000;
const relative = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });

/** Formats an instant as "prije 5 minuta", switching to the full date after a day. */
export function formatAgo(value: string, now: number = Date.now()): string {
  const minutes = Math.round((new Date(value).getTime() - now) / MINUTE);
  if (Math.abs(minutes) < 60) return relative.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return relative.format(hours, "hour");
  return formatDateTime(value);
}

/** Formats a calendar date as "1. 11. 2026." */
export function formatDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  return `${day}. ${month}. ${year}.`;
}
