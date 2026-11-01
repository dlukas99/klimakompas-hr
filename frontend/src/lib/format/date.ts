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
