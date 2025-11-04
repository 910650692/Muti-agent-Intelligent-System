import React from 'react';
import { Message } from '../types/message';

interface ChatMessageProps {
message: Message;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
    const isUser = message.role === 'user';

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

          {/* 时间戳 */}
          <div
            className={`text-xs mt-1 ${
              isUser ? 'text-blue-100' : 'text-gray-500'
            }`}
          >
            {message.timestamp.toLocaleTimeString()}
          </div>
        </div>
      </div>
    );
  };