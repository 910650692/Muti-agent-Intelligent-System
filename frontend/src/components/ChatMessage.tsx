import React from 'react';
import { Message } from '../types/message';

interface ChatMessageProps {
message: Message;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
    const isUser = message.role === 'user';

    // 格式化延迟时间（毫秒转为秒，保留2位小数）
    const formatLatency = (ms: number | undefined): string => {
      if (ms === undefined) return '-';
      return `${(ms / 1000).toFixed(2)}s`;
    };

    return (
      <div
        className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}
      >
        <div
          className={`max-w-[70%] rounded-lg px-4 py-2 ${
            isUser
              ? 'bg-blue-500 text-white'
              : 'bg-gray-200 text-gray-800'
          }`}
        >
          {/* 显示图片（如果有） */}
          {message.images && message.images.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {message.images.map((img, index) => (
                <img
                  key={index}
                  src={img.data}
                  alt={`image-${index}`}
                  className="max-w-full max-h-60 rounded border"
                />
              ))}
            </div>
          )}

          {/* 显示文本内容 */}
          {message.content && (
            <div className="whitespace-pre-wrap break-words">
              {message.content}
            </div>
          )}

          {/* 时间戳和性能指标 */}
          <div className="flex items-center justify-between mt-1 gap-2">
            {/* 时间戳 */}
            <div
              className={`text-xs ${
                isUser ? 'text-blue-100' : 'text-gray-500'
              }`}
            >
              {message.timestamp.toLocaleTimeString()}
            </div>

            {/* 性能指标（仅显示assistant消息） */}
            {!isUser && message.metrics && (
              <div
                className="text-xs text-gray-400 flex items-center gap-2"
                title="首字延迟 | 总延迟"
              >
                {message.metrics.firstTokenLatency !== undefined && (
                  <span>
                    首字: {formatLatency(message.metrics.firstTokenLatency)}
                  </span>
                )}
                {message.metrics.totalLatency !== undefined && (
                  <span>
                    总计: {formatLatency(message.metrics.totalLatency)}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };