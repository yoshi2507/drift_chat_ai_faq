# src/app.py - 対話フロー対応版

"""
PIP-Maker チャットボット Phase 1.5.1 - 対話フロー対応版
"""

import csv
import logging
import uuid
import os
import sys
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# 🔧 設定とサービスインポート（修正版）
try:
    from .config import get_settings, create_data_service
    from .conversation_flow import ConversationFlowService, ConversationState, ConversationContext
    settings = get_settings()
    LOGGER.info("✅ 正常なインポート完了")
    
    # データサービスを作成
    data_service = create_data_service()
    LOGGER.info(f"データサービス初期化完了: {type(data_service).__name__}")
    
except ImportError as e:
    LOGGER.error(f"❌ インポートエラー: {e}")
    print(f"❌ ConversationFlow import error: {e}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    
    # フォールバック設定（緊急用）
    class FallbackSettings:
        csv_file_path = "src/qa_data.csv"
        app_name = "PIP‑Maker Chat API"
        app_version = "1.5.1"
        search_similarity_threshold = 0.1
        slack_webhook_url = None
        debug = False
        google_sheets_enabled = False
        is_google_sheets_configured = False
        
        def get_data_source_config(self):
            return {'google_sheets_enabled': False, 'csv_fallback': self.csv_file_path}
    
    settings = FallbackSettings()
    
    # フォールバック データサービス
    try:
        sys.path.append(os.path.dirname(__file__))
        from enhanced_sheet_service import EnhancedGoogleSheetsService
        data_service = EnhancedGoogleSheetsService(settings.csv_file_path)
        LOGGER.info("✅ フォールバック データサービス初期化完了")
    except Exception as import_error:
        LOGGER.error(f"⚠️ フォールバック データサービス初期化失敗: {import_error}")
        data_service = None
    
    # フォールバック ConversationFlowService クラス
    class FallbackConversationFlowService:
        def __init__(self, sheet_service):
            self.sheet_service = sheet_service
            self.contexts = {}
            
        async def get_welcome_message(self):
            return {
                "message": "こんにちは！PIP-Maker HPにお越しいただきありがとうございます。\n興味があることを以下から選んでください。",
                "type": "category_selection",
                "categories": [
                    {
                        "id": "about", 
                        "name": "💡 PIP-Makerとは？",
                        "description": "PIP-Makerの基本的な概要と特徴について説明します。"
                    },
                    {
                        "id": "cases", 
                        "name": "📈 PIP-Makerの導入事例",
                        "description": "実際の導入事例と成功例をご紹介します。"
                    },
                    {
                        "id": "features", 
                        "name": "⚙️ PIP-Makerの機能",
                        "description": "PIP-Makerの主要機能と使い方について説明します。"
                    },
                    {
                        "id": "pricing", 
                        "name": "💰 PIP-Makerの料金プラン / ライセンスルール",
                        "description": "料金体系とライセンス情報についてご案内します。"
                    },
                    {
                        "id": "other", 
                        "name": "❓ その他",
                        "description": "上記以外のご質問やご相談についてお答えします。"
                    }
                ]
            }
            
        async def select_category(self, conversation_id, category_id):
            category_names = {
                "about": "PIP-Makerとは？",
                "cases": "PIP-Makerの導入事例", 
                "features": "PIP-Makerの機能",
                "pricing": "PIP-Makerの料金プラン / ライセンスルール",
                "other": "その他"
            }
            
            category_name = category_names.get(category_id, "選択されたカテゴリー")
            
            # 簡単なFAQリストを返す
            faqs = []
            if self.sheet_service:
                try:
                    data = await self.sheet_service.get_qa_data()
                    for row in data:
                        if (row.get('category', '').lower() == category_id.lower() and 
                            row.get('notes') == 'よくある質問' and 
                            row.get('faq_id')):
                            faqs.append({
                                "id": row["faq_id"],
                                "question": row["question"],
                                "answer": row.get("answer", "")
                            })
                except Exception as e:
                    LOGGER.error(f"FAQ取得エラー: {e}")
            
            return {
                "message": f"{category_name}についてのご質問ですね。\n\nよくあるご質問から選択するか、直接ご質問をご入力ください。",
                "type": "faq_selection",
                "category": {
                    "id": category_id,
                    "name": category_name,
                    "description": f"{category_name}に関する情報"
                },
                "faqs": faqs,
                "show_inquiry_button": True
            }
            
        async def select_faq(self, conversation_id, faq_id):
            if self.sheet_service:
                try:
                    data = await self.sheet_service.get_qa_data()
                    for row in data:
                        if row.get('faq_id') == faq_id:
                            return {
                                "message": row["answer"],
                                "type": "faq_answer",
                                "faq_id": faq_id,
                                "source": row.get("source"),
                                "show_inquiry_button": True,
                                "show_more_questions": True
                            }
                except Exception as e:
                    LOGGER.error(f"FAQ選択エラー: {e}")
            
            return {
                "message": "申し訳ございません。FAQ情報の取得に失敗しました。",
                "type": "error",
                "show_inquiry_button": True
            }
            
        async def submit_inquiry(self, conversation_id, form_data):
            # バリデーション
            required_fields = ['name', 'company', 'email', 'inquiry']
            missing_fields = []
            for field in required_fields:
                if not form_data.get(field, '').strip():
                    missing_fields.append(field)
            
            if missing_fields:
                field_names = {
                    'name': 'お名前',
                    'company': '会社名', 
                    'email': 'メールアドレス',
                    'inquiry': 'お問い合わせ内容'
                }
                missing_names = [field_names.get(field, field) for field in missing_fields]
                raise ValueError(f"以下の必須項目が入力されていません: {', '.join(missing_names)}")
            
            # お問い合わせIDを生成
            inquiry_id = f"INQ_{conversation_id}_{int(datetime.now().timestamp())}"
            
            return {
                "message": "お問合せありがとうございました！担当者からお返事いたしますので、少々お待ちください。",
                "type": "inquiry_completed",
                "inquiry_id": inquiry_id,
                "estimated_response_time": "1営業日以内"
            }
            
        def get_conversation_context(self, conversation_id):
            return None
    
    ConversationFlowService = FallbackConversationFlowService

# 例外クラス
class ChatBotException(Exception):
    """チャットボット基底例外クラス"""

class SearchException(ChatBotException):
    """検索失敗時に発生する例外"""

class DataSourceException(ChatBotException):
    """データソース関連例外"""

# APIリクエスト/レスポンスモデル
class CategorySelectionRequest(BaseModel):
    conversation_id: str
    category_id: str

class FAQSelectionRequest(BaseModel):
    conversation_id: str
    faq_id: str

class InquirySubmissionRequest(BaseModel):
    conversation_id: str
    form_data: Dict[str, str]

class SearchQuery(BaseModel):
    question: str = Field(..., title="ユーザーの質問")
    category: Optional[str] = Field(None, title="質問カテゴリ")
    conversation_id: Optional[str] = Field(None, title="会話ID")

class SearchResponse(BaseModel):
    answer: str
    confidence: float
    source: Optional[str] = None
    question: Optional[str] = None
    response_type: str = "search"

class FeedbackRequest(BaseModel):
    conversation_id: str = Field(..., description="会話の一意識別子")
    rating: str = Field(..., description="positive または negative")
    comment: Optional[str] = Field(None, description="追加コメント")

# サービスクラス
class SlackNotificationService:
    """Slack通知送信用のサービス"""

    def __init__(self, webhook_url: Optional[str] = None) -> None:
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)
        
        if self.enabled:
            LOGGER.info(f"Slack通知サービス: 有効")
        else:
            LOGGER.info("Slack通知サービス: 無効 (Webhook URLが設定されていません)")

    async def notify_chat_interaction(
        self,
        question: str,
        answer: str,
        confidence: float,
        user_info: Optional[Dict[str, str]] = None,
        interaction_type: str = "search"
    ) -> None:
        """チャット対話の通知"""
        LOGGER.info(
            "[Slack] %s: question=%s, answer=%.50s..., confidence=%.2f",
            interaction_type,
            question,
            answer,
            confidence
        )

    async def notify_faq_selection(
        self, 
        faq_id: str, 
        question: str, 
        category: str,
        user_info: Optional[Dict[str, str]] = None
    ) -> None:
        """FAQ選択の通知"""
        LOGGER.info(
            "[Slack] FAQ選択: faq_id=%s, category=%s, question=%s",
            faq_id, category, question
        )

    async def notify_inquiry_submission(self, inquiry_data: Dict[str, str]) -> None:
        """お問い合わせ送信時の通知"""
        company = inquiry_data.get('company', '')
        name = inquiry_data.get('name', '')
        email = inquiry_data.get('email', '')
        inquiry = inquiry_data.get('inquiry', '')
        
        LOGGER.info(
            "[Slack] 🔥 新しいお問い合わせ: %s (%s) - %s",
            name, company, email
        )
        LOGGER.info("[Slack] 内容: %.100s...", inquiry)

    async def notify_negative_feedback(self, feedback: Dict[str, str]) -> None:
        """ネガティブフィードバックの通知"""
        LOGGER.info("[Slack] ⚠️  ネガティブフィードバック: %s", feedback)

    async def notify_data_source_change(self, source_type: str, status: str) -> None:
        """データソース変更の通知"""
        LOGGER.info(f"[Slack] 📊 データソース変更: {source_type} - {status}")

