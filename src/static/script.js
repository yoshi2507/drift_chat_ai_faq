// Phase 3.1対応版 script.js - 関数順序修正版

// グローバル状態管理（最初に定義）
let currentConversationId = null;
let currentState = 'initial';
let isFormSubmitting = false;

// ユーティリティ関数（最初に定義）
function generateConversationId() {
  return Date.now().toString(36) + Math.random().toString(36).substring(2, 8);
}

// === API通信関数（先に定義） ===

async function selectCategory(categoryId) {
  const typingIndicator = new TypingIndicator(document.getElementById('chat'));
  
  try {
    typingIndicator.show();
    
    const response = await fetch('/api/conversation/category', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        conversation_id: currentConversationId,
        category_id: categoryId 
      }),
    });

    typingIndicator.hide();

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    const chatContainer = document.getElementById('chat');
    
    // カテゴリー選択をユーザーメッセージとして表示
    addMessage(chatContainer, data.category.name, 'user');
    
    // Bot応答のコンテナを作成
    const botContent = document.createElement('div');
    
    // メッセージテキスト
    const messageText = document.createElement('div');
    messageText.textContent = data.message;
    botContent.appendChild(messageText);
    
    // FAQボタンを追加
    if (data.faqs && data.faqs.length > 0) {
      const br1 = document.createElement('br');
      const br2 = document.createElement('br');
      botContent.appendChild(br1);
      botContent.appendChild(br2);
      botContent.appendChild(createFAQButtons(data.faqs));
    }
    
    // アクションボタンを追加
    if (data.show_inquiry_button) {
      botContent.appendChild(createActionButtons(true, false));
    }
    
    addMessage(chatContainer, botContent, 'bot');
    currentState = 'faq_selection';
    
  } catch (error) {
    typingIndicator.hide();
    console.error('Category selection error:', error);
    addMessage(document.getElementById('chat'), 
      'カテゴリー選択でエラーが発生しました。もう一度お試しください。', 'bot');
  }
}

async function selectFAQ(faqId) {
  const typingIndicator = new TypingIndicator(document.getElementById('chat'));
  
  try {
    typingIndicator.show();
    
    const response = await fetch('/api/conversation/faq', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        conversation_id: currentConversationId,
        faq_id: faqId 
      }),
    });

    typingIndicator.hide();

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    const chatContainer = document.getElementById('chat');
    
    addMessage(chatContainer, data.message, 'bot', {
      showFeedback: true,
      conversationId: currentConversationId
    });

    if (data.show_inquiry_button || data.show_more_questions) {
      const actionContainer = document.createElement('div');
      actionContainer.appendChild(createActionButtons(data.show_inquiry_button, data.show_more_questions));
      addMessage(chatContainer, actionContainer, 'bot');
    }
    
  } catch (error) {
    typingIndicator.hide();
    console.error('FAQ selection error:', error);
    addMessage(document.getElementById('chat'), 
      'FAQ取得でエラーが発生しました。もう一度お試しください。', 'bot');
  }
}

async function startInquiryForm() {
  const chatContainer = document.getElementById('chat');
  
  const formContent = document.createElement('div');
  
  const introText = document.createElement('div');
  introText.textContent = 'お問い合わせフォームに移ります。以下の情報をご入力ください。';
  
  const br1 = document.createElement('br');
  const br2 = document.createElement('br');
  
  formContent.appendChild(introText);
  formContent.appendChild(br1);
  formContent.appendChild(br2);
  formContent.appendChild(createInquiryForm());
  
  addMessage(chatContainer, formContent, 'bot');
  currentState = 'inquiry_form';
  
  // フォーム送信を無効化
  document.getElementById('chat-form').style.display = 'none';
}

