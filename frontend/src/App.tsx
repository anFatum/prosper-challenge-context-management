import { useEffect, useState } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import AgentGraph from './components/AgentGraph';
import type { AgentConfig, ToolInfo } from './types';

type CallStatus = 'idle' | 'connecting' | 'connected';

export default function App() {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [availableTools, setAvailableTools] = useState<ToolInfo[]>([]);
  const [isDirty, setIsDirty] = useState(false);
  const [callStatus, setCallStatus] = useState<CallStatus>('idle');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const apiError = 'Failed to load agent — is the API server running? (make run-api)';
    Promise.all([
      fetch('/api/agent').then(r => { if (!r.ok) throw new Error(); return r.json() as Promise<AgentConfig>; }),
      fetch('/api/tools').then(r => { if (!r.ok) throw new Error(); return r.json() as Promise<ToolInfo[]>; }),
    ])
      .then(([agentData, toolsData]) => {
        setConfig(agentData);
        setAvailableTools(toolsData);
        setIsDirty(false);
      })
      .catch(() => setLoadError(apiError));
  }, []);

  // Called by AgentGraph when the schema changes (node/edge edits, not drag repositioning)
  const handleAgentChange = (updated: AgentConfig) => {
    setConfig(updated);
    setIsDirty(true);
    setSaveError(null);
  };

  const handleSave = async () => {
    if (!config || saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      const r = await fetch('/api/agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (!r.ok) {
        const err = await r.json() as { detail?: string };
        setSaveError(err.detail ?? 'Save failed');
        return;
      }
      setIsDirty(false);
    } catch {
      setSaveError('Save failed — is the API server running? (make run-api)');
    } finally {
      setSaving(false);
    }
  };

  const handleConnect = () => {
    if (callStatus === 'idle') {
      setCallStatus('connecting');
      // TODO: WebRTC handshake with pipecat backend
      setTimeout(() => setCallStatus('connected'), 800);
    } else {
      setCallStatus('idle');
    }
  };

  const canConnect = !isDirty && callStatus === 'idle';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        height: 52,
        background: 'var(--color-surface)',
        borderBottom: '1px solid var(--color-border)',
        flexShrink: 0,
        gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontWeight: 700, fontSize: 16 }}>Prosper</span>
          {config && (
            <span style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>
              / {config.name}
            </span>
          )}
          {isDirty && (
            <span style={{ fontSize: 11, color: '#f59e0b', fontWeight: 500 }}>
              Unsaved changes
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {saveError && (
            <span style={{ fontSize: 12, color: '#dc2626', maxWidth: 280 }}>{saveError}</span>
          )}

          <button
            onClick={handleSave}
            disabled={!isDirty || saving}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              border: '1.5px solid var(--color-border)',
              cursor: (!isDirty || saving) ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: 13,
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              opacity: (!isDirty || saving) ? 0.4 : 1,
            }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>

          {callStatus === 'connected' && (
            <span style={{ fontSize: 12, color: 'var(--color-success)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--color-success)', display: 'inline-block' }} />
              Connected
            </span>
          )}

          <button
            onClick={handleConnect}
            disabled={!canConnect && callStatus === 'idle'}
            title={isDirty ? 'Save your changes before connecting' : undefined}
            style={{
              padding: '6px 16px',
              borderRadius: 6,
              border: 'none',
              cursor: (!canConnect && callStatus === 'idle') ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: 13,
              background: callStatus === 'connected'
                ? '#fee2e2'
                : (!canConnect && callStatus === 'idle')
                ? '#94a3b8'
                : 'var(--color-primary)',
              color: callStatus === 'connected' ? '#dc2626' : '#fff',
              transition: 'background 0.15s',
            }}
          >
            {callStatus === 'idle'
              ? 'Connect'
              : callStatus === 'connecting'
              ? 'Connecting…'
              : 'Disconnect'}
          </button>
        </div>
      </header>

      <main style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {loadError && (
          <div style={{ padding: 24, color: '#dc2626' }}>{loadError}</div>
        )}
        {config && (
          <ReactFlowProvider>
            <AgentGraph config={config} availableTools={availableTools} onAgentChange={handleAgentChange} />
          </ReactFlowProvider>
        )}
      </main>
    </div>
  );
}