export interface Span {
  span_id: string;
  parent_span_id?: string | null;
  type: "llm_call" | "tool_call" | "retrieval" | "agent_step";
  name: string;
  started_at: string;
  ended_at: string;
  input?: any;
  output?: any;
  error?: string | null;
}

export interface SpanTreeNode extends Span {
  children: SpanTreeNode[];
  depth: number;
}

/**
 * Builds a hierarchical span tree from a flat list of spans.
 */
export function buildSpanTree(spans: Span[] | null | undefined): SpanTreeNode[] {
  if (!spans || spans.length === 0) return [];

  // Create tree nodes for all spans
  const nodeMap = new Map<string, SpanTreeNode>();
  for (const span of spans) {
    nodeMap.set(span.span_id, {
      ...span,
      children: [],
      depth: 0,
    });
  }

  const roots: SpanTreeNode[] = [];

  // Establish parent/child relationships
  for (const node of nodeMap.values()) {
    const parentId = node.parent_span_id;
    if (!parentId) {
      roots.push(node);
    } else {
      const parentNode = nodeMap.get(parentId);
      if (parentNode) {
        parentNode.children.push(node);
      } else {
        // Nonexistent parent references are treated as root nodes
        roots.push(node);
      }
    }
  }

  // Calculate depths recursively and sort children chronologically
  const assignDepthAndSort = (node: SpanTreeNode, currentDepth: number) => {
    node.depth = currentDepth;
    node.children.sort((a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime());
    for (const child of node.children) {
      assignDepthAndSort(child, currentDepth + 1);
    }
  };

  // Sort roots chronologically
  roots.sort((a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime());

  for (const root of roots) {
    assignDepthAndSort(root, 0);
  }

  return roots;
}

/**
 * Helper function to flatten the tree back to a list in pre-order traversal
 * for linear rendering with indentation.
 */
export function flattenSpanTree(nodes: SpanTreeNode[]): SpanTreeNode[] {
  const result: SpanTreeNode[] = [];
  const traverse = (node: SpanTreeNode) => {
    result.push(node);
    for (const child of node.children) {
      traverse(child);
    }
  };
  for (const node of nodes) {
    traverse(node);
  }
  return result;
}