async function submitInquiry() {
  if (isFormSubmitting) return;
  
  const formData = {
    name: document.getElementById('inquiry-name').value.trim(),
    company: document.getElementById('inquiry-company').value.trim(),
    email: document.getElementById('inquiry-email').value.trim(),
    inquiry: document.getElementById('inquiry-content').value.trim()
  };

  // バリデーション
  const requiredFields = [
    { key: 'name', label: 'お名前' },
    { key: 'company', label: '会社名' },
    { key: 'email', label: 'メールアドレス' },
    { key: 'inquiry', label: 'お問い合わせ内容' }
  ];

  for (const field of requiredFields) {
    if (!formData[field.key]) {
      alert(`${field.label}を入力してください。`);
      return;
    }
  }

  // メールアドレス形式チェック
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(formData.email)) {
    alert('正しいメールアドレスを入力してください。');
    return;
  }

  isFormSubmitting = true;
  const submitButton = document.querySelector('.submit-button');
  const originalText = submitButton.textContent;
  submitButton.textContent = '送信中...';
  submitButton.disabled = true;

  try {
    const response = await fetch('/api/conversation/inquiry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        conversation_id: currentConversationId,
        form_data: formData 
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    const chatContainer = document.getElementById('chat');
    
    // 完了メッセージのDOM要素を作成
    const completionDiv = document.createElement('div');
    completionDiv.style.background = 'linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%)';
    completionDiv.style.border = '1px solid #c3e6cb';
    completionDiv.style.borderRadius = '8px';
    completionDiv.style.color = '#155724';
    completionDiv.style.padding = '16px';
    completionDiv.style.margin = '12px 0';
    
    completionDiv.innerHTML = `
      ✅ ${data.message}
      <br><br>
      <strong>お問い合わせID:</strong> ${data.inquiry_id}<br>
      <strong>回答予定:</strong> ${data.estimated_response_time || '1営業日以内'}
    `;
    
    addMessage(chatContainer, completionDiv, 'bot');
    currentState = 'completed';
    
  } catch (error) {
    console.error('Inquiry submission error:', error);
    alert('お問い合わせの送信でエラーが発生しました。もう一度お試しください。');
    
    submitButton.textContent = originalText;
    submitButton.disabled = false;
    isFormSubmitting = false;
  }
}

function showMoreQuestionOptions() {
  const chatContainer = document.getElementById('chat');
  
  const welcomeDiv = document.createElement('div');
  welcomeDiv.innerHTML = `
    他にご質問はありますか？<br>
    • 直接質問を入力する<br>
    • 最初のカテゴリー選択に戻る<br><br>
  `;
  
  const restartBtn = document.createElement('button');
  restartBtn.className = 'action-button secondary';
  restartBtn.textContent = '🔄 最初からやり直す';
  restartBtn.onclick = restartConversation;
  restartBtn.style.marginTop = '10px';
  
  welcomeDiv.appendChild(restartBtn);
  
  addMessage(chatContainer, welcomeDiv, 'bot');
  
  // 入力フォームを再度有効化
  document.getElementById('chat-form').style.display = 'flex';
}

async function restartConversation() {
  currentConversationId = generateConversationId();
  currentState = 'initial';
  document.getElementById('chat').innerHTML = '';
  document.getElementById('chat-form').style.display = 'flex';
  await initializeChat();
}

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
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    console.log('Feedback sent successfully');
  } catch (err) {
    console.error('Failed to send feedback', err);
  }
}

// === クラス定義 ===

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
    this.container.scrollTop = this.container.scrollHeight;
  }
  
  hide() {
    if (this.indicator) {
      this.indicator.remove();
      this.indicator = null;
    }
  }
}

// === メッセージ表示関数 ===

function addMessage(container, text, sender = 'bot', options = {}) {
  const messageEl = document.createElement('div');
  messageEl.classList.add('message');
  messageEl.classList.add(sender === 'user' ? 'user' : 'bot');

  if (typeof text === 'string') {
    const processedContent = text
       .replace(/\r\n/g, '\n')
       .replace(/\r/g, '\n')
       .replace(/\n/g, '<br>');
    messageEl.innerHTML = processedContent;
  } else {
    if (text instanceof HTMLElement) {
      messageEl.appendChild(text);
    } else {
      messageEl.appendChild(text);
    }
  }

  container.appendChild(messageEl);
  container.scrollTop = container.scrollHeight;

  // 信頼度スコア表示
  if (sender === 'bot' && options.confidence !== undefined) {
    const confidenceEl = document.createElement('div');
    confidenceEl.style.fontSize = '11px';
    confidenceEl.style.color = '#6c757d';
    confidenceEl.style.marginTop = '6px';
    confidenceEl.style.fontStyle = 'italic';
    confidenceEl.textContent = `信頼度: ${Math.round(options.confidence * 100)}%`;
    messageEl.appendChild(confidenceEl);
  }

  // Phase 3.1: 引用情報を表示
  if (sender === 'bot' && options.citations && options.citations.citations && options.citations.citations.length > 0) {
    const citationsEl = createCitationsDisplay(options.citations);
    messageEl.appendChild(citationsEl);
  }

  // フィードバックボタン追加
  if (sender === 'bot' && options.showFeedback && options.conversationId) {
    addFeedbackButtons(messageEl, options.conversationId);
  }

  return messageEl;
}

