// @vitest-environment jsdom

import { fireEvent, render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("dataset-free application shell", () => {
  it("describes local guided measurement without an inference service", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /one clear sizing result per nail/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/8 photos → 1 clear result per nail/i),
    ).toBeVisible();
    expect(screen.getByText(/never uploaded/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("requires confirmation of the current Third Series 50-cent coin", () => {
    render(
      <MemoryRouter initialEntries={["/prepare"]}>
        <App />
      </MemoryRouter>,
    );

    const ready = screen.getByRole("button", { name: /I’m ready/i });
    expect(ready).toBeDisabled();
    expect(screen.getAllByText(/Port of Singapore/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Older Singapore 50-cent coins/i)).toBeVisible();

    const confirmation = screen.getByRole("checkbox", {
      name: /I have the Third Series/i,
    });
    fireEvent.click(confirmation);
    expect(confirmation).toBeChecked();
    expect(ready).toBeEnabled();
  });

  it("states the no-network privacy boundary", () => {
    render(
      <MemoryRouter initialEntries={["/privacy"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /never leave this browser/i,
      }),
    ).toBeVisible();
    expect(screen.getByText(/does not send selected photos/i)).toBeVisible();
    expect(screen.getByText(/does not train or run/i)).toBeVisible();
  });

  it("does not expose an automatic sizing route", async () => {
    const view = render(
      <MemoryRouter initialEntries={["/instant"]}>
        <App />
      </MemoryRouter>,
    );
    const route = within(view.container);

    expect(
      await route.findByRole("heading", {
        level: 1,
        name: /one clear sizing result per nail/i,
      }),
    ).toBeVisible();
    expect(route.queryByText(/automatic sizing/i)).not.toBeInTheDocument();
  });
});
