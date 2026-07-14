// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("private sizing application shell", () => {
  it("leads with the one-photo automatic sizing promise", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /upload one nail photo.*one best-fit suggestion/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/never uploaded/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /size one nail from a photo/i }),
    ).toHaveAttribute("href", "/instant");
    expect(screen.getByText(/one photo, then a quick review/i)).toBeVisible();
    expect(screen.getByText(/1 best-fit suggestion/i)).toBeVisible();
    expect(screen.queryByText(/about one minute/i)).not.toBeInTheDocument();
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
    expect(screen.getByText(/runs it in your browser/i)).toBeVisible();
    expect(screen.getByText(/not used for training/i)).toBeVisible();
  });
});
