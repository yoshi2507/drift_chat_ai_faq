// Client-side logic for the Drift-style chat

document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chat-messages');
    const inputContainer = document.getElementById('chat-input-container');

    // Currently selected topic from the quick options. Used to tailor responses.
    let selectedTopic = null;

    /**
     * Append a message from either the bot or the user to the chat area.
     * @param {string} sender "bot" or "user"
     * @param {string} text Message content to display
     */
    function appendMessage(sender, text) {
        const messageEl = document.createElement('div');
        messageEl.classList.add('message', sender);
        const bubble = document.createElement('div');
        bubble.classList.add('bubble');
        bubble.textContent = text;
        messageEl.appendChild(bubble);
        chatMessages.appendChild(messageEl);
        // Scroll to the bottom to show the latest message
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    /**
     * Clear the input container.
     */
    function clearInput() {
        while (inputContainer.firstChild) {
            inputContainer.removeChild(inputContainer.firstChild);
        }
    }

    /**
     * Display quick reply options for the initial question.
     * @param {string[]} options Array of option strings
     */
    function showOptions(options) {
        clearInput();
        const optionsContainer = document.createElement('div');
        optionsContainer.classList.add('quick-options');
        options.forEach(option => {
            const btn = document.createElement('div');
            btn.classList.add('quick-option');
            btn.textContent = option;
            btn.addEventListener('click', () => handleOptionSelected(option));
            optionsContainer.appendChild(btn);
        });
        inputContainer.appendChild(optionsContainer);
    }

    /**
     * Handle user selecting one of the quick options.
     * @param {string} option Selected option text
     */
    function handleOptionSelected(option) {
        // Display the user's selection
        appendMessage('user', option);
        // Store selected topic for later use in AI responses
        selectedTopic = option;
        // Respond based on the selected option
        switch (option) {
            case 'サービス内容について':
                appendMessage('bot', '弊社では動画作成ソフト PIP-Maker を提供しています。AIキャラクターを用いて簡単にナレーション付き動画を作成でき、営業資料や教育コンテンツなど様々な用途でご利用いただけます。');
                break;
            case '料金について':
                appendMessage('bot', '料金プランは複数あり、基本プランとプレミアムプランがございます。具体的な料金体系についてはお問い合わせいただいた後に詳しくご案内いたします。');
                break;
            case '機能比較':
                appendMessage('bot', 'PIP-Makerの主な機能には、AIキャラクターを使ったナレーション生成、動画編集機能、簡単なシナリオ作成があります。競合製品との比較や詳細な機能説明をご希望でしたら、ぜひお問い合わせください。');
                break;
            default:
                appendMessage('bot', 'その他のお問い合わせについて、詳しい内容を教えていただけますでしょうか。');
                break;
        }
        // After giving information, prompt the user for a question before the form
        setTimeout(() => {
            showQuestionInput();
        }, 600);
    }

    /**
     * Display an input for the user to ask a question. This function displays a textarea
     * and two buttons: one to send the question and one to skip directly to the form.
     * When a question is submitted, the bot queries the backend for an answer and
     * displays it. Afterwards, the user is prompted again for additional questions.
     * If the user chooses to skip, the contact form is shown.
     */
    function showQuestionInput() {
        clearInput();
        // Provide instruction from bot
        appendMessage('bot', 'ご質問があればご記入ください。質問がない場合はそのままフォームに進んでください。');
        // Container for textarea and buttons
        const container = document.createElement('div');
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.gap = '8px';
        // Textarea element
        const questionInput = document.createElement('textarea');
        questionInput.placeholder = 'ご質問内容を入力してください';
        questionInput.style.width = '100%';
        questionInput.style.padding = '6px';
        questionInput.style.border = '1px solid #ccc';
        questionInput.style.borderRadius = '4px';
        questionInput.style.fontSize = '14px';
        questionInput.style.minHeight = '60px';
        container.appendChild(questionInput);
        // Container for buttons
        const buttons = document.createElement('div');
        buttons.style.display = 'flex';
        buttons.style.gap = '8px';
        // Send button
        const sendBtn = document.createElement('button');
        sendBtn.textContent = '質問を送信';
        sendBtn.style.flex = '1';
        sendBtn.style.padding = '8px';
        sendBtn.style.backgroundColor = '#007AFF';
        sendBtn.style.color = '#fff';
        sendBtn.style.border = 'none';
        sendBtn.style.borderRadius = '4px';
        sendBtn.style.fontSize = '14px';
        sendBtn.style.cursor = 'pointer';
        sendBtn.addEventListener('click', () => {
            const question = questionInput.value.trim();
            if (!question) {
                // If no question is provided, skip to form
                askForForm();
                return;
            }
            // Append user's question to chat
            appendMessage('user', question);
            // Send question to backend search endpoint with optional category filter
            fetch('/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question: question, category: selectedTopic })
            })
                .then(resp => resp.json())
                .then(result => {
                    if (result && result.found && result.answer) {
                        appendMessage('bot', result.answer);
                    } else {
                        // Fallback: attempt simple keyword-based answer as backup
                        const fallbackAnswer = generateFallbackAnswer(question);
                        appendMessage('bot', fallbackAnswer);
                    }
                    // Prompt for another question or skip
                    setTimeout(() => {
                        showQuestionInput();
                    }, 500);
                })
                .catch(() => {
                    // If server unreachable (e.g., running via file://), fall back to keyword logic
                    const fallbackAnswer = generateFallbackAnswer(question);
                    appendMessage('bot', fallbackAnswer);
                    setTimeout(() => {
                        showQuestionInput();
                    }, 500);
                });
        });
        buttons.appendChild(sendBtn);
        // Skip button
        const skipBtn = document.createElement('button');
        skipBtn.textContent = '質問しないでフォームへ';
        skipBtn.style.flex = '1';
        skipBtn.style.padding = '8px';
        skipBtn.style.backgroundColor = '#e0e0e0';
        skipBtn.style.color = '#333';
        skipBtn.style.border = 'none';
        skipBtn.style.borderRadius = '4px';
        skipBtn.style.fontSize = '14px';
        skipBtn.style.cursor = 'pointer';
        skipBtn.addEventListener('click', () => {
            askForForm();
        });
        buttons.appendChild(skipBtn);
        container.appendChild(buttons);
        inputContainer.appendChild(container);
    }

    /**
     * Fallback answer generator using simple keyword matching. This function is used
     * when the backend search does not return a confident answer or when the
     * application is running without a server (e.g., via file://). It uses the
     * currently selected topic and keywords in the user's question to craft a
     * response.
     * @param {string} question The user's question
     * @returns {string} Generated fallback answer
     */
    function generateFallbackAnswer(question) {
        let answer = '';
        const q = question;
        if (selectedTopic === 'サービス内容について') {
            if (q.includes('キャラクター') || q.includes('キャラ')) {
                answer = 'PIP-Makerでは数十種類のAIキャラクターをご用意しており、用途に応じて人物タイプや声の種類を選択できます。';
            } else if (q.includes('動画') || q.includes('作成')) {
                answer = 'PIP-Makerではシンプルな操作で動画のシナリオ作成から編集まで行うことができます。テンプレートも多数用意しています。';
            } else {
                answer = 'ご質問ありがとうございます。PIP-Makerのサービス内容について詳しくは担当よりご案内いたします。';
            }
        } else if (selectedTopic === '料金について') {
            if (q.includes('値段') || q.includes('料金') || q.includes('価格')) {
                answer = '料金についてはプランにより異なりますが、無料トライアル期間もございます。詳細はお問い合わせ後にご案内いたします。';
            } else if (q.includes('割引') || q.includes('キャンペーン')) {
                answer = '期間限定のキャンペーンや割引プランもございます。最新情報は担当までお問い合わせください。';
            } else {
                answer = '料金に関するご質問ありがとうございます。詳しいお見積りは担当よりご連絡いたします。';
            }
        } else if (selectedTopic === '機能比較') {
            if (q.includes('他社') || q.includes('比較')) {
                answer = '他社製品との比較では、PIP-MakerはAIキャラクターによるナレーション生成や簡単な動画編集機能が強みです。具体的な比較表をご希望であればお問い合わせください。';
            } else if (q.includes('機能')) {
                answer = '主な機能としてAIキャラクター、ナレーション生成、動画編集、テンプレート機能などがあります。詳細資料をご希望でしたらご連絡ください。';
            } else {
                answer = '機能についてのご質問ありがとうございます。詳細は担当よりご案内いたします。';
            }
        } else {
            answer = 'ご質問ありがとうございます。詳細につきましては担当よりご案内いたします。';
        }
        return answer;
    }

    /**
     * Prompt the user to fill in the contact form.
     */
    function askForForm() {
        appendMessage('bot', 'お問い合わせありがとうございます。お手数ですが、以下の情報をご入力ください。');
        showForm();
    }

    /**
     * Display a form for the user to enter contact details.
     */
    function showForm() {
        clearInput();
        const form = document.createElement('form');
        form.id = 'form-container';
        // Create input fields
        const fields = [
            { name: 'name', label: 'お名前', type: 'text' },
            { name: 'email', label: 'メールアドレス', type: 'email' },
            { name: 'phone', label: '電話番号', type: 'tel' },
            { name: 'company', label: '会社名', type: 'text' },
        ];
        fields.forEach(field => {
            const input = document.createElement('input');
            input.name = field.name;
            input.type = field.type;
            input.placeholder = field.label;
            form.appendChild(input);
        });
        // Text area for message
        const textarea = document.createElement('textarea');
        textarea.name = 'message';
        textarea.placeholder = 'お問い合わせ内容';
        form.appendChild(textarea);
        // Submit button
        const submitBtn = document.createElement('button');
        submitBtn.type = 'submit';
        submitBtn.textContent = '送信する';
        form.appendChild(submitBtn);
        // Attach event listener
        form.addEventListener('submit', handleFormSubmit);
        inputContainer.appendChild(form);
    }

    /**
     * Handle form submission by sending data to the server.
     * @param {Event} event Form submit event
     */
    function handleFormSubmit(event) {
        event.preventDefault();
        const form = event.target;
        // Collect form data
        const formData = new FormData(form);
        const data = {};
        formData.forEach((value, key) => {
            data[key] = value.trim();
        });
        // Validate client-side: ensure all fields have values
        const requiredFields = ['name', 'email', 'phone', 'company', 'message'];
        const missing = requiredFields.filter(field => !data[field]);
        if (missing.length > 0) {
            alert('全ての項目を入力してください。');
            return;
        }
        // Disable the form to prevent multiple submissions
        Array.from(form.elements).forEach(el => el.disabled = true);
        // Send data via fetch to the backend
        appendMessage('user', 'フォームを送信しました。');
        fetch('/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
            .then(response => {
                // Attempt to parse JSON response if server is reachable
                return response.json().catch(() => {
                    return { message: null, error: 'Invalid response' };
                });
            })
            .then(res => {
                if (res.error) {
                    // Show generic success if an error occurs (e.g., running locally without backend)
                    appendMessage('bot', 'お問い合わせありがとうございます。担当者よりご連絡いたします。');
                } else if (res.message) {
                    appendMessage('bot', res.message);
                } else {
                    appendMessage('bot', 'お問い合わせありがとうございます。担当者よりご連絡いたします。');
                }
                // Remove the form from input container regardless of result
                clearInput();
            })
            .catch(() => {
                // Network error (e.g., running from file). Provide fallback success message.
                appendMessage('bot', 'お問い合わせありがとうございます。担当者よりご連絡いたします。');
                clearInput();
            });
    }

    // Kick off the conversation
    function startConversation() {
        appendMessage('bot', 'こんにちは！どんなことについて知りたいですか？');
        showOptions(['サービス内容について', '料金について', '機能比較', 'その他']);
    }

    // Initialize chat on page load
    startConversation();
});