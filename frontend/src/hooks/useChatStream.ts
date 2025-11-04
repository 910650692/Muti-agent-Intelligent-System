import { useState, useCallback, useEffect } from 'react';
import { Message, ImageData } from '../types/message';

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

    const sendMessage = useCallback(async (userMessage: string, images?: ImageData[]) => {
      // 添加用户消息
      const userMsg: Message = {
        role: 'user',
        content: userMessage,
        timestamp: new Date(),
        images,  // 包含图片
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
            images,  // 发送图片到后端
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

        const nodeMessageIndex = new Map<string, number>();
        const defaultNodeKey = 'assistant';

        const ensureAssistantMessage = (nodeKey: string, initialContent = '') => {
          const timestamp = new Date();
          setMessages((prev) => {
            const newMessages = [...prev];
            const existingIndex = nodeMessageIndex.get(nodeKey);

            if (existingIndex === undefined) {
              newMessages.push({
                role: 'assistant',
                content: initialContent,
                timestamp,
                node: nodeKey,
              });
              nodeMessageIndex.set(nodeKey, newMessages.length - 1);
            } else {
              const existing = newMessages[existingIndex];
              if (!existing) {
                newMessages.push({
                  role: 'assistant',
                  content: initialContent,
                  timestamp,
                  node: nodeKey,
                });
                nodeMessageIndex.set(nodeKey, newMessages.length - 1);
              }
            }

            return newMessages;
          });
        };

        const appendToAssistantMessage = (nodeKey: string, fragment: string) => {
          if (!fragment) return;
          const timestamp = new Date();
          setMessages((prev) => {
            const newMessages = [...prev];
            let index = nodeMessageIndex.get(nodeKey);

            if (index === undefined) {
              newMessages.push({
                role: 'assistant',
                content: fragment,
                timestamp,
                node: nodeKey,
              });
              index = newMessages.length - 1;
              nodeMessageIndex.set(nodeKey, index);
            } else {
              const updated = {
                ...newMessages[index],
                content: `${newMessages[index].content || ''}${fragment}`,
                timestamp,
              };
              newMessages[index] = updated;
            }

            return newMessages;
          });
        };

        const replaceAssistantMessage = (nodeKey: string, content: string) => {
          const timestamp = new Date();
          setMessages((prev) => {
            const newMessages = [...prev];
            let index = nodeMessageIndex.get(nodeKey);

            if (index === undefined) {
              newMessages.push({
                role: 'assistant',
                content,
                timestamp,
                node: nodeKey,
              });
              index = newMessages.length - 1;
              nodeMessageIndex.set(nodeKey, index);
            } else {
              const updated = {
                ...newMessages[index],
                content,
                timestamp,
              };
              newMessages[index] = updated;
            }

            return newMessages;
          });
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (!line.startsWith('data: ')) {
              continue;
            }

            try {
              const data = JSON.parse(line.slice(6));
              const nodeKey: string = data.node || defaultNodeKey;

              switch (data.type) {
                case 'start':
                  // ignore
                  break;
                case 'node_start':
                  ensureAssistantMessage(nodeKey, '');
                  break;
                case 'token':
                  appendToAssistantMessage(nodeKey, data.content || '');
                  break;
                case 'message':
                  replaceAssistantMessage(nodeKey, (data.content || '').trim());
                  break;
                case 'error':
                  setError(data.message || '发生未知错误');
                  break;
                case 'done':
                  setIsLoading(false);
                  break;
                default:
                  // 忽略 tool_start / tool_end 等事件
                  break;
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
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
