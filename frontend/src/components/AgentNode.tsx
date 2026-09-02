import { Handle, Position } from '@xyflow/react';
import type { AgentNode as AgentNodeData } from '../types';

interface AgentNodeProps {
  data: {
    node: AgentNodeData;
    isInitial: boolean;
  };
}

export default function AgentNode({ data }: AgentNodeProps) {
  const { node, isInitial } = data;
  const firstTask = node.task_messages[0]?.content ?? '';
  const preview = firstTask.length > 80 ? firstTask.slice(0, 80) + '…' : firstTask;

  const bg = isInitial
    ? 'var(--color-node-initial)'
    : node.end
    ? 'var(--color-node-terminal)'
    : 'var(--color-node-bg)';

  return (
    <div style={{
      background: bg,
      border: `1.5px solid var(--color-node-border)`,
      borderRadius: 8,
      padding: '10px 14px',
      width: 240,
      minHeight: 80,
      boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
    }}>
      <Handle type="target" position={Position.Left} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{node.name}</span>
        {isInitial && <Badge color="#3b82f6">start</Badge>}
        {node.end && <Badge color="#22c55e">end</Badge>}
      </div>

      {preview && (
        <p style={{ fontSize: 11, color: 'var(--color-text-muted)', lineHeight: 1.4 }}>
          {preview}
        </p>
      )}

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

function Badge({ children, color }: { children: string; color: string }) {
  return (
    <span style={{
      fontSize: 10,
      fontWeight: 600,
      color,
      border: `1px solid ${color}`,
      borderRadius: 4,
      padding: '1px 5px',
      lineHeight: '14px',
    }}>
      {children}
    </span>
  );
}