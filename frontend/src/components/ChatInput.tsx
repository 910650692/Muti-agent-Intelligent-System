import React, { useState, useRef } from 'react';
import { ImageData } from '../types/message';

interface ChatInputProps {
  onSend: (message: string, images?: ImageData[]) => void;
  disabled: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, disabled }) => {
  const [input, setInput] = useState('');
  const [selectedImages, setSelectedImages] = useState<ImageData[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if ((input.trim() || selectedImages.length > 0) && !disabled) {
      onSend(input.trim(), selectedImages.length > 0 ? selectedImages : undefined);
      setInput('');
      setSelectedImages([]);
    }
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    Array.from(files).forEach((file) => {
      if (!file.type.startsWith('image/')) {
        alert('请选择图片文件');
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const base64 = event.target?.result as string;
        setSelectedImages((prev) => [...prev, {
          type: 'base64',
          data: base64,
        }]);
      };
      reader.readAsDataURL(file);
    });

    // 清空input，允许重复选择同一文件
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeImage = (index: number) => {
    setSelectedImages((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <form onSubmit={handleSubmit} className="border-t p-4">
      {/* 图片预览区 */}
      {selectedImages.length > 0 && (
        <div className="flex gap-2 mb-2 flex-wrap">
          {selectedImages.map((img, index) => (
            <div key={index} className="relative group">
              <img
                src={img.data}
                alt={`preview-${index}`}
                className="w-20 h-20 object-cover rounded border"
              />
              <button
                type="button"
                onClick={() => removeImage(index)}
                className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-6 h-6 text-sm hover:bg-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        {/* 图片选择按钮 */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleImageSelect}
          className="hidden"
          disabled={disabled}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          className="px-3 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:bg-gray-100 disabled:cursor-not-allowed"
          title="选择图片"
        >
          📷
        </button>

        {/* 文本输入 */}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入消息..."
          disabled={disabled}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
        />

        {/* 发送按钮 */}
        <button
          type="submit"
          disabled={disabled || (!input.trim() && selectedImages.length === 0)}
          className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          发送
        </button>
      </div>
    </form>
  );
};