import { useState, useCallback, useEffect } from 'react';
import { Message, ImageData, HITLInterruptData, HITLState } from '../types/message';

const API_BASE_URL = 'http://localhost:8000';
const USER_ID = 'user_001';  // 固定用户ID（未来从登录系统获取）

// ⚠️ 移除自动恢复对话的逻辑
// 现在每次打开应用都是新对话（conversationId 初始为 null）

// 合并连续的AI消息
const mergeConsecutiveAIMessages = (messages: Message[]): Message[] => {
  const merged: Message[] = [];

  for (const msg of messages) {
    const lastMsg = merged[merged.length - 1];

    // 如果当前消息和上一条消息都是assistant，且内容都存在，则合并
    if (
      lastMsg &&
      lastMsg.role === 'assistant' &&
      msg.role === 'assistant' &&
      lastMsg.content &&
      msg.content
    ) {
      // 合并内容，用两个换行分隔
      lastMsg.content = lastMsg.content + '\n\n' + msg.content;
      // 更新时间戳为最新的
      lastMsg.timestamp = msg.timestamp;
      // 保留第一条消息的metrics（首字延迟等）
    } else {
      // 不能合并，添加为新消息
      merged.push({...msg});
    }
  }

  return merged;
};

 export const useChatStream = () => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // HITL 状态
    const [hitlState, setHitlState] = useState<HITLState>({
      isWaiting: false,
      interruptData: null,
    });

    // ⚠️ conversationId 初始为 null（不自动恢复）
    const [conversationId, setConversationId] = useState<string | null>(null);

    // ⚠️ 启动时检查 profile 状态，显示引导消息
    useEffect(() => {
      const checkProfileAndGreet = async () => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/memory/check-profile?user_id=${USER_ID}`);
          if (!response.ok) {
            console.error('Failed to check profile status');
            return;
          }

          const data = await response.json();

          if (!data.is_initialized && data.greeting) {
            // Profile 未初始化，显示引导消息
            setMessages([{
              role: 'assistant',
              content: data.greeting,
              timestamp: new Date(),
            }]);
          } else {
            // Profile 已初始化，显示空白页
            setMessages([]);
          }
        } catch (error) {
          console.error('Failed to check profile:', error);
          // 出错时显示空白页
          setMessages([]);
        }
      };

      // 只在初始化时执行一次
      checkProfileAndGreet();
    }, []);  // 空依赖数组，只执行一次

    // 从后端加载历史消息
    const loadMessagesFromBackend = useCallback(async (convId: string) => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/conversations/${convId}/messages`);
        if (response.ok) {
          const backendMessages = await response.json();
          // 转换为前端Message格式
          const formattedMessages = backendMessages.map((msg: any) => ({
            role: msg.role,
            content: msg.content,
            timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
          }));
          setMessages(formattedMessages);
          // 同时保存到localStorage
          localStorage.setItem(`chat_messages_${convId}`, JSON.stringify(formattedMessages));
        }
      } catch (e) {
        console.error('Failed to load messages from backend:', e);
      }
    }, []);

    // ⚠️ 移除 localStorage 自动加载逻辑
    // 只在切换对话时加载历史消息
    useEffect(() => {
      if (!conversationId) {
        // 没有conversationId，清空消息（空白页）
        setMessages([]);
        return;
      }

      // 有conversationId，尝试从localStorage加载
      const storedMessages = localStorage.getItem(`chat_messages_${conversationId}`);
      if (storedMessages) {
        try {
          const parsed = JSON.parse(storedMessages);
          const messagesWithDates = parsed.map((msg: any) => ({
            ...msg,
            timestamp: new Date(msg.timestamp)
          }));
          setMessages(messagesWithDates);
        } catch (e) {
          console.error('Failed to load messages from localStorage:', e);
        }
      }
      // ⚠️ 删除了 else 分支的 setMessages([])
      // 如果 localStorage 没有缓存，保持当前消息状态（避免清空刚添加的消息）
    }, [conversationId]);

    // 保存消息到 localStorage
    useEffect(() => {
      if (messages.length > 0) {
        localStorage.setItem(`chat_messages_${conversationId}`, JSON.stringify(messages));
      }
    }, [messages, conversationId]);

    const sendMessage = useCallback(async (userMessage: string, images?: ImageData[], onMessageSent?: () => void) => {
      // ⚠️ 如果没有 conversationId，先创建一个
      let currentConversationId = conversationId;
      if (!currentConversationId) {
        const timestamp = Date.now();
        const random = Math.random().toString(36).substring(2, 11);
        currentConversationId = `conv_${timestamp}_${random}`;
        setConversationId(currentConversationId);
        localStorage.setItem('current_conversation_id', currentConversationId);
      }

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

      // 性能指标追踪
      const startTime = performance.now();
      let firstTokenTime: number | undefined = undefined;
      let hasReceivedFirstToken = false;

      try {
        const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: userMessage,
            user_id: USER_ID,  // 固定用户ID
            conversation_id: currentConversationId,  // ⚠️ 使用新创建的 ID
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
        let lastActiveNodeKey = defaultNodeKey;  // 追踪最后活跃的节点
        let isFilteringMemoryBlock = false;  // ⚠️ 状态：是否正在过滤记忆标记块

        const ensureAssistantMessage = (nodeKey: string, initialContent = '') => {
          lastActiveNodeKey = nodeKey;  // 更新最后活跃节点
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
                metrics: {
                  startTime,  // 记录开始时间
                },
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
                  metrics: {
                    startTime,
                  },
                });
                nodeMessageIndex.set(nodeKey, newMessages.length - 1);
              }
            }

            return newMessages;
          });
        };

        const appendToAssistantMessage = (nodeKey: string, fragment: string) => {
          if (!fragment) return;

          lastActiveNodeKey = nodeKey;  // 更新最后活跃节点

          // ⚠️ 过滤记忆检测标记（不显示给用户）
          // 检测标记开始
          if (fragment.includes('__DETECTED_MEMORIES__')) {
            isFilteringMemoryBlock = true;
            // 只添加标记之前的内容
            const beforeMarker = fragment.split('__DETECTED_MEMORIES__')[0];
            if (beforeMarker.trim()) {
              fragment = beforeMarker;
            } else {
              return;  // 如果标记之前没有内容，跳过
            }
          }

          // 检测标记结束
          if (fragment.includes('__END_DETECTED_MEMORIES__')) {
            isFilteringMemoryBlock = false;
            return;  // 跳过结束标记
          }

          // 如果正在过滤中，跳过所有内容
          if (isFilteringMemoryBlock) {
            return;
          }

          // 记录首字延迟
          if (!hasReceivedFirstToken) {
            firstTokenTime = performance.now();
            hasReceivedFirstToken = true;
          }

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
                metrics: {
                  startTime,
                  firstTokenLatency: firstTokenTime ? firstTokenTime - startTime : undefined,
                },
              });
              index = newMessages.length - 1;
              nodeMessageIndex.set(nodeKey, index);
            } else {
              const updated = {
                ...newMessages[index],
                content: `${newMessages[index].content || ''}${fragment}`,
                timestamp,
                metrics: {
                  startTime,
                  firstTokenLatency: firstTokenTime ? firstTokenTime - startTime : undefined,
                },
              };
              newMessages[index] = updated;
            }

            return newMessages;
          });
        };

        const replaceAssistantMessage = (nodeKey: string, content: string) => {
          lastActiveNodeKey = nodeKey;  // 更新最后活跃节点

          // ⚠️ 过滤标记
          let cleanContent = content;
          if (cleanContent.includes('__DETECTED_MEMORIES__')) {
            const beforeMarker = cleanContent.split('__DETECTED_MEMORIES__')[0];
            cleanContent = beforeMarker.trim();
          }

          const timestamp = new Date();
          setMessages((prev) => {
            const newMessages = [...prev];
            let index = nodeMessageIndex.get(nodeKey);

            if (index === undefined) {
              newMessages.push({
                role: 'assistant',
                content: cleanContent,
                timestamp,
                node: nodeKey,
                metrics: {
                  startTime,
                  firstTokenLatency: firstTokenTime ? firstTokenTime - startTime : undefined,
                },
              });
              index = newMessages.length - 1;
              nodeMessageIndex.set(nodeKey, index);
            } else {
              const updated = {
                ...newMessages[index],
                content: cleanContent,
                timestamp,
                metrics: {
                  startTime,
                  firstTokenLatency: firstTokenTime ? firstTokenTime - startTime : undefined,
                },
              };
              newMessages[index] = updated;
            }

            return newMessages;
          });
        };

        const updateMetrics = (nodeKey: string) => {
          const endTime = performance.now();
          setMessages((prev) => {
            const newMessages = [...prev];
            const index = nodeMessageIndex.get(nodeKey);

            if (index !== undefined && newMessages[index]) {
              // 只更新有实际内容的消息
              if (newMessages[index].content && newMessages[index].content.trim()) {
                newMessages[index] = {
                  ...newMessages[index],
                  metrics: {
                    ...newMessages[index].metrics,
                    startTime,
                    firstTokenLatency: firstTokenTime ? firstTokenTime - startTime : undefined,
                    totalLatency: endTime - startTime,
                  },
                };
              } else {
                // 移除空消息
                newMessages.splice(index, 1);
                nodeMessageIndex.delete(nodeKey);
              }
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
                case 'interrupt':
                  // HITL 中断：设置等待状态
                  console.log('[HITL] Received interrupt:', data.data);
                  setHitlState({
                    isWaiting: true,
                    interruptData: data.data as HITLInterruptData,
                  });
                  // ⚠️ 不需要添加消息，HITLDialog会显示确认界面
                  setIsLoading(false);
                  break;
                case 'waiting_input':
                  // 等待用户输入
                  console.log('[HITL] Waiting for user input:', data.message);
                  setIsLoading(false);
                  break;
                case 'done':
                  // 更新性能指标（使用最后活跃的节点或当前节点）
                  const targetNodeKey = data.node || lastActiveNodeKey;
                  updateMetrics(targetNodeKey);
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

        // 流式输出结束后，清理assistant的空消息（保留用户消息）
        setMessages((prev) => {
          // 1. 先过滤空消息
          const filtered = prev.filter(msg =>
            msg.role === 'user' || (msg.content && msg.content.trim())
          );
          // 2. 合并连续的AI消息
          return mergeConsecutiveAIMessages(filtered);
        });

        setIsLoading(false);

        // 发送消息完成后，通知父组件刷新对话列表
        if (onMessageSent) {
          onMessageSent();
        }
      } catch (err) {
        console.error('Stream error:', err);
        setError(err instanceof Error ? err.message : '发生未知错误');
        setIsLoading(false);
      }
    }, [conversationId]);  // 添加 conversationId 依赖

    const clearMessages = useCallback(() => {
      setMessages([]);
      setError(null);
    }, []);

    const startNewChat = useCallback(() => {
      // 创建新的 conversation ID
      const timestamp = Date.now();
      const random = Math.random().toString(36).substring(2, 11);
      const newId = `conv_${timestamp}_${random}`;
      localStorage.setItem('current_conversation_id', newId);
      setConversationId(newId);

      // 清空当前消息
      setMessages([]);
      setError(null);

      // 清除旧的消息记录
      localStorage.removeItem(`chat_messages_${conversationId}`);
    }, [conversationId]);

    // 切换对话
    const switchConversation = useCallback(async (newConversationId: string) => {
      // 更新当前conversation ID
      localStorage.setItem('current_conversation_id', newConversationId);
      setConversationId(newConversationId);

      // 清空当前消息
      setMessages([]);
      setError(null);

      // 清除 HITL 状态
      setHitlState({ isWaiting: false, interruptData: null });

      // 显式从后端加载历史消息（不依赖 useEffect）
      await loadMessagesFromBackend(newConversationId);
    }, [loadMessagesFromBackend]);

    // HITL: 恢复中断的对话
    const resumeWithResponse = useCallback(async (response: any) => {
      console.log('[HITL] Resuming with response:', response);
      setIsLoading(true);
      setHitlState({ isWaiting: false, interruptData: null });

      try {
        const apiResponse = await fetch(`${API_BASE_URL}/api/chat/resume`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            conversation_id: conversationId,
            user_id: USER_ID,
            resume_value: response,
          }),
        });

        if (!apiResponse.ok) {
          throw new Error(`HTTP error! status: ${apiResponse.status}`);
        }

        const reader = apiResponse.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error('Response body is null');
        }

        // ⚠️ 状态：是否正在过滤记忆标记块
        let isFilteringMemoryBlock = false;

        // 处理 resume 的流式响应
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;

            try {
              const data = JSON.parse(line.slice(6));

              switch (data.type) {
                case 'resume_start':
                  console.log('[HITL] Resume started');
                  break;
                case 'token':
                  // ⚠️ 过滤记忆标记
                  let token = data.content || '';

                  // 检测标记开始
                  if (token.includes('__DETECTED_MEMORIES__')) {
                    isFilteringMemoryBlock = true;
                    const beforeMarker = token.split('__DETECTED_MEMORIES__')[0];
                    token = beforeMarker;
                  }

                  // 检测标记结束
                  if (token.includes('__END_DETECTED_MEMORIES__')) {
                    isFilteringMemoryBlock = false;
                    break;  // 跳过这个 token
                  }

                  // 如果正在过滤中，跳过
                  if (isFilteringMemoryBlock || !token) {
                    break;
                  }

                  // 追加 token 到最后一条 assistant 消息
                  setMessages((prev) => {
                    const newMessages = [...prev];
                    const lastIdx = newMessages.length - 1;
                    if (lastIdx >= 0 && newMessages[lastIdx].role === 'assistant') {
                      newMessages[lastIdx] = {
                        ...newMessages[lastIdx],
                        content: (newMessages[lastIdx].content || '') + token,
                      };
                    } else {
                      newMessages.push({
                        role: 'assistant',
                        content: token,
                        timestamp: new Date(),
                      });
                    }
                    return newMessages;
                  });
                  break;
                case 'message':
                  // ⚠️ 过滤完整消息中的标记
                  let messageContent = data.content || '';
                  const messageNode = data.node || 'assistant';

                  // 如果包含标记，移除标记部分
                  if (messageContent.includes('__DETECTED_MEMORIES__')) {
                    const beforeMarker = messageContent.split('__DETECTED_MEMORIES__')[0];
                    messageContent = beforeMarker.trim();
                  }

                  if (messageContent) {
                    // ⚠️ 修复：替换相同节点的最后一条 assistant 消息，避免重复
                    setMessages((prev) => {
                      const newMessages = [...prev];
                      const lastIdx = newMessages.length - 1;

                      // 如果最后一条消息是来自同一节点的 assistant，则替换它
                      if (lastIdx >= 0 &&
                          newMessages[lastIdx].role === 'assistant' &&
                          newMessages[lastIdx].node === messageNode) {
                        newMessages[lastIdx] = {
                          ...newMessages[lastIdx],
                          content: messageContent,
                          timestamp: new Date(),
                        };
                      } else {
                        // 否则追加新消息
                        newMessages.push({
                          role: 'assistant',
                          content: messageContent,
                          timestamp: new Date(),
                          node: messageNode,
                        });
                      }
                      return newMessages;
                    });
                  }
                  break;
                case 'interrupt':
                  // 再次触发 HITL
                  console.log('[HITL] Another interrupt:', data.data);
                  setHitlState({
                    isWaiting: true,
                    interruptData: data.data as HITLInterruptData,
                  });
                  // ⚠️ 不需要添加消息，HITLDialog会显示确认界面
                  setIsLoading(false);
                  return;  // 停止处理，等待用户响应
                case 'error':
                  setError(data.message || '发生错误');
                  break;
                case 'done':
                  console.log('[HITL] Resume completed');
                  break;
              }
            } catch (e) {
              console.error('Failed to parse resume SSE data:', e);
            }
          }
        }

        // 清理空消息并合并
        setMessages((prev) => {
          const filtered = prev.filter(msg =>
            msg.role === 'user' || (msg.content && msg.content.trim())
          );
          return mergeConsecutiveAIMessages(filtered);
        });

        setIsLoading(false);
      } catch (err) {
        console.error('[HITL] Resume error:', err);
        setError(err instanceof Error ? err.message : '恢复执行失败');
        setIsLoading(false);
      }
    }, [conversationId]);

    // HITL: 取消中断
    const cancelHITL = useCallback(() => {
      console.log('[HITL] Cancelled by user');
      setHitlState({ isWaiting: false, interruptData: null });
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: '操作已取消。',
        timestamp: new Date(),
      }]);
    }, []);

    return {
      messages,
      isLoading,
      error,
      sendMessage,
      clearMessages,
      startNewChat,
      switchConversation,
      conversationId,
      // HITL
      hitlState,
      resumeWithResponse,
      cancelHITL,
    };
  };
