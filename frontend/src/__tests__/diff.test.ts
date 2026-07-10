import { describe, it, expect } from "vitest";
import { diffWords } from "../utils/diff";

describe("diffWords", () => {
  it("handles empty or null strings gracefully", () => {
    expect(diffWords("", "")).toEqual([]);
    expect(diffWords(null, undefined)).toEqual([]);
    expect(diffWords("hello", "")).toEqual([{ value: "hello", removed: true }]);
    expect(diffWords("", "world")).toEqual([{ value: "world", added: true }]);
  });

  it("identifies matching words without flagging differences", () => {
    const diff = diffWords("hello world", "hello world");
    expect(diff).toEqual([
      { value: "hello" },
      { value: " " },
      { value: "world" }
    ]);
  });

  it("correctly identifies additions and removals", () => {
    const diff = diffWords("hello world", "hello brave new world");
    expect(diff).toEqual([
      { value: "hello" },
      { value: " ", added: true },
      { value: "brave", added: true },
      { value: " ", added: true },
      { value: "new", added: true },
      { value: " " },
      { value: "world" }
    ]);
  });
});
