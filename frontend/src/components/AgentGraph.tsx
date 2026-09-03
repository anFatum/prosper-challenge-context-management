import { useCallback, useRef, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node as RFNode,
  type Edge as RFEdge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import AgentNodeComponent from './AgentNode';
import NodeEditor from './NodeEditor';
import type { AgentConfig, AgentEdge, AgentNode, ToolInfo } from '../types';
import { agentToFlow, flowToAgent } from '../agentToFlow';

const nodeTypes = { agentNode: AgentNodeComponent };

interface AgentGraphProps {
  config: AgentConfig;
  availableTools?: ToolInfo[];
  onAgentChange?: (updated: AgentConfig) => void;
}

function makeNewNode(existingIds: Set<string>): AgentNode {
  let i = 1;
  while (existingIds.has(`node_${i}`)) i++;
  return {
    name: `node_${i}`,
    task_messages: [{ role: 'developer', content: '' }],
    edges: [],
    tools: [],
    pre_actions: [],
    post_actions: [],
    end: false,
  };
}

export default function AgentGraph({ config, availableTools = [], onAgentChange }: AgentGraphProps) {
  // Initialise from config once; positions live in RF state, schema flows out via onAgentChange.
  const initRef = useRef(config);
  const { nodes: initNodes, edges: initEdges } = agentToFlow(initRef.current);

  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Top-level config fields (name, persona, …) that don't live in RF state.
  const cfgRef = useRef(config);

  const emit = useCallback((ns: RFNode[], es: RFEdge[], cfg = cfgRef.current) => {
    onAgentChange?.(flowToAgent(cfg, ns, es));
  }, [onAgentChange]);

  // ── Selection ──────────────────────────────────────────────────────────────
  const onNodeClick = useCallback((_: React.MouseEvent, node: RFNode) => {
    setSelectedId(node.id);
  }, []);
  const onPaneClick = useCallback(() => setSelectedId(null), []);

  // ── Add node ───────────────────────────────────────────────────────────────
  const addNode = useCallback(() => {
    const agentNode = makeNewNode(new Set(nodes.map(n => n.id)));
    const rfNode: RFNode = {
      id: agentNode.name,
      type: 'agentNode',
      position: { x: 80 + nodes.length * 24, y: 80 + nodes.length * 24 },
      data: { node: agentNode, isInitial: false },
    };
    const newNodes = [...nodes, rfNode];
    setNodes(newNodes);
    emit(newNodes, edges);
    setSelectedId(agentNode.name);
  }, [nodes, edges, emit, setNodes]);

  // ── Delete node (keyboard or NodeEditor button) ────────────────────────────
  const onNodesDelete = useCallback((deleted: RFNode[]) => {
    const ids = new Set(deleted.map(n => n.id));
    const newEdges = edges.filter(e => !ids.has(e.source) && !ids.has(e.target));
    const newNodes = nodes.filter(n => !ids.has(n.id));
    setEdges(newEdges);
    emit(newNodes, newEdges);
    if (selectedId && ids.has(selectedId)) setSelectedId(null);
  }, [nodes, edges, selectedId, emit, setEdges]);

  const deleteSelected = useCallback(() => {
    if (!selectedId) return;
    const newNodes = nodes.filter(n => n.id !== selectedId);
    const newEdges = edges.filter(e => e.source !== selectedId && e.target !== selectedId);
    setNodes(newNodes);
    setEdges(newEdges);
    emit(newNodes, newEdges);
    setSelectedId(null);
  }, [selectedId, nodes, edges, emit, setNodes, setEdges]);

  // ── Connect (drag edge) ────────────────────────────────────────────────────
  const onConnect = useCallback((connection: Connection) => {
    const fn = `${connection.source}_to_${connection.target}`;
    const edgeData: AgentEdge = {
      function: fn,
      description: '',
      target: connection.target!,
      properties: {},
      required: [],
    };
    const rfEdge: RFEdge = {
      id: `${connection.source}→${fn}`,
      source: connection.source!,
      target: connection.target!,
      label: fn,
      type: 'smoothstep',
      labelStyle: { fontSize: 11, fill: '#718096' },
      labelBgStyle: { fill: '#f8f9fa' },
      data: edgeData as unknown as Record<string, unknown>,
    };
    const newEdges = [...edges, rfEdge];
    setEdges(newEdges);
    emit(nodes, newEdges);
    setSelectedId(connection.source); // open source node to edit the new edge
  }, [nodes, edges, emit, setEdges]);

  // ── Delete edge (keyboard) ─────────────────────────────────────────────────
  const onEdgesDelete = useCallback((deleted: RFEdge[]) => {
    const ids = new Set(deleted.map(e => e.id));
    const newEdges = edges.filter(e => !ids.has(e.id));
    emit(nodes, newEdges);
  }, [nodes, edges, emit]);

  // ── Edit node data (NodeEditor) ────────────────────────────────────────────
  const updateNode = useCallback((nodeId: string, updated: AgentNode) => {
    const newName = updated.name;
    const renamed = newName !== nodeId;

    const newNodes = nodes.map(n => {
      if (n.id !== nodeId) return n;
      return { ...n, id: newName, data: { node: updated, isInitial: cfgRef.current.initial_node === nodeId } };
    });

    const newEdges = renamed
      ? edges.map(e => ({
          ...e,
          source: e.source === nodeId ? newName : e.source,
          target: e.target === nodeId ? newName : e.target,
          data: e.target === nodeId ? { ...(e.data as unknown as AgentEdge), target: newName } as unknown as Record<string, unknown> : e.data,
        }))
      : edges;

    let cfg = cfgRef.current;
    if (renamed && cfg.initial_node === nodeId) {
      cfg = { ...cfg, initial_node: newName };
      cfgRef.current = cfg;
    }

    setNodes(newNodes);
    setEdges(newEdges);
    if (renamed) setSelectedId(newName);
    emit(newNodes, newEdges, cfg);
  }, [nodes, edges, emit, setNodes, setEdges]);

  // ── Edit edge data (NodeEditor) ────────────────────────────────────────────
  const updateEdge = useCallback((nodeId: string, oldFn: string, updated: AgentEdge) => {
    const newEdges = edges.map(e => {
      if (e.source !== nodeId || (e.data as unknown as AgentEdge).function !== oldFn) return e;
      return {
        ...e,
        id: `${nodeId}→${updated.function}`,
        target: updated.target,
        label: updated.function,
        data: updated as unknown as Record<string, unknown>,
      };
    });
    setEdges(newEdges);
    emit(nodes, newEdges);
  }, [nodes, edges, emit, setEdges]);

  const deleteEdge = useCallback((nodeId: string, fn: string) => {
    const newEdges = edges.filter(e => !(e.source === nodeId && (e.data as unknown as AgentEdge).function === fn));
    setEdges(newEdges);
    emit(nodes, newEdges);
  }, [nodes, edges, emit, setEdges]);

  // ── Derived values for NodeEditor ──────────────────────────────────────────
  const selectedNode = selectedId ? nodes.find(n => n.id === selectedId) : null;
  const selectedAgentNode = selectedNode?.data.node as AgentNode | undefined;
  const outgoingEdges = edges
    .filter(e => e.source === selectedId)
    .map(e => e.data as unknown as AgentEdge);

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodesDelete={onNodesDelete}
          onEdgesDelete={onEdgesDelete}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          deleteKeyCode="Delete"
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
          <Panel position="top-left">
            <button
              onClick={addNode}
              style={{
                padding: '6px 12px',
                borderRadius: 6,
                border: '1.5px solid #e2e8f0',
                background: '#fff',
                fontWeight: 600,
                fontSize: 13,
                cursor: 'pointer',
                boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
              }}
            >
              + Add node
            </button>
          </Panel>
        </ReactFlow>
      </div>

      {selectedAgentNode && (
        <NodeEditor
          nodeId={selectedId!}
          agentNode={selectedAgentNode}
          isInitial={selectedId === cfgRef.current.initial_node}
          outgoingEdges={outgoingEdges}
          nodeNames={nodes.map(n => n.id)}
          availableTools={availableTools}
          onUpdateNode={updated => updateNode(selectedId!, updated)}
          onUpdateEdge={(oldFn, updated) => updateEdge(selectedId!, oldFn, updated)}
          onDeleteEdge={fn => deleteEdge(selectedId!, fn)}
          onDelete={deleteSelected}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
