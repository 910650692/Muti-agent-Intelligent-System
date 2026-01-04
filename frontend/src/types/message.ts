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
    | 'error'
    | 'interrupt'
    | 'waiting_input'
    | 'resume_start';
  node?: string;
  content?: string;
  message?: string;
  tool?: string;
  result?: string;
  data?: HITLInterruptData;  // HITL 中断数据
}

// ===== HITL (Human-in-the-Loop) 类型定义 =====

export type HITLType = 'confirmation' | 'selection' | 'ask_params' | 'save_memory';

export interface HITLCandidate {
  id: number;
  name: string;
  description?: string;
  raw?: any;
}

// 记忆检测数据结构
export interface DetectedMemory {
  type: 'profile' | 'relationship';
  data: Record<string, any>;
  confidence: 'high' | 'medium' | 'low';
}

export interface HITLInterruptData {
  type: HITLType;
  tool_name?: string;
  message: string;
  options?: string[];           // 用于确认类型
  candidates?: HITLCandidate[]; // 用于选择类型
  missing_params?: string[];    // 用于缺参追问
  current_args?: Record<string, any>;
  args?: Record<string, any>;
  reason?: string;
  memories?: DetectedMemory[];  // 用于记忆保存确认
}

export interface HITLState {
  isWaiting: boolean;           // 是否正在等待用户输入
  interruptData: HITLInterruptData | null;  // 中断数据
}
