import { describe, it, expect } from "vitest";
import { buildSpanTree, Span } from "../utils/spanTree";

describe("buildSpanTree", () => {
  it("returns empty array when input is null, undefined, or empty", () => {
    expect(buildSpanTree(null)).toEqual([]);
    expect(buildSpanTree(undefined)).toEqual([]);
    expect(buildSpanTree([])).toEqual([]);
  });

  it("handles a flat list with one root and two children correctly", () => {
    const spans: Span[] = [
      {
        span_id: "root-1",
        type: "agent_step",
        name: "agent_root",
        started_at: "2026-07-10T12:00:00Z",
        ended_at: "2026-07-10T12:00:05Z",
      },
      {
        span_id: "child-1",
        parent_span_id: "root-1",
        type: "llm_call",
        name: "llm_1",
        started_at: "2026-07-10T12:00:01Z",
        ended_at: "2026-07-10T12:00:02Z",
      },
      {
        span_id: "child-2",
        parent_span_id: "root-1",
        type: "tool_call",
        name: "tool_1",
        started_at: "2026-07-10T12:00:03Z",
        ended_at: "2026-07-10T12:00:04Z",
      },
    ];

    const tree = buildSpanTree(spans);
    expect(tree).toHaveLength(1);
    expect(tree[0].span_id).toBe("root-1");
    expect(tree[0].depth).toBe(0);
    expect(tree[0].children).toHaveLength(2);
    expect(tree[0].children[0].span_id).toBe("child-1");
    expect(tree[0].children[0].depth).toBe(1);
    expect(tree[0].children[1].span_id).toBe("child-2");
    expect(tree[0].children[1].depth).toBe(1);
  });

  it("treats spans with missing or null parent_span_id as root nodes", () => {
    const spans: Span[] = [
      {
        span_id: "root-1",
        type: "agent_step",
        name: "root_one",
        started_at: "2026-07-10T12:00:00Z",
        ended_at: "2026-07-10T12:00:01Z",
      },
      {
        span_id: "root-2",
        parent_span_id: null,
        type: "agent_step",
        name: "root_two",
        started_at: "2026-07-10T12:00:02Z",
        ended_at: "2026-07-10T12:00:03Z",
      },
    ];

    const tree = buildSpanTree(spans);
    expect(tree).toHaveLength(2);
    expect(tree[0].span_id).toBe("root-1");
    expect(tree[1].span_id).toBe("root-2");
  });

  it("handles deeply nested spans (3+ levels) correctly", () => {
    const spans: Span[] = [
      {
        span_id: "root",
        type: "agent_step",
        name: "root",
        started_at: "2026-07-10T12:00:00Z",
        ended_at: "2026-07-10T12:00:10Z",
      },
      {
        span_id: "level-1",
        parent_span_id: "root",
        type: "agent_step",
        name: "level-1",
        started_at: "2026-07-10T12:00:01Z",
        ended_at: "2026-07-10T12:00:05Z",
      },
      {
        span_id: "level-2",
        parent_span_id: "level-1",
        type: "llm_call",
        name: "level-2",
        started_at: "2026-07-10T12:00:02Z",
        ended_at: "2026-07-10T12:00:04Z",
      },
    ];

    const tree = buildSpanTree(spans);
    expect(tree).toHaveLength(1);
    expect(tree[0].children).toHaveLength(1);
    expect(tree[0].children[0].span_id).toBe("level-1");
    expect(tree[0].children[0].depth).toBe(1);
    expect(tree[0].children[0].children).toHaveLength(1);
    expect(tree[0].children[0].children[0].span_id).toBe("level-2");
    expect(tree[0].children[0].children[0].depth).toBe(2);
  });

  it("places a span with nonexistent parent_span_id at the root level", () => {
    const spans: Span[] = [
      {
        span_id: "orphan",
        parent_span_id: "nonexistent-parent",
        type: "llm_call",
        name: "orphan_span",
        started_at: "2026-07-10T12:00:00Z",
        ended_at: "2026-07-10T12:00:01Z",
      },
    ];

    const tree = buildSpanTree(spans);
    expect(tree).toHaveLength(1);
    expect(tree[0].span_id).toBe("orphan");
    expect(tree[0].parent_span_id).toBe("nonexistent-parent");
    expect(tree[0].depth).toBe(0);
  });
});
