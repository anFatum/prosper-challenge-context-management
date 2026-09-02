import type { Node, Edge } from '@xyflow/react';
import type { AgentConfig, AgentNode } from './types';

const NODE_W = 240;
const NODE_H = 100;
const H_GAP = 120;
const V_GAP = 48;

export function agentToFlow(config: AgentConfig): { nodes: Node[]; edges: Edge[] } {
  // BFS to assign columns
  const col: Record<string, number> = {};
  const queue: string[] = [config.initial_node];
  col[config.initial_node] = 0;

  while (queue.length) {
    const name = queue.shift()!;
    const node = config.nodes.find((n: AgentNode) => n.name === name);
    if (!node) continue;
    for (const edge of node.edges ?? []) {
      if (!(edge.target in col)) {
        col[edge.target] = col[name] + 1;
        queue.push(edge.target);
      }
    }
  }

  // Row index per column for vertical stacking
  const rowCount: Record<number, number> = {};
  const rowIndex: Record<string, number> = {};
  for (const node of config.nodes) {
    const c = col[node.name] ?? 0;
    rowIndex[node.name] = rowCount[c] ?? 0;
    rowCount[c] = (rowCount[c] ?? 0) + 1;
  }

  const nodes: Node[] = config.nodes.map((n: AgentNode) => ({
    id: n.name,
    type: 'agentNode',
    position: {
      x: (col[n.name] ?? 0) * (NODE_W + H_GAP),
      y: (rowIndex[n.name] ?? 0) * (NODE_H + V_GAP),
    },
    data: {
      node: n,
      isInitial: n.name === config.initial_node,
    },
  }));

  const edges: Edge[] = config.nodes.flatMap((n: AgentNode) =>
    (n.edges ?? []).map(e => ({
      id: `${n.name}→${e.function}`,
      source: n.name,
      target: e.target,
      label: e.function,
      type: 'smoothstep',
      labelStyle: { fontSize: 11, fill: '#718096' },
      labelBgStyle: { fill: '#f8f9fa' },
    }))
  );

  return { nodes, edges };
}
