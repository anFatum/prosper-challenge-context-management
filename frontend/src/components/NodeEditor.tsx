import { useState, type CSSProperties } from 'react';
import type { AgentEdge, AgentNode, ToolInfo } from '../types';

interface NodeEditorProps {
  nodeId: string;
  agentNode: AgentNode;
  isInitial: boolean;
  outgoingEdges: AgentEdge[];
  nodeNames: string[];
  availableTools?: ToolInfo[];
  onUpdateNode: (updated: AgentNode) => void;
  onUpdateEdge: (oldFn: string, updated: AgentEdge) => void;
  onDeleteEdge: (fn: string) => void;
  onDelete: () => void;
  onClose: () => void;
}

export default function NodeEditor({
  nodeId,
  agentNode,
  isInitial,
  outgoingEdges,
  nodeNames,
  availableTools = [],
  onUpdateNode,
  onUpdateEdge,
  onDeleteEdge,
  onDelete,
  onClose,
}: NodeEditorProps) {
  const task = agentNode.task_messages[0]?.content ?? '';
  const set = (patch: Partial<AgentNode>) => onUpdateNode({ ...agentNode, ...patch });

  return (
    <div style={{
      width: 288,
      flexShrink: 0,
      height: '100%',
      background: '#fff',
      borderLeft: '1px solid #e2e8f0',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 14px',
        borderBottom: '1px solid #e2e8f0',
        flexShrink: 0,
      }}>
        <span style={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {nodeId}
        </span>
        <button onClick={onClose} style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#718096', fontSize: 18, lineHeight: 1, padding: '0 2px' }}>
          ×
        </button>
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 16 }}>

        <Field label="Name">
          <input
            value={agentNode.name}
            onChange={e => set({ name: e.target.value })}
            style={input}
          />
        </Field>

        <Field label="Task">
          <textarea
            value={task}
            rows={5}
            onChange={e => set({
              task_messages: [
                { role: 'developer', content: e.target.value },
                ...agentNode.task_messages.slice(1),
              ],
            })}
            style={{ ...input, resize: 'vertical' }}
          />
        </Field>

        <Field label="Role override">
          <input
            value={agentNode.role_message ?? ''}
            placeholder="Inherits global persona"
            onChange={e => set({ role_message: e.target.value || undefined })}
            style={input}
          />
        </Field>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={agentNode.end ?? false}
            onChange={e => set({ end: e.target.checked })}
          />
          Terminal node (ends the call)
        </label>

        {availableTools.length > 0 && (
          <div>
            <SectionLabel>Tools</SectionLabel>
            <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {availableTools.map(tool => {
                const enabled = (agentNode.tools ?? []).includes(tool.name);
                return (
                  <label
                    key={tool.name}
                    title={tool.description}
                    style={{ display: 'flex', alignItems: 'flex-start', gap: 7, cursor: 'pointer', fontSize: 13 }}
                  >
                    <input
                      type="checkbox"
                      checked={enabled}
                      style={{ marginTop: 2, flexShrink: 0 }}
                      onChange={e => {
                        const current = agentNode.tools ?? [];
                        const tools = e.target.checked
                          ? [...current, tool.name]
                          : current.filter(t => t !== tool.name);
                        set({ tools });
                      }}
                    />
                    <span>
                      <span style={{ fontWeight: 500 }}>{tool.name}</span>
                      {tool.description && (
                        <span style={{ display: 'block', fontSize: 11, color: '#718096', marginTop: 1 }}>
                          {tool.description}
                        </span>
                      )}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
        )}

        <div>
          <SectionLabel>Outgoing edges</SectionLabel>
          {outgoingEdges.length === 0 ? (
            <p style={{ fontSize: 12, color: '#a0aec0', marginTop: 6 }}>
              Drag from this node's right handle to another node to add an edge.
            </p>
          ) : (
            outgoingEdges.map(e => (
              <EdgeRow
                key={e.function}
                edge={e}
                nodeNames={nodeNames}
                onUpdate={updated => onUpdateEdge(e.function, updated)}
                onDelete={() => onDeleteEdge(e.function)}
              />
            ))
          )}
        </div>
      </div>

      {/* Footer */}
      {!isInitial && (
        <div style={{ padding: 14, borderTop: '1px solid #e2e8f0', flexShrink: 0 }}>
          <button
            onClick={onDelete}
            style={{
              width: '100%',
              padding: '7px 0',
              borderRadius: 6,
              border: '1.5px solid #feb2b2',
              background: '#fff',
              color: '#e53e3e',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            Delete node
          </button>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <SectionLabel>{label}</SectionLabel>
      <div style={{ marginTop: 5 }}>{children}</div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 10, fontWeight: 700, color: '#718096', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
      {children}
    </div>
  );
}

function EdgeRow({ edge, nodeNames, onUpdate, onDelete }: {
  edge: AgentEdge;
  nodeNames: string[];
  onUpdate: (e: AgentEdge) => void;
  onDelete: () => void;
}) {
  const [propsJson, setPropsJson] = useState(
    Object.keys(edge.properties ?? {}).length
      ? JSON.stringify(edge.properties, null, 2)
      : ''
  );
  const [propsError, setPropsError] = useState<string | null>(null);

  const handlePropsChange = (raw: string) => {
    setPropsJson(raw);
    if (raw.trim() === '') {
      setPropsError(null);
      onUpdate({ ...edge, properties: {} });
      return;
    }
    try {
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      setPropsError(null);
      onUpdate({ ...edge, properties: parsed });
    } catch {
      setPropsError('Invalid JSON');
    }
  };

  return (
    <div style={{
      border: '1px solid #e2e8f0',
      borderRadius: 6,
      padding: 10,
      marginTop: 8,
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
    }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <input
          value={edge.function}
          placeholder="function name"
          onChange={e => onUpdate({ ...edge, function: e.target.value })}
          style={{ ...input, fontSize: 12, flex: 1 }}
        />
        <button onClick={onDelete} title="Remove edge" style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#a0aec0', fontSize: 16, lineHeight: 1, padding: '0 2px', flexShrink: 0 }}>
          ×
        </button>
      </div>
      <input
        value={edge.description}
        placeholder="when to call this"
        onChange={e => onUpdate({ ...edge, description: e.target.value })}
        style={{ ...input, fontSize: 12 }}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ color: '#718096', fontSize: 11, flexShrink: 0 }}>→</span>
        <select
          value={edge.target}
          onChange={e => onUpdate({ ...edge, target: e.target.value })}
          style={{ ...input, fontSize: 12, flex: 1 }}
        >
          {nodeNames.map(name => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
      </div>
      <div>
        <div style={{ fontSize: 10, color: '#a0aec0', marginBottom: 3 }}>Properties (JSON schema)</div>
        <textarea
          value={propsJson}
          rows={3}
          placeholder={'{\n  "field": { "type": "string" }\n}'}
          onChange={e => handlePropsChange(e.target.value)}
          style={{
            ...input,
            fontSize: 11,
            fontFamily: 'monospace',
            resize: 'vertical',
            borderColor: propsError ? '#fc8181' : '#e2e8f0',
          }}
        />
        {propsError && <div style={{ fontSize: 10, color: '#e53e3e', marginTop: 2 }}>{propsError}</div>}
      </div>
      <div>
        <div style={{ fontSize: 10, color: '#a0aec0', marginBottom: 3 }}>Required (comma-separated)</div>
        <input
          value={(edge.required ?? []).join(', ')}
          placeholder="field1, field2"
          onChange={e => onUpdate({
            ...edge,
            required: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
          })}
          style={{ ...input, fontSize: 12 }}
        />
      </div>
    </div>
  );
}

const input: CSSProperties = {
  width: '100%',
  padding: '6px 8px',
  border: '1.5px solid #e2e8f0',
  borderRadius: 5,
  fontSize: 13,
  outline: 'none',
  fontFamily: 'inherit',
  boxSizing: 'border-box',
};