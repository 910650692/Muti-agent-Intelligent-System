export interface ImageData {
  type: 'base64' | 'url';
  data: string;
}

export interface PerformanceMetrics {
  firstTokenLatency?: number;  // 首字延迟（毫秒）
  totalLatency?: number;        // 总延迟（毫秒）
  startTime?: number;           // 开始时间戳
}

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  node?: string;
  images?: ImageData[];  // 支持多图片
  metrics?: PerformanceMetrics;  // 性能指标
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