// Phase 3.1: 引用情報表示の作成
function createCitationsDisplay(citations) {
  const citationsContainer = document.createElement('div');
  citationsContainer.className = 'citations-container';
  citationsContainer.style.cssText = `
    margin-top: 12px;
    padding: 12px;
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    border-radius: 8px;
    border-left: 3px solid #007bff;
  `;

  const citationsHeader = document.createElement('div');
  citationsHeader.style.cssText = `
    font-size: 12px;
    font-weight: 600;
    color: #495057;
    margin-bottom: 8px;
  `;
  citationsHeader.textContent = `📚 参考情報 (${citations.showing}/${citations.total_sources}件)`;
  citationsContainer.appendChild(citationsHeader);

  citations.citations.forEach((citation, index) => {
    const citationEl = document.createElement('div');
    citationEl.className = 'citation-item';
    citationEl.style.cssText = `
      margin: 6px 0;
      padding: 8px;
      background: white;
      border-radius: 4px;
      border: 1px solid #dee2e6;
      font-size: 12px;
    `;

    const titleEl = document.createElement('div');
    titleEl.style.cssText = `
      font-weight: 600;
      color: #007bff;
      margin-bottom: 4px;
      display: flex;
      align-items: center;
      gap: 4px;
    `;
    
    if (citation.url) {
      const linkEl = document.createElement('a');
      linkEl.href = citation.url;
      linkEl.target = '_blank';
      linkEl.rel = 'noopener noreferrer';
      linkEl.style.cssText = `
        text-decoration: none;
        color: inherit;
        display: flex;
        align-items: center;
        gap: 4px;
      `;
      linkEl.innerHTML = `${citation.icon} ${citation.title}`;
      titleEl.appendChild(linkEl);
    } else {
      titleEl.innerHTML = `${citation.icon} ${citation.title}`;
    }

    citationEl.appendChild(titleEl);

    const typeEl = document.createElement('div');
    typeEl.style.cssText = `
      font-size: 10px;
      color: #6c757d;
      margin-bottom: 4px;
    `;
    typeEl.textContent = `${citation.type_label} | 信頼度: ${Math.round(citation.confidence * 100)}%`;
    if (citation.verified) {
      typeEl.innerHTML += ' <span style="color: #28a745;">✓ 確認済み</span>';
    }
    citationEl.appendChild(typeEl);

    if (citation.excerpt) {
      const excerptEl = document.createElement('div');
      excerptEl.style.cssText = `
        font-size: 11px;
        color: #495057;
        line-height: 1.4;
        padding: 4px 8px;
        background: #f8f9fa;
        border-radius: 3px;
        margin-top: 4px;
      `;
      excerptEl.textContent = citation.excerpt.length > 100 
        ? citation.excerpt.substring(0, 100) + '...'
        : citation.excerpt;
      citationEl.appendChild(excerptEl);
    }

    citationsContainer.appendChild(citationEl);
  });

  if (citations.has_more) {
    const moreEl = document.createElement('div');
    moreEl.style.cssText = `
      font-size: 11px;
      color: #6c757d;
      text-align: center;
      margin-top: 8px;
      font-style: italic;
    `;
    moreEl.textContent = `他にも${citations.total_sources - citations.showing}件の参考情報があります`;
    citationsContainer.appendChild(moreEl);
  }

  return citationsContainer;
}

function addFeedbackButtons(messageEl, conversationId) {
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
    showFeedbackThankYou(messageEl, feedbackContainer);
  });
  
  negativeBtn.addEventListener('click', () => {
    sendFeedback(conversationId, 'negative');
    showFeedbackThankYou(messageEl, feedbackContainer);
  });
}

