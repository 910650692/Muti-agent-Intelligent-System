export interface Message {
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: Date;
  }
  export interface SSEEvent {
    type: 'start' | 'node_start' | 'node_end' | 'message' | 'done' | 'error';
    node?: string;
    content?: string;
    message?: string;
  }