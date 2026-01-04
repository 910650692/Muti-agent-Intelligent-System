import { useState, useCallback, useEffect } from 'react';

const API_BASE_URL = 'http://localhost:8000';
const USER_ID = 'user_001';

export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  is_archived: boolean;
  preview: string | null;
}

export const useConversations = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载对话列表
  const loadConversations = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/conversations?user_id=${USER_ID}`);
      if (!response.ok) {
        throw new Error('Failed to load conversations');
      }
      const data = await response.json();
      setConversations(data);
    } catch (err) {
      console.error('Load conversations error:', err);
      setError(err instanceof Error ? err.message : '加载对话列表失败');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 创建新对话
  const createConversation = useCallback(async (title?: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/conversations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: USER_ID,
          title: title || '新对话',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create conversation');
      }

      const newConversation = await response.json();
      setConversations((prev) => [newConversation, ...prev]);
      return newConversation;
    } catch (err) {
      console.error('Create conversation error:', err);
      setError(err instanceof Error ? err.message : '创建对话失败');
      return null;
    }
  }, []);

  // 删除对话
  const deleteConversation = useCallback(async (conversationId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete conversation');
      }

      setConversations((prev) => prev.filter((conv) => conv.id !== conversationId));

      // 清除该对话的本地消息缓存
      localStorage.removeItem(`chat_messages_${conversationId}`);

      return true;
    } catch (err) {
      console.error('Delete conversation error:', err);
      setError(err instanceof Error ? err.message : '删除对话失败');
      return false;
    }
  }, []);

  // 更新对话标题
  const updateConversationTitle = useCallback(async (conversationId: string, title: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title }),
      });

      if (!response.ok) {
        throw new Error('Failed to update conversation');
      }

      const updatedConversation = await response.json();
      setConversations((prev) =>
        prev.map((conv) => (conv.id === conversationId ? updatedConversation : conv))
      );
      return updatedConversation;
    } catch (err) {
      console.error('Update conversation error:', err);
      setError(err instanceof Error ? err.message : '更新对话失败');
      return null;
    }
  }, []);

  // 加载对话的完整消息历史
  const loadConversationMessages = useCallback(async (conversationId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/messages`);
      if (!response.ok) {
        throw new Error('Failed to load messages');
      }
      return await response.json();
    } catch (err) {
      console.error('Load messages error:', err);
      setError(err instanceof Error ? err.message : '加载消息失败');
      return [];
    }
  }, []);

  // 初始加载
  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  return {
    conversations,
    isLoading,
    error,
    loadConversations,
    createConversation,
    deleteConversation,
    updateConversationTitle,
    loadConversationMessages,
  };
};