function showFeedbackThankYou(messageEl, feedbackContainer) {
  feedbackContainer.remove();
  const thankYouMsg = document.createElement('div');
  thankYouMsg.style.fontSize = '11px';
  thankYouMsg.style.color = '#28a745';
  thankYouMsg.style.marginTop = '6px';
  thankYouMsg.style.fontStyle = 'italic';
  thankYouMsg.textContent = '💚 フィードバックありがとうございます！';
  messageEl.appendChild(thankYouMsg);
}

// === UI要素作成関数 ===

function createCategoryButtons(categories) {
  const container = document.createElement('div');
  container.className = 'category-buttons';
  
  categories.forEach((category, index) => {
    const button = document.createElement('button');
    button.className = 'category-button';
    
    const strong = document.createElement('strong');
    strong.textContent = category.name;
    
    const br = document.createElement('br');
    
    const small = document.createElement('small');
    small.textContent = category.description;
    
    button.appendChild(strong);
    button.appendChild(br);
    button.appendChild(small);
    
    button.style.animationDelay = `${index * 0.1}s`;
    // 🔧 イベントリスナーを使用（onclickの代わり）
    button.addEventListener('click', () => selectCategory(category.id.replace(/[^a-zA-Z0-9]/g, '')));
    container.appendChild(button);
  });
  
  return container;
}

function createFAQButtons(faqs) {
  if (!faqs || faqs.length === 0) {
    const emptyEl = document.createElement('p');
    const em = document.createElement('em');
    em.textContent = 'このカテゴリーのFAQは現在準備中です。';
    emptyEl.appendChild(em);
    return emptyEl;
  }

  const container = document.createElement('div');
  container.className = 'faq-buttons';
  
  faqs.forEach((faq, index) => {
    const button = document.createElement('button');
    button.className = 'faq-button';
    button.textContent = `Q: ${faq.question}`;
    button.style.animationDelay = `${index * 0.1}s`;
    // 🔧 イベントリスナーを使用
    button.addEventListener('click', () => selectFAQ(faq.id));
    container.appendChild(button);
  });
  
  return container;
}

function createActionButtons(showInquiry = false, showMoreQuestions = false) {
  const container = document.createElement('div');
  container.className = 'action-buttons';
  
  if (showInquiry) {
    const inquiryBtn = document.createElement('button');
    inquiryBtn.className = 'action-button';
    inquiryBtn.textContent = '📝 お問い合わせする';
    inquiryBtn.addEventListener('click', startInquiryForm);
    container.appendChild(inquiryBtn);
  }
  
  if (showMoreQuestions) {
    const moreBtn = document.createElement('button');
    moreBtn.className = 'action-button secondary';
    moreBtn.textContent = '❓ 他の質問をする';
    moreBtn.addEventListener('click', showMoreQuestionOptions);
    container.appendChild(moreBtn);
  }
  
  return container;
}

function createInquiryForm() {
  const form = document.createElement('div');
  form.className = 'inquiry-form';
  
  // お名前
  const nameGroup = document.createElement('div');
  nameGroup.className = 'form-group';
  const nameLabel = document.createElement('label');
  nameLabel.setAttribute('for', 'inquiry-name');
  nameLabel.innerHTML = 'お名前 <span style="color: red;">*</span>';
  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.id = 'inquiry-name';
  nameInput.required = true;
  nameInput.placeholder = '山田 太郎';
  nameGroup.appendChild(nameLabel);
  nameGroup.appendChild(nameInput);
  
  // 会社名
  const companyGroup = document.createElement('div');
  companyGroup.className = 'form-group';
  const companyLabel = document.createElement('label');
  companyLabel.setAttribute('for', 'inquiry-company');
  companyLabel.innerHTML = '会社名 <span style="color: red;">*</span>';
  const companyInput = document.createElement('input');
  companyInput.type = 'text';
  companyInput.id = 'inquiry-company';
  companyInput.required = true;
  companyInput.placeholder = '株式会社サンプル';
  companyGroup.appendChild(companyLabel);
  companyGroup.appendChild(companyInput);
  
  // メールアドレス
  const emailGroup = document.createElement('div');
  emailGroup.className = 'form-group';
  const emailLabel = document.createElement('label');
  emailLabel.setAttribute('for', 'inquiry-email');
  emailLabel.innerHTML = 'メールアドレス <span style="color: red;">*</span>';
  const emailInput = document.createElement('input');
  emailInput.type = 'email';
  emailInput.id = 'inquiry-email';
  emailInput.required = true;
  emailInput.placeholder = 'example@company.com';
  emailGroup.appendChild(emailLabel);
  emailGroup.appendChild(emailInput);
  
  // お問い合わせ内容
  const contentGroup = document.createElement('div');
  contentGroup.className = 'form-group';
  const contentLabel = document.createElement('label');
  contentLabel.setAttribute('for', 'inquiry-content');
  contentLabel.innerHTML = 'お問い合わせ内容 <span style="color: red;">*</span>';
  const contentTextarea = document.createElement('textarea');
  contentTextarea.id = 'inquiry-content';
  contentTextarea.required = true;
  contentTextarea.placeholder = 'PIP-Makerについてお聞きしたいことをご記入ください';
  contentGroup.appendChild(contentLabel);
  contentGroup.appendChild(contentTextarea);
  
  // 送信ボタン
  const submitBtn = document.createElement('button');
  submitBtn.type = 'button';
  submitBtn.className = 'submit-button';
  submitBtn.textContent = '📤 送信する';
  submitBtn.addEventListener('click', submitInquiry);
  
  form.appendChild(nameGroup);
  form.appendChild(companyGroup);
  form.appendChild(emailGroup);
  form.appendChild(contentGroup);
  form.appendChild(submitBtn);
  
  return form;
}

