import type { Node as RFNode, Edge as RFEdge } from '@xyflow/react';
import type { AgentConfig, AgentEdge, AgentNode } from './types';

const NODE_W = 240;
const NODE_H = 100;
const H_GAP = 120;
const V_GAP = 48;

export function agentToFlow(config: AgentConfig): { nodes: RFNode[]; edges: RFEdge[] } {
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

  const rowCount: Record<number, number> = {};
  const rowIndex: Record<string, number> = {};
  for (const node of config.nodes) {
    const c = col[node.name] ?? 0;
    rowIndex[node.name] = rowCount[c] ?? 0;
    rowCount[c] = (rowCount[c] ?? 0) + 1;
  }

  const nodes: RFNode[] = config.nodes.map((n: AgentNode) => ({
    id: n.name,
    type: 'agentNode',
    position: {
      x: (col[n.name] ?? 0) * (NODE_W + H_GAP),
      y: (rowIndex[n.name] ?? 0) * (NODE_H + V_GAP),
    },
    data: { node: n, isInitial: n.name === config.initial_node },
  }));

  const edges: RFEdge[] = config.nodes.flatMap((n: AgentNode) =>
    (n.edges ?? []).map(e => ({
      id: `${n.name}→${e.function}`,
      source: n.name,
      target: e.target,
      label: e.function,
      type: 'smoothstep',
      labelStyle: { fontSize: 11, fill: '#718096' },
      labelBgStyle: { fill: '#f8f9fa' },
      data: e as unknown as Record<string, unknown>, // cast required by RF Edge type constraint
    }))
  );

  return { nodes, edges };
}

/** Reconstruct an AgentConfig from the current React Flow graph state. */
export function flowToAgent(base: AgentConfig, rfNodes: RFNode[], rfEdges: RFEdge[]): AgentConfig {
  const edgesBySource: Record<string, AgentEdge[]> = {};
  for (const e of rfEdges) {
    if (!edgesBySource[e.source]) edgesBySource[e.source] = [];
    edgesBySource[e.source].push({ ...(e.data as unknown as AgentEdge), target: e.target });
  }

  const nodes: AgentNode[] = rfNodes.map(n => ({
    ...(n.data.node as AgentNode),
    edges: edgesBySource[n.id] ?? [],
  }));

  return { ...base, nodes };
}