class SearchService:
    """Q&Aデータに対してファジー検索を実行するサービス"""

    def __init__(self, data_service) -> None:
        self.data_service = data_service
        self.similarity_threshold = getattr(settings, 'search_similarity_threshold', 0.1)

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """文字列の類似度を計算"""
        return SequenceMatcher(None, a, b).ratio()

    async def search(
        self, 
        query: str, 
        category: Optional[str] = None,
        exclude_faqs: bool = False
    ) -> SearchResponse:
        """検索を実行"""
        try:
            data = await self.data_service.get_qa_data()
        except Exception as e:
            raise SearchException(f"データ取得エラー: {str(e)}")
        
        if not data:
            raise SearchException("Q&Aデータが空です。")

        query_norm = query.strip().lower()
        best_match = None
        best_score = 0.0
        
        for row in data:
            # カテゴリーフィルター
            if category and row.get('category'):
                if row['category'].lower() != category.lower():
                    continue
            
            # FAQを除外する場合
            if exclude_faqs and row.get('notes') == 'よくある質問':
                continue
                
            question = row.get('question', '')
            if not question:
                continue
                
            score = self._similarity(query_norm, question.lower())
            if score > best_score:
                best_match = row
                best_score = score

        if not best_match or best_score < self.similarity_threshold:
            raise SearchException("該当する回答が見つかりませんでした。より具体的なキーワードでお試しください。")

        answer = best_match.get('answer', '')
        if not answer:
            answer = "申し訳ございませんが、この質問に対する回答が登録されていません。お問い合わせフォームからご連絡ください。"
        
        return SearchResponse(
            answer=answer,
            confidence=round(float(best_score), 2),
            source=best_match.get('source'),
            question=best_match.get('question'),
            response_type="search"
        )

