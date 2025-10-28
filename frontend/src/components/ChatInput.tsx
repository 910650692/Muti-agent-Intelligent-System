import React, { useState } from 'react';

interface ChatInputProps {
onSend: (message: string) => void;
disabled: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, disabled }) => {
const [input, setInput] = useState('');

const handleSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  if (input.trim() && !disabled) {
    onSend(input.trim());
    setInput('');
  }
};

return (
  <form onSubmit={handleSubmit} className="border-t p-4">
    <div className="flex gap-2">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="输入消息..."
        disabled={disabled}
        className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2
focus:ring-blue-500 disabled:bg-gray-100"
      />
      <button
        type="submit"
        disabled={disabled || !input.trim()}
        className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300
disabled:cursor-not-allowed"
      >
        发送
      </button>
    </div>
  </form>
);
};