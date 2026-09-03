export interface AgentEdge {
  function: string;
  description: string;
  target: string;
  properties: Record<string, unknown>;
  required: string[];
}

export interface AgentNode {
  name: string;
  task_messages: Array<{ role: string; content: string }>;
  role_message?: string;
  edges?: AgentEdge[];
  tools?: string[];
  pre_actions: unknown[];
  post_actions: unknown[];
  end: boolean;
}

export interface ToolInfo {
  name: string;
  description: string;
}

export interface AgentConfig {
  name: string;
  persona: string;
  voice_id: string;
  model: string;
  initial_node: string;
  nodes: AgentNode[];
}