class FeedbackService:
    """ユーザーフィードバックを記録するサービス"""

    def __init__(self, slack_service: SlackNotificationService) -> None:
        self.slack_service = slack_service

    async def record_feedback(
        self, 
        conversation_id: str, 
        rating: str, 
        comment: Optional[str],
        context: Optional[Dict] = None
    ) -> None:
        """フィードバックを記録"""
        feedback = {
            "conversation_id": conversation_id,
            "rating": rating,
            "comment": comment,
            "timestamp": datetime.now().isoformat(),
            "context": context
        }
        
        LOGGER.info("フィードバックを記録: %s", feedback)
        
        # ネガティブフィードバックの場合はSlackに通知
        if rating == "negative":
            await self.slack_service.notify_negative_feedback(feedback)

# サービスの初期化
if data_service:
    conversation_flow_service = ConversationFlowService(data_service)
    search_service = SearchService(data_service)
else:
    conversation_flow_service = None
    search_service = None
    LOGGER.error("❌ データサービスが利用できません")

# Slack通知サービスの初期化
slack_webhook_url = getattr(settings, 'slack_webhook_url', None)
slack_service = SlackNotificationService(webhook_url=slack_webhook_url)
feedback_service = FeedbackService(slack_service)

# FastAPIアプリケーションの初期化
app_name = getattr(settings, 'app_name', 'PIP‑Maker Chat API')
app_version = getattr(settings, 'app_version', '1.5.1')
app = FastAPI(
    title=f"{app_name} (対話フロー対応版)", 
    version=app_version,
    description="対話フロー機能完全対応版"
)

