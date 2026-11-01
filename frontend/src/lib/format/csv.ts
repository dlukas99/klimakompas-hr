/** Builds CSV text and saves it through the browser; nothing leaves the page. */
export function toCsv(
  header: string[],
  rows: (string | number | null | undefined)[][],
): string {
  const cell = (value: string | number | null | undefined) => {
    const text = value == null ? "" : String(value);
    return /[";\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [header, ...rows].map((row) => row.map(cell).join(";")).join("\r\n");
}

export function downloadCsv(filename: string, text: string): void {
  // The byte order mark lets spreadsheet programs read the diacritics correctly.
  const url = URL.createObjectURL(
    new Blob(["﻿", text], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
