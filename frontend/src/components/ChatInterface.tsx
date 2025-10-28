import React, { useEffect, useRef } from 'react';
import { useChatStream } from '../hooks/useChatStream';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';

export const ChatInterface: React.FC = () => {
const { messages, isLoading, error, sendMessage, clearMessages } = useChatStream();
const messagesEndRef = useRef<HTMLDivElement>(null);

// 自动滚动到底部
useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
}, [messages]);

return (
  <div className="flex flex-col h-screen max-w-4xl mx-auto bg-white shadow-lg">
    {/* Header */}
    <div className="bg-blue-500 text-white p-4 flex justify-between items-center">
      <h1 className="text-xl font-bold">🤖 智能助手</h1>
      <button
        onClick={clearMessages}
        className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm"
      >
        清空对话
      </button>
    </div>

    {/* Messages */}
    <div className="flex-1 overflow-y-auto p-4">
      {messages.length === 0 && (
        <div className="text-center text-gray-500 mt-10">
          <p className="text-lg mb-2">👋 你好！我是智能助手</p>
          <p className="text-sm">你可以问我天气相关的问题</p>
          <p className="text-xs text-gray-400 mt-4">
            例如："北京明天天气怎么样？"
          </p>
        </div>
      )}

      {messages.map((msg, index) => (
        <ChatMessage key={index} message={msg} />
      ))}

      {isLoading && (
        <div className="flex justify-start mb-4">
          <div className="bg-gray-200 rounded-lg px-4 py-2">
            <div className="flex space-x-2">
              <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-100"></div>
              <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-200"></div>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          ❌ {error}
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>

    {/* Input */}
    <ChatInput onSend={sendMessage} disabled={isLoading} />
  </div>
);
};