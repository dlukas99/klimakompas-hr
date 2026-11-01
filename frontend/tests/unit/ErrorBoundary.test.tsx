import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ErrorBoundary } from "../../src/components/ErrorBoundary";

function Broken(): never {
  throw new Error("no WebGL");
}

it("shows a message instead of blanking the page", () => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  render(
    <ErrorBoundary message="Karta nije dostupna.">
      <Broken />
    </ErrorBoundary>,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("Karta nije dostupna.");
});