# 例外ハンドラー
@app.exception_handler(ChatBotException)
async def chatbot_exception_handler(request: Request, exc: ChatBotException) -> JSONResponse:
    """ChatBotExceptionとそのサブクラス用の統一エラーレスポンス"""
    error_id = uuid.uuid4().hex
    LOGGER.error("%s: %s [error_id=%s]", exc.__class__.__name__, exc, error_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": "システムエラーが発生しました。",
            "fallback_message": "申し訳ございません。担当者までお問い合わせください。",
            "error_id": error_id,
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """pydanticバリデーションエラーを適切に処理"""
    return JSONResponse(
        status_code=422,
        content={"error": "入力内容が正しくありません。", "details": exc.errors()},
    )

# 基本エンドポイント
@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """フロントエンドHTMLページを配信"""
    # 🔧 パス検索ロジック修正
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "index.html"),
        os.path.join(os.getcwd(), "index.html"),
        "index.html"
    ]
    
    html_content = None
    for html_path in possible_paths:
        if os.path.exists(html_path):
            try:
                with open(html_path, encoding="utf-8") as fp:
                    html_content = fp.read()
                LOGGER.info(f"✅ HTMLファイルを読み込み: {html_path}")
                break
            except Exception as e:
                LOGGER.warning(f"HTMLファイル読み込みエラー {html_path}: {e}")
                continue
    
    if not html_content:
        # フォールバックHTML
        html_content = """
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <title>PIP-Maker Chat</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                .success { background: #e8f5e8; padding: 20px; border-radius: 8px; border: 1px solid #4caf50; }
            </style>
        </head>
        <body>
            <div class="success">
                <h1>🎉 PIP-Maker チャットボット</h1>
                <p>システムが起動しました！</p>
                <p>チャット機能を利用できます。</p>
            </div>
        </body>
        </html>"""
        LOGGER.warning("⚠️ フォールバックHTMLを使用")
    
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health() -> Dict[str, Any]:
    """ヘルスチェックエンドポイント"""
    csv_path = getattr(settings, 'csv_file_path', 'unknown')
    
    return {
        "status": "ok", 
        "version": app_version,
        "phase": "1.5.1-conversation-flow",
        "data_service": type(data_service).__name__ if data_service else "None",
        "search_service": type(search_service).__name__ if search_service else "None",
        "conversation_flow_service": type(conversation_flow_service).__name__ if conversation_flow_service else "None",
        "csv_path": csv_path,
        "csv_exists": os.path.exists(csv_path) if csv_path != 'unknown' else False,
        "csv_absolute_path": os.path.abspath(csv_path) if csv_path != 'unknown' else 'unknown'
    }

@app.post("/api/search", response_model=SearchResponse)
async def search_endpoint(query: SearchQuery) -> SearchResponse:
    """検索エンドポイント"""
    if not search_service:
        raise ChatBotException("検索サービスが初期化されていません")
        
    try:
        result = await search_service.search(
            query.question, 
            query.category,
            exclude_faqs=False
        )
    except SearchException as exc:
        raise ChatBotException(str(exc)) from exc
    
    # Slack通知
    await slack_service.notify_chat_interaction(
        question=query.question,
        answer=result.answer,
        confidence=result.confidence,
        interaction_type="search"
    )
    
    return result

@app.post("/api/feedback")
async def feedback_endpoint(feedback: FeedbackRequest) -> Dict[str, str]:
    """フィードバック記録エンドポイント"""
    if feedback.rating not in ["positive", "negative"]:
        raise HTTPException(
            status_code=422, 
            detail="ratingは 'positive' または 'negative' である必要があります"
        )
    
    context = None
    if conversation_flow_service:
        context_obj = conversation_flow_service.get_conversation_context(feedback.conversation_id)
        if context_obj:
            context = {
                "state": getattr(context_obj, 'state', 'unknown'),
                "category": getattr(context_obj, 'selected_category', None),
                "interaction_count": getattr(context_obj, 'interaction_count', 0)
            }
    
    await feedback_service.record_feedback(
        conversation_id=feedback.conversation_id,
        rating=feedback.rating,
        comment=feedback.comment,
        context=context
    )
    
    return {"status": "received"}

# 🔧 対話フロー用エンドポイント（完全実装）
@app.get("/api/conversation/welcome")
async def get_welcome_message() -> Dict[str, Any]:
    """初期の歓迎メッセージとカテゴリー選択肢を返す"""
    if not conversation_flow_service:
        return {
            "message": "こんにちは！PIP-Makerについてのご質問をお気軽にどうぞ。",
            "type": "welcome"
        }
    
    try:
        return await conversation_flow_service.get_welcome_message()
    except Exception as e:
        LOGGER.error(f"Welcome message error: {e}")
        return {
            "message": "こんにちは！PIP-Makerについてのご質問をお気軽にどうぞ。",
            "type": "welcome_fallback"
        }

