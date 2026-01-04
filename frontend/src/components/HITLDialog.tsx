import React, { useState } from 'react';
import { HITLInterruptData, HITLCandidate, DetectedMemory } from '../types/message';

interface HITLDialogProps {
  interruptData: HITLInterruptData;
  onResponse: (response: any) => void;
  onCancel: () => void;
}

export const HITLDialog: React.FC<HITLDialogProps> = ({
  interruptData,
  onResponse,
  onCancel,
}) => {
  const [inputValue, setInputValue] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedMemories, setSelectedMemories] = useState<Set<number>>(new Set());

  const handleConfirm = () => {
    onResponse({ choice: '确认' });
  };

  const handleReject = () => {
    onResponse({ choice: '取消' });
  };

  const handleSelect = (candidate: HITLCandidate) => {
    setSelectedId(candidate.id);
    onResponse({ choice: candidate.id, selected: candidate.id });
  };

  const handleParamSubmit = () => {
    if (inputValue.trim()) {
      // 如果有多个缺失参数，这里简化处理，只填充第一个
      const params: Record<string, string> = {};
      if (interruptData.missing_params && interruptData.missing_params.length > 0) {
        params[interruptData.missing_params[0]] = inputValue.trim();
      }
      onResponse({ params });
    }
  };

  // 记忆选择处理
  const toggleMemorySelection = (index: number) => {
    const newSelection = new Set(selectedMemories);
    if (newSelection.has(index)) {
      newSelection.delete(index);
    } else {
      newSelection.add(index);
    }
    setSelectedMemories(newSelection);
  };

  const handleMemoryConfirm = () => {
    if (selectedMemories.size === 0) {
      onCancel();
      return;
    }

    const confirmed = interruptData.memories
      ?.filter((_, index) => selectedMemories.has(index))
      || [];

    onResponse({ confirmed_memories: confirmed });
  };

  const formatMemoryData = (memory: DetectedMemory): string => {
    const { type, data } = memory;
    const parts: string[] = [];

    if (type === 'profile') {
      if (data.name) parts.push(`姓名: ${data.name}`);
      if (data.occupation) parts.push(`职业: ${data.occupation}`);
      if (data.interests) {
        const interests = Array.isArray(data.interests) ? data.interests.join('、') : data.interests;
        parts.push(`兴趣: ${interests}`);
      }
      if (data.age_range) parts.push(`年龄段: ${data.age_range}`);
      if (data.mbti) parts.push(`MBTI: ${data.mbti}`);
    } else if (type === 'relationship') {
      if (data.name) parts.push(`姓名: ${data.name}`);
      if (data.relation) parts.push(`关系: ${data.relation}`);
      if (data.home_address) parts.push(`地址: ${data.home_address}`);
      if (data.phone) parts.push(`电话: ${data.phone}`);
    }

    return parts.join('，');
  };

  const renderContent = () => {
    switch (interruptData.type) {
      case 'confirmation':
        return (
          <div className="space-y-4">
            <p className="text-gray-700">{interruptData.message}</p>
            {interruptData.reason && (
              <p className="text-sm text-gray-500">{interruptData.reason}</p>
            )}
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleReject}
                className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg text-gray-700"
              >
                取消
              </button>
              <button
                onClick={handleConfirm}
                className="px-4 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg text-white"
              >
                确认
              </button>
            </div>
          </div>
        );

      case 'selection':
        return (
          <div className="space-y-4">
            <p className="text-gray-700">{interruptData.message}</p>
            <div className="max-h-60 overflow-y-auto space-y-2">
              {interruptData.candidates?.map((candidate) => (
                <div
                  key={candidate.id}
                  onClick={() => handleSelect(candidate)}
                  className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                    selectedId === candidate.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-medium">{candidate.id}. {candidate.name}</div>
                  {candidate.description && (
                    <div className="text-sm text-gray-500 mt-1">{candidate.description}</div>
                  )}
                </div>
              ))}
            </div>
            <div className="flex justify-end">
              <button
                onClick={onCancel}
                className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg text-gray-700"
              >
                取消
              </button>
            </div>
          </div>
        );

      case 'ask_params':
        return (
          <div className="space-y-4">
            <p className="text-gray-700">{interruptData.message}</p>
            {interruptData.missing_params && interruptData.missing_params.length > 0 && (
              <p className="text-sm text-gray-500">
                缺少参数: {interruptData.missing_params.join(', ')}
              </p>
            )}
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleParamSubmit()}
              placeholder="请输入..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            <div className="flex gap-3 justify-end">
              <button
                onClick={onCancel}
                className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg text-gray-700"
              >
                取消
              </button>
              <button
                onClick={handleParamSubmit}
                disabled={!inputValue.trim()}
                className="px-4 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                提交
              </button>
            </div>
          </div>
        );

      case 'save_memory':
        return (
          <div className="space-y-4">
            <p className="text-gray-700">{interruptData.message}</p>
            <div className="max-h-60 overflow-y-auto space-y-2">
              {interruptData.memories?.map((memory, index) => (
                <div
                  key={index}
                  onClick={() => toggleMemorySelection(index)}
                  className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                    selectedMemories.has(index)
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={selectedMemories.has(index)}
                      onChange={() => toggleMemorySelection(index)}
                      className="mt-1 cursor-pointer"
                      onClick={(e) => e.stopPropagation()}
                    />
                    <div className="flex-1">
                      <div className="font-medium">
                        {memory.type === 'profile' ? '👤 用户画像' : '👥 关系网络'}
                      </div>
                      <div className="text-sm text-gray-600 mt-1">
                        {formatMemoryData(memory)}
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        置信度: {memory.confidence === 'high' ? '高' : memory.confidence === 'medium' ? '中' : '低'}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={onCancel}
                className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg text-gray-700"
              >
                取消
              </button>
              <button
                onClick={handleMemoryConfirm}
                disabled={selectedMemories.size === 0}
                className="px-4 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                保存 ({selectedMemories.size})
              </button>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  const getTitle = () => {
    switch (interruptData.type) {
      case 'confirmation':
        return '操作确认';
      case 'selection':
        return '请选择';
      case 'ask_params':
        return '需要更多信息';
      case 'save_memory':
        return '保存记忆';
      default:
        return '请确认';
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-blue-500 text-white px-6 py-4">
          <h3 className="text-lg font-semibold">{getTitle()}</h3>
          {interruptData.tool_name && (
            <p className="text-sm text-blue-100 mt-1">
              工具: {interruptData.tool_name}
            </p>
          )}
        </div>

        {/* Content */}
        <div className="p-6">
          {renderContent()}
        </div>
      </div>
    </div>
  );
};
