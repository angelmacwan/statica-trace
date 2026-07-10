/**
 * Button.test.tsx — Vitest smoke test (backlog item 0.2.1)
 *
 * Acceptance criteria:
 * - A trivial smoke test exists and passes (renders a <Button> component
 *   and asserts it's in the DOM).
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Button } from "../components/Button";

describe("Button", () => {
  it("renders children in the DOM", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: /click me/i })).toBeInTheDocument();
  });

  it("forwards disabled prop to the underlying button element", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button", { name: /disabled/i })).toBeDisabled();
  });
});