@app.post("/api/conversation/category")
async def select_category_endpoint(request: CategorySelectionRequest) -> Dict[str, Any]:
    """カテゴリー選択処理"""
    if not conversation_flow_service:
        raise HTTPException(status_code=500, detail="対話フローサービスが利用できません")
    
    try:
        LOGGER.info(f"カテゴリー選択: {request.category_id} (会話ID: {request.conversation_id})")
        
        result = await conversation_flow_service.select_category(
            request.conversation_id, 
            request.category_id
        )
        
        LOGGER.info(f"カテゴリー選択処理完了: {request.category_id}")
        return result
        
    except ValueError as exc:
        LOGGER.error(f"カテゴリー選択バリデーションエラー: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        LOGGER.error(f"カテゴリー選択処理エラー: {exc}")
        import traceback
        LOGGER.error(f"スタックトレース: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="カテゴリー選択でエラーが発生しました。もう一度お試しください。")

@app.post("/api/conversation/faq")
async def select_faq_endpoint(request: FAQSelectionRequest) -> Dict[str, Any]:
    """FAQ選択処理"""
    if not conversation_flow_service:
        raise HTTPException(status_code=500, detail="対話フローサービスが利用できません")
    
    try:
        LOGGER.info(f"FAQ選択: {request.faq_id} (会話ID: {request.conversation_id})")
        
        result = await conversation_flow_service.select_faq(
            request.conversation_id,
            request.faq_id
        )
        
        # Slack通知
        await slack_service.notify_faq_selection(
            faq_id=request.faq_id,
            question=result.get("message", "")[:100],
            category="unknown"
        )
        
        return result
        
    except ValueError as exc:
        LOGGER.error(f"FAQ選択バリデーションエラー: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        LOGGER.error(f"FAQ選択処理エラー: {exc}")
        raise HTTPException(status_code=500, detail="FAQ選択でエラーが発生しました。もう一度お試しください。")

@app.post("/api/conversation/inquiry")
async def submit_inquiry_endpoint(request: InquirySubmissionRequest) -> Dict[str, Any]:
    """お問い合わせ送信処理"""
    if not conversation_flow_service:
        raise HTTPException(status_code=500, detail="対話フローサービスが利用できません")
    
    try:
        LOGGER.info(f"お問い合わせ送信: (会話ID: {request.conversation_id})")
        
        result = await conversation_flow_service.submit_inquiry(
            request.conversation_id,
            request.form_data
        )
        
        # Slack通知
        await slack_service.notify_inquiry_submission(request.form_data)
        
        return result
        
    except ValueError as exc:
        LOGGER.error(f"お問い合わせバリデーションエラー: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        LOGGER.error(f"お問い合わせ送信処理エラー: {exc}")
        raise HTTPException(status_code=500, detail="お問い合わせ送信でエラーが発生しました。もう一度お試しください。")

# デバッグエンドポイント
@app.get("/debug/status")
async def debug_status() -> Dict[str, Any]:
    """デバッグ情報を表示"""
    csv_path = getattr(settings, 'csv_file_path', 'unknown')
    
    debug_info = {
        "working_directory": os.getcwd(),
        "csv_path": csv_path,
        "csv_absolute_path": os.path.abspath(csv_path) if csv_path != 'unknown' else 'unknown',
        "csv_exists": os.path.exists(csv_path) if csv_path != 'unknown' else False,
        "data_service": type(data_service).__name__ if data_service else "None",
        "conversation_flow_service": type(conversation_flow_service).__name__ if conversation_flow_service else "None",
        "search_service": type(search_service).__name__ if search_service else "None",
        "directory_contents": list(os.listdir(os.getcwd())),
        "src_directory_contents": list(os.listdir('./src')) if os.path.exists('./src') else "src directory not found"
    }
    
    # データサービスの詳細情報
    if data_service and hasattr(data_service, 'get_cache_info'):
        debug_info['data_service_cache'] = data_service.get_cache_info()
    
    return debug_info

# 静的ファイル配信（修正版）
project_root = Path(__file__).parent.parent
static_paths_to_try = [
    Path(__file__).parent / "static",
    project_root / "static",
    project_root / "src" / "static",
]