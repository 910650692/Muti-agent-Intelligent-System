import React, { useCallback } from 'react';
import { ChatInterface } from './components/ChatInterface';
import { ConversationList } from './components/ConversationList';
import { useChatStream } from './hooks/useChatStream';
import { useConversations } from './hooks/useConversations';
import { ImageData } from './types/message';
import './App.css';

function App() {
  // 对话管理
  const {
    conversations,
    isLoading: conversationsLoading,
    error: conversationsError,
    loadConversations,
    createConversation,
    deleteConversation,
    updateConversationTitle,
  } = useConversations();

  // 聊天流
  const {
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
  } = useChatStream();

  // 新建对话
  const handleNewConversation = useCallback(() => {
    startNewChat();
    // 注意：对话记录会在第一次发送消息时自动创建
  }, [startNewChat]);

  // 选择对话
  const handleSelectConversation = useCallback(async (convId: string) => {
    await switchConversation(convId);
  }, [switchConversation]);

  // 删除对话
  const handleDeleteConversation = useCallback(async (convId: string) => {
    const success = await deleteConversation(convId);
    if (success && convId === conversationId) {
      // 如果删除的是当前对话，创建新对话
      startNewChat();
    }
  }, [deleteConversation, conversationId, startNewChat]);

  // 包装 sendMessage，在消息发送后刷新对话列表
  const handleSendMessage = useCallback(async (message: string, images?: ImageData[]) => {
    await sendMessage(message, images, () => {
      // 消息发送完成后，刷新对话列表
      loadConversations();
    });
  }, [sendMessage, loadConversations]);

  // 调试日志
  console.log('App渲染:', {
    conversations: conversations.length,
    conversationId,
    messagesCount: messages.length
  });

  return (
    <div className="App">
      <div className="app-container">
        <ConversationList
          conversations={conversations}
          currentConversationId={conversationId}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          onNewConversation={handleNewConversation}
        />
        <ChatInterface
          messages={messages}
          isLoading={isLoading}
          error={error}
          sendMessage={handleSendMessage}
          clearMessages={clearMessages}
          startNewChat={handleNewConversation}
          hitlState={hitlState}
          onHITLResponse={resumeWithResponse}
          onHITLCancel={cancelHITL}
        />
      </div>
    </div>
  );
}

export default App;
