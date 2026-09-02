import { useEffect, useState } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import AgentGraph from './components/AgentGraph';
import type { AgentConfig } from './types';

type CallStatus = 'idle' | 'connecting' | 'connected';

export default function App() {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [callStatus, setCallStatus] = useState<CallStatus>('idle');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/example_flow.json')
      .then(r => r.json())
      .then((data: AgentConfig) => setConfig(data))
      .catch(() => setError('Failed to load agent flow.'));
  }, []);

  const handleConnect = () => {
    if (callStatus === 'idle') {
      setCallStatus('connecting');
      // TODO: initiate WebRTC connection to pipecat backend
      setTimeout(() => setCallStatus('connected'), 800);
    } else {
      setCallStatus('idle');
    }
  };

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
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontWeight: 700, fontSize: 16 }}>Prosper</span>
          {config && (
            <span style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>
              / {config.name}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {callStatus === 'connected' && (
            <span style={{ fontSize: 12, color: 'var(--color-success)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--color-success)', display: 'inline-block' }} />
              Connected
            </span>
          )}
          <button
            onClick={handleConnect}
            style={{
              padding: '6px 16px',
              borderRadius: 6,
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: 13,
              background: callStatus === 'connected' ? '#fee2e2' : 'var(--color-primary)',
              color: callStatus === 'connected' ? '#dc2626' : '#fff',
              transition: 'background 0.15s',
            }}
          >
            {callStatus === 'idle' ? 'Connect' : callStatus === 'connecting' ? 'Connecting…' : 'Disconnect'}
          </button>
        </div>
      </header>

      <main style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {error && (
          <div style={{ padding: 24, color: '#dc2626' }}>{error}</div>
        )}
        {config && (
          <ReactFlowProvider>
            <AgentGraph config={config} />
          </ReactFlowProvider>
        )}
      </main>
    </div>
  );
}