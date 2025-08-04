// 実装計画書に基づくタイピングインジケータークラス
class TypingIndicator {
  constructor(chatContainer) {
    this.container = chatContainer;
    this.indicator = null;
  }
  
  show() {
    if (this.indicator) return;
    this.indicator = document.createElement('div');
    this.indicator.className = 'typing-indicator';
    this.indicator.innerHTML = `
      <div class="typing-dots">
        <span></span><span></span><span></span>
      </div>
    `;
    this.container.appendChild(this.indicator);
    // 最下部にスクロール
    this.container.scrollTop = this.container.scrollHeight;
  }
  
  hide() {
    if (this.indicator) {
      this.indicator.remove();
      this.indicator = null;
    }
  }
}

// チャットメッセージを追加するユーティリティ
function addMessage(container, text, sender = 'bot', confidence = null, conversationId = null) {
  const messageEl = document.createElement('div');
  messageEl.classList.add('message');
  messageEl.classList.add(sender === 'user' ? 'user' : 'bot');
  messageEl.textContent = text;
  container.appendChild(messageEl);
  container.scrollTop = container.scrollHeight;

  // ボットメッセージかつconversationIdが提供された場合、フィードバックボタンを表示
  if (sender === 'bot' && conversationId) {
    const feedbackContainer = document.createElement('div');
    feedbackContainer.className = 'feedback-container';

    const positiveBtn = document.createElement('button');
    positiveBtn.className = 'feedback-button positive';
    positiveBtn.innerHTML = '👍';
    positiveBtn.title = '役に立った';

    const negativeBtn = document.createElement('button');
    negativeBtn.className = 'feedback-button negative';
    negativeBtn.innerHTML = '👎';
    negativeBtn.title = '役に立たなかった';

    feedbackContainer.appendChild(positiveBtn);
    feedbackContainer.appendChild(negativeBtn);
    messageEl.appendChild(feedbackContainer);

    positiveBtn.addEventListener('click', () => {
      sendFeedback(conversationId, 'positive');
      feedbackContainer.remove();
      // フィードバック送信完了のメッセージを表示
      const thankYouMsg = document.createElement('div');
      thankYouMsg.className = 'feedback-thank-you';
      thankYouMsg.textContent = 'フィードバックありがとうございます！';
      messageEl.appendChild(thankYouMsg);
    });
    
    negativeBtn.addEventListener('click', () => {
      sendFeedback(conversationId, 'negative');
      feedbackContainer.remove();
      // フィードバック送信完了のメッセージを表示
      const thankYouMsg = document.createElement('div');
      thankYouMsg.className = 'feedback-thank-you';
      thankYouMsg.textContent = 'フィードバックありがとうございます！';
      messageEl.appendChild(thankYouMsg);
    });
  }

  // 信頼度スコアが利用可能な場合は表示
  if (confidence !== null && sender === 'bot') {
    const confidenceEl = document.createElement('div');
    confidenceEl.className = 'confidence-score';
    confidenceEl.textContent = `信頼度: ${Math.round(confidence * 100)}%`;
    messageEl.appendChild(confidenceEl);
  }
}

// バックエンドにフィードバックを送信
async function sendFeedback(conversationId, rating) {
  try {
    const response = await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        conversation_id: conversationId, 
        rating: rating 
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTPエラー! ステータス: ${response.status}`);
    }

    console.log('フィードバックの送信に成功しました');
  } catch (err) {
    console.error('フィードバックの送信に失敗しました', err);
    // ユーザーにエラーを通知
    alert('フィードバックの送信に失敗しました。');
  }
}

// エラーメッセージハンドラー
function displayErrorMessage(container, errorData) {
  let errorMessage = 'エラーが発生しました。';
  
  if (errorData && errorData.error) {
    errorMessage = errorData.error;
  }
  
  if (errorData && errorData.fallback_message) {
    errorMessage += '\n' + errorData.fallback_message;
  }
  
  addMessage(container, errorMessage, 'bot');
}

// メインロジック
document.addEventListener('DOMContentLoaded', () => {
  const chatContainer = document.getElementById('chat');
  const inputEl = document.getElementById('user-input');
  const formEl = document.getElementById('chat-form');
  const typingIndicator = new TypingIndicator(chatContainer);

  // ウェルカムメッセージを追加
  addMessage(chatContainer, 'こんにちは！PIP-Makerについてのご質問をお気軽にどうぞ。', 'bot');

  formEl.addEventListener('submit', async (e) => {
    e.preventDefault();
    const question = inputEl.value.trim();
    if (!question) return;

    // ユーザーメッセージを表示
    addMessage(chatContainer, question, 'user');
    inputEl.value = '';
    
    // タイピングインジケーターを表示
    typingIndicator.show();

    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question }),
      });

      typingIndicator.hide();

      if (!response.ok) {
        // HTTPエラーを処理
        const errorData = await response.json().catch(() => null);
        displayErrorMessage(chatContainer, errorData);
        return;
      }

      const data = await response.json();
      
      // 会話の一意ID（タイムスタンプ + ランダム）
      const conversationId = Date.now().toString(36) + Math.random().toString(36).substring(2, 8);
      
      const answer = data.answer || '回答を生成できませんでした。';
      addMessage(chatContainer, answer, 'bot', data.confidence, conversationId);

    } catch (error) {
      typingIndicator.hide();
      console.error('検索リクエストが失敗しました:', error);
      
      // ネットワークエラーやその他の問題
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        addMessage(chatContainer, 'ネットワークエラーが発生しました。インターネット接続を確認してください。', 'bot');
      } else {
        addMessage(chatContainer, 'システムエラーが発生しました。しばらく待ってから再度お試しください。', 'bot');
      }
    }
  });

  // Enterキーサポート
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      formEl.requestSubmit();
    }
  });
});