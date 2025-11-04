export interface ImageData {
  type: 'base64' | 'url';
  data: string;
}

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  node?: string;
  images?: ImageData[];  // 支持多图片
}

export interface SSEEvent {
  type:
    | 'start'
    | 'node_start'
    | 'node_end'
    | 'token'
    | 'message'
    | 'tool_start'
    | 'tool_end'
    | 'done'
    | 'error';
  node?: string;
  content?: string;
  message?: string;
  tool?: string;
  result?: string;
}
