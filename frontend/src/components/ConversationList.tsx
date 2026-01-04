import React, { useState } from 'react';
import { Conversation } from '../hooks/useConversations';
import './ConversationList.css';

interface ConversationListProps {
  conversations: Conversation[];
  currentConversationId: string | null;  // ⚠️ 允许 null（初始状态）
  onSelectConversation: (conversationId: string) => void;
  onDeleteConversation: (conversationId: string) => void;
  onNewConversation: () => void;
}

export const ConversationList: React.FC<ConversationListProps> = ({
  conversations,
  currentConversationId,
  onSelectConversation,
  onDeleteConversation,
  onNewConversation,
}) => {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  console.log('ConversationList渲染:', {
    conversationsCount: conversations.length,
    currentConversationId,
    conversations
  });

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins}分钟前`;
    if (diffHours < 24) return `${diffHours}小时前`;
    if (diffDays < 7) return `${diffDays}天前`;
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="conversation-list">
      <div className="conversation-list-header">
        <h2>对话</h2>
        <button className="new-conversation-btn" onClick={onNewConversation} title="新建对话">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      <div className="conversation-list-items">
        {conversations.length === 0 ? (
          <div className="empty-state">
            <p>还没有对话</p>
            <p className="empty-hint">点击 + 创建新对话</p>
          </div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${conv.id === currentConversationId ? 'active' : ''}`}
              onClick={() => onSelectConversation(conv.id)}
              onMouseEnter={() => setHoveredId(conv.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              <div className="conversation-content">
                <div className="conversation-header">
                  <h3 className="conversation-title">{conv.title}</h3>
                  <span className="conversation-time">{formatDate(conv.updated_at)}</span>
                </div>
                {conv.preview && (
                  <p className="conversation-preview">{conv.preview}</p>
                )}
                <div className="conversation-meta">
                  <span className="message-count">{conv.message_count} 条消息</span>
                </div>
              </div>

              {hoveredId === conv.id && (
                <button
                  className="delete-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm('确定要删除这个对话吗？')) {
                      onDeleteConversation(conv.id);
                    }
                  }}
                  title="删除对话"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
