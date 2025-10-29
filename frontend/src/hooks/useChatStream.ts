import { useState, useCallback, useEffect } from 'react';
import { Message } from '../types/message';

const API_BASE_URL = 'http://localhost:8000';

// 从 localStorage 获取或创建新的 session ID
const getOrCreateSessionId = (): string => {
  const stored = localStorage.getItem('chat_session_id');
  if (stored) {
    return stored;
  }
  const newId = `session-${Date.now()}`;
  localStorage.setItem('chat_session_id', newId);
  return newId;
};

 export const useChatStream = () => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 从 localStorage 获取 session ID
    const [sessionId, setSessionId] = useState(() => getOrCreateSessionId());

    // 从 localStorage 加载历史消息
    useEffect(() => {
      const storedMessages = localStorage.getItem(`chat_messages_${sessionId}`);
      if (storedMessages) {
        try {
          const parsed = JSON.parse(storedMessages);
          // 恢复 Date 对象
          const messagesWithDates = parsed.map((msg: any) => ({
            ...msg,
            timestamp: new Date(msg.timestamp)
          }));
          setMessages(messagesWithDates);
        } catch (e) {
          console.error('Failed to load messages from localStorage:', e);
        }
      }
    }, [sessionId]);

    // 保存消息到 localStorage
    useEffect(() => {
      if (messages.length > 0) {
        localStorage.setItem(`chat_messages_${sessionId}`, JSON.stringify(messages));
      }
    }, [messages, sessionId]);

    const sendMessage = useCallback(async (userMessage: string) => {
      // 添加用户消息
      const userMsg: Message = {
        role: 'user',
        content: userMessage,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: userMessage,
            thread_id: sessionId,  // 使用持久化的 session ID
          }),
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error('Response body is null');
        }

        let assistantContent = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));

                if (data.type === 'token') {
                  // 逐字符累积（打字机效果）
                  assistantContent += data.content;

                  setMessages((prev) => {
                    const newMessages = [...prev];
                    const lastMsg = newMessages[newMessages.length - 1];

                    if (lastMsg?.role === 'assistant') {
                      // 更新最后一条 assistant 消息
                      lastMsg.content = assistantContent;
                    } else {
                      // 添加新的 assistant 消息
                      newMessages.push({
                        role: 'assistant',
                        content: assistantContent,
                        timestamp: new Date(),
                      });
                    }
                    return newMessages;
                  });
                } else if (data.type === 'message') {
                  // 兼容旧的完整消息格式
                  assistantContent += data.content + '\n\n';

                  setMessages((prev) => {
                    const newMessages = [...prev];
                    const lastMsg = newMessages[newMessages.length - 1];

                    if (lastMsg?.role === 'assistant') {
                      lastMsg.content = assistantContent.trim();
                    } else {
                      newMessages.push({
                        role: 'assistant',
                        content: assistantContent.trim(),
                        timestamp: new Date(),
                      });
                    }
                    return newMessages;
                  });
                } else if (data.type === 'error') {
                  setError(data.message || '发生未知错误');
                } else if (data.type === 'done') {
                  setIsLoading(false);
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', e);
              }
            }
          }
        }

        setIsLoading(false);
      } catch (err) {
        console.error('Stream error:', err);
        setError(err instanceof Error ? err.message : '发生未知错误');
        setIsLoading(false);
      }
    }, [sessionId]);  // 添加 sessionId 依赖

    const clearMessages = useCallback(() => {
      setMessages([]);
      setError(null);
    }, []);

    const startNewChat = useCallback(() => {
      // 创建新的 session ID
      const newId = `session-${Date.now()}`;
      localStorage.setItem('chat_session_id', newId);
      setSessionId(newId);

      // 清空当前消息
      setMessages([]);
      setError(null);

      // 清除旧的消息记录
      localStorage.removeItem(`chat_messages_${sessionId}`);
    }, [sessionId]);

    return { messages, isLoading, error, sendMessage, clearMessages, startNewChat };
  };