import { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import AgentNode from './AgentNode';
import type { AgentConfig } from '../types';
import { agentToFlow } from '../agentToFlow';

const nodeTypes = { agentNode: AgentNode };

interface AgentGraphProps {
  config: AgentConfig;
}

export default function AgentGraph({ config }: AgentGraphProps) {
  const { nodes: initial, edges: initialEdges } = agentToFlow(config);
  const [nodes, , onNodesChange] = useNodesState(initial);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (connection: Connection) => setEdges(eds => addEdge(connection, eds)),
    [setEdges],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.2 }}
    >
      <Background gap={16} color="#e2e8f0" />
      <Controls />
      <MiniMap
        nodeColor={node => {
          const d = node.data as { isInitial?: boolean; node?: { end?: boolean } };
          if (d.isInitial) return '#bfdbfe';
          if (d.node?.end) return '#bbf7d0';
          return '#e2e8f0';
        }}
      />
    </ReactFlow>
  );
}