// === 初期化関数 ===

async function initializeChat() {
  const typingIndicator = new TypingIndicator(document.getElementById('chat'));
  
  try {
    typingIndicator.show();
    
    const response = await fetch('/api/conversation/welcome');
    const data = await response.json();
    
    typingIndicator.hide();
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const welcomeContent = document.createElement('div');
    
    const messageText = document.createElement('div');
    messageText.textContent = data.message;
    welcomeContent.appendChild(messageText);
    
    if (data.categories) {
      const br1 = document.createElement('br');
      const br2 = document.createElement('br');
      welcomeContent.appendChild(br1);
      welcomeContent.appendChild(br2);
      welcomeContent.appendChild(createCategoryButtons(data.categories));
    }
    
    addMessage(document.getElementById('chat'), welcomeContent, 'bot');
    currentState = 'category_selection';
    
  } catch (error) {
    typingIndicator.hide();
    console.error('Welcome message error:', error);
    addMessage(document.getElementById('chat'), 
      'こんにちは！PIP-Makerについてお聞かせください。', 'bot');
  }
}

// === DOMContentLoaded イベントリスナー ===

document.addEventListener('DOMContentLoaded', async () => {
  currentConversationId = generateConversationId();
  await initializeChat();

  const formEl = document.getElementById('chat-form');
  const inputEl = document.getElementById('user-input');
  const typingIndicator = new TypingIndicator(document.getElementById('chat'));
  
  formEl.addEventListener('submit', async (e) => {
    e.preventDefault();
    const question = inputEl.value.trim();
    if (!question) return;

    const chatContainer = document.getElementById('chat');
    addMessage(chatContainer, question, 'user');
    inputEl.value = '';
    
    typingIndicator.show();

    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          question: question,
          conversation_id: currentConversationId
        }),
      });

      typingIndicator.hide();

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        if (errorData && errorData.error) {
          addMessage(chatContainer, errorData.error, 'bot');
        } else {
          addMessage(chatContainer, 'エラーが発生しました。もう一度お試しください。', 'bot');
        }
        return;
      }

      const data = await response.json();
      
      // Phase 3.1: 引用情報付きでメッセージを表示
      addMessage(chatContainer, data.answer, 'bot', {
        confidence: data.confidence,
        citations: data.citations,
        showFeedback: true,
        conversationId: currentConversationId
      });
      
      // アクションボタンを別途追加
      const actionContainer = document.createElement('div');
      actionContainer.appendChild(createActionButtons(true, true));
      addMessage(chatContainer, actionContainer, 'bot');
      
    } catch (error) {
      typingIndicator.hide();
      console.error('Search request failed:', error);
      addMessage(chatContainer, 'ネットワークエラーが発生しました。接続を確認してください。', 'bot');
    }
  });

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      formEl.requestSubmit();
    }
  });
});