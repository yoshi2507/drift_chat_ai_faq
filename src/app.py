# src/app.py - Phase 2 AI統合完全版

"""
PIP-Maker チャットボット Phase 2.0 - AI統合完全版
OpenAI統合、カテゴリー対応検索、意図分類機能搭載
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

# エラーハンドリング
from .error_handling import (
    ChatBotException, 
    DataSourceException, 
    SearchException, 
    ConversationFlowException,
    AIServiceException,
    CategoryException,
    VectorSearchException,
    chatbot_exception_handler,
    general_exception_handler,
)

# 設定とサービス
from .config import (
    get_settings, 
    create_complete_ai_system,
    create_data_service,
    create_category_aware_search_service
)

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# 🚀 Phase 2: AI統合システム初期化
print("🚀 Phase 2: AI統合システム初期化中...")
settings = get_settings()

try:
    # 完全なAIシステムを作成
    ai_components = create_complete_ai_system()
    
    # コンポーネント取得
    data_service = ai_components.get('data_service')
    openai_service = ai_components.get('openai_service')
    intent_classifier = ai_components.get('intent_classifier')
    category_search_engine = ai_components.get('category_search_engine')
    basic_search_service = ai_components.get('basic_search_service')
    
    LOGGER.info("✅ Phase 2 AI統合システム初期化完了")
    
    # 利用可能機能をログ出力
    available_features = []
    if data_service:
        available_features.append(f"データ: {type(data_service).__name__}")
    if openai_service:
        available_features.append("OpenAI統合")
    if intent_classifier:
        available_features.append("AI意図分類")
    if category_search_engine:
        available_features.append("カテゴリー対応検索")
    if basic_search_service:
        available_features.append("基本検索")
    
    LOGGER.info(f"✨ 利用可能機能: {', '.join(available_features)}")
    
except Exception as e:
    LOGGER.error(f"❌ AI統合システム初期化失敗: {e}")
    
    # フォールバック：基本システム
    print("📄 フォールバック：基本システムで起動")
    try:
        data_service = create_data_service()
        openai_service = None
        intent_classifier = None
        category_search_engine = None
        basic_search_service = None
        
        if data_service:
            # 基本検索サービスを作成
            class BasicSearchService:
                def __init__(self, data_service):
                    self.data_service = data_service
                    self.similarity_threshold = getattr(settings, 'search_similarity_threshold', 0.3)
                
                @staticmethod
                def _similarity(a: str, b: str) -> float:
                    return SequenceMatcher(None, a, b).ratio()
                
                async def search(self, query: str, category: Optional[str] = None, exclude_faqs: bool = False):
                    try:
                        data = await self.data_service.get_qa_data()
                    except Exception as e:
                        raise DataSourceException(f"Q&Aデータの取得に失敗しました") from e
                    
                    if not data:
                        raise SearchException("該当する回答が見つかりませんでした。")
                    
                    query_norm = query.strip().lower()
                    best_match = None
                    best_score = 0.0
                    
                    for row in data:
                        if category and row.get('category', '').lower() != category.lower():
                            continue
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
                        raise SearchException("該当する回答が見つかりませんでした。")
                    
                    # SearchResponseクラス（フォールバック用）
                    class SearchResponse:
                        def __init__(self, answer, confidence, source=None, question=None, response_type="search"):
                            self.answer = answer
                            self.confidence = confidence
                            self.source = source
                            self.question = question
                            self.response_type = response_type
                    
                    return SearchResponse(
                        answer=best_match.get('answer', ''),
                        confidence=round(float(best_score), 2),
                        source=best_match.get('source'),
                        question=best_match.get('question'),
                        response_type="basic_search"
                    )
            
            basic_search_service = BasicSearchService(data_service)
            LOGGER.info("📄 基本検索サービス初期化完了（フォールバック）")
        
    except Exception as fallback_error:
        LOGGER.error(f"❌ フォールバック初期化も失敗: {fallback_error}")
        data_service = None
        basic_search_service = None

# ConversationFlowService の初期化
try:
    from .conversation_flow import ConversationFlowService
    
    if data_service:
        conversation_flow_service = ConversationFlowService(data_service)
        LOGGER.info("✅ 対話フローサービス初期化完了")
    else:
        conversation_flow_service = None
        LOGGER.warning("⚠️ 対話フローサービス: データサービスなしで無効")
        
except ImportError as e:
    LOGGER.error(f"❌ ConversationFlowService import error: {e}")
    conversation_flow_service = None

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
    use_ai_generation: bool = Field(default=True, title="AI回答生成使用")
    use_category_optimization: bool = Field(default=True, title="カテゴリー最適化使用")

class SearchResponse(BaseModel):
    answer: str
    confidence: float
    source: Optional[str] = None
    question: Optional[str] = None
    response_type: str = "search"
    category: Optional[str] = None
    sources_used: List[str] = []
    ai_generated: bool = False
    category_optimized: bool = False
    search_time: Optional[float] = None
    intent_confidence: Optional[float] = None
    method: str = "unknown"

class FeedbackRequest(BaseModel):
    conversation_id: str = Field(..., description="会話の一意識別子")
    rating: str = Field(..., description="positive または negative")
    comment: Optional[str] = Field(None, description="追加コメント")

# Slack通知サービス
class SlackNotificationService:
    """Slack通知送信用のサービス（AI対応版）"""

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
        interaction_type: str = "search",
        ai_generated: bool = False,
        category: str = "unknown",
        sources_used: List[str] = []
    ) -> None:
        """チャット対話の通知（AI情報付き）"""
        ai_info = "🤖 AI生成" if ai_generated else "📊 データベース"
        sources_info = f"({len(sources_used)}件のソース)" if sources_used else ""
        
        LOGGER.info(
            "[Slack] %s %s: question=%s, answer=%.50s..., confidence=%.2f, category=%s %s",
            ai_info,
            interaction_type,
            question,
            answer,
            confidence,
            category,
            sources_info
        )

    async def notify_ai_service_status(self, service_name: str, status: str, details: Dict = None) -> None:
        """AIサービス状態変更の通知"""
        LOGGER.info(f"[Slack] 🤖 AIサービス状態: {service_name} - {status}")
        if details:
            LOGGER.info(f"[Slack] 詳細: {details}")

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

# フィードバックサービス
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
slack_webhook_url = getattr(settings, 'slack_webhook_url', None)
slack_service = SlackNotificationService(webhook_url=slack_webhook_url)
feedback_service = FeedbackService(slack_service)

# FastAPIアプリケーションの初期化
app_name = getattr(settings, 'app_name', 'PIP‑Maker Chat API')
app_version = getattr(settings, 'app_version', '2.0.0')
app = FastAPI(
    title=f"{app_name} (Phase 2 AI統合版)", 
    version=app_version,
    description="OpenAI統合、カテゴリー対応検索、意図分類機能搭載"
)

# 例外ハンドラー
app.add_exception_handler(ChatBotException, chatbot_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

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
    # HTMLファイル検索
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
        # フォールバックHTML（Phase 2対応）
        html_content = """
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <title>PIP-Maker Chat (Phase 2)</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                .success { background: linear-gradient(135deg, #e8f5e8 0%, #d4edda 100%); padding: 20px; border-radius: 12px; border: 1px solid #4caf50; }
                .feature { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #007bff; }
                .ai-badge { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px; }
            </style>
        </head>
        <body>
            <div class="success">
                <h1>🚀 PIP-Maker チャットボット (Phase 2)</h1>
                <p><span class="ai-badge">🤖 AI統合</span> システムが起動しました！</p>
                
                <div class="feature">
                    <h3>✨ 新機能</h3>
                    <ul>
                        <li>🤖 OpenAI統合による高精度回答生成</li>
                        <li>🎯 AI意図分類によるカテゴリー自動判定</li>
                        <li>🔍 カテゴリー対応検索エンジン</li>
                        <li>📊 コンテキスト対応回答最適化</li>
                    </ul>
                </div>
                
                <p>チャット機能をお試しください。</p>
            </div>
        </body>
        </html>"""
        LOGGER.warning("⚠️ フォールバックHTML（Phase 2対応）を使用")
    
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health() -> Dict[str, Any]:
    """ヘルスチェックエンドポイント（Phase 2対応）"""
    csv_path = getattr(settings, 'csv_file_path', 'unknown')
    
    health_info = {
        "status": "ok", 
        "version": app_version,
        "phase": "2.0-ai-integration",
        "timestamp": datetime.now().isoformat(),
        
        # Phase 2: AI統合機能
        "ai_features": {
            "openai_service": openai_service is not None,
            "intent_classifier": intent_classifier is not None,
            "category_search_engine": category_search_engine is not None,
            "ai_answer_generation": bool(openai_service and settings.ai_answer_generation),
            "ai_intent_classification": bool(intent_classifier and settings.ai_intent_classification)
        },
        
        # 基本サービス
        "services": {
            "data_service": type(data_service).__name__ if data_service else "None",
            "basic_search_service": type(basic_search_service).__name__ if basic_search_service else "None",
            "conversation_flow_service": type(conversation_flow_service).__name__ if conversation_flow_service else "None"
        },
        
        # データソース情報
        "data_sources": {
            "csv_path": csv_path,
            "csv_exists": os.path.exists(csv_path) if csv_path != 'unknown' else False,
            "csv_absolute_path": os.path.abspath(csv_path) if csv_path != 'unknown' else 'unknown',
            "google_sheets_configured": settings.is_google_sheets_configured
        }
    }
    
    # OpenAI サービスのヘルスチェック
    if openai_service:
        try:
            openai_health = await openai_service.health_check()
            health_info["ai_services"] = {"openai": openai_health}
        except Exception as e:
            health_info["ai_services"] = {"openai": {"status": "error", "error": str(e)}}
    
    # カテゴリー検索エンジンのヘルスチェック
    if category_search_engine:
        try:
            category_health = await category_search_engine.health_check()
            health_info["ai_services"]["category_search"] = category_health
        except Exception as e:
            health_info["ai_services"]["category_search"] = {"status": "error", "error": str(e)}
    
    return health_info

@app.post("/api/search", response_model=SearchResponse)
async def search_endpoint(query: SearchQuery) -> SearchResponse:
    """検索エンドポイント（Phase 2: AI統合完全版）"""
    
    # 入力バリデーション
    if not query.question:
        raise SearchException("質問を入力してください。", query="")
    
    question_trimmed = query.question.strip()
    if not question_trimmed:
        raise SearchException("質問を入力してください。", query=query.question)
    
    if len(question_trimmed) < 2:
        raise SearchException("もう少し詳しい質問を入力してください。", query=question_trimmed)
    
    search_start_time = datetime.now()
    
    # === Phase 2: AI統合検索パイプライン ===
    
    # 1. AI統合カテゴリー対応検索（最優先）
    if category_search_engine and query.use_category_optimization:
        try:
            LOGGER.info(f"🤖 AI統合検索開始: {question_trimmed}")
            
            # 会話コンテキストを構築
            conversation_context = {
                "conversation_id": query.conversation_id,
                "selected_category": query.category
            } if query.conversation_id else None
            
            # AI統合検索を実行
            result = await category_search_engine.search_with_category_context(
                query=question_trimmed,
                selected_category=query.category,
                conversation_context=conversation_context,
                use_ai_generation=query.use_ai_generation and bool(openai_service)
            )
            
            # Phase 2 結果をSearchResponseに変換
            search_response = SearchResponse(
                answer=result['answer'],
                confidence=result['confidence'],
                source=result.get('sources_used', [None])[0],  # 最初のソース
                question=question_trimmed,
                response_type="ai_integrated",
                category=result.get('category'),
                sources_used=result.get('sources_used', []),
                ai_generated=result.get('ai_generated', False),
                category_optimized=result.get('category_optimized', True),
                search_time=result.get('search_time'),
                intent_confidence=result.get('intent_confidence'),
                method=result.get('method', 'ai_integrated')
            )
            
            # Slack通知（AI情報付き）
            try:
                await slack_service.notify_chat_interaction(
                    question=question_trimmed,
                    answer=result['answer'],
                    confidence=result['confidence'],
                    interaction_type="ai_integrated_search",
                    ai_generated=result.get('ai_generated', False),
                    category=result.get('category', 'unknown'),
                    sources_used=result.get('sources_used', [])
                )
            except Exception as slack_error:
                LOGGER.warning(f"Slack通知失敗: {slack_error}")
            
            LOGGER.info(f"✅ AI統合検索成功: 信頼度={result['confidence']:.2f}, AI生成={result.get('ai_generated', False)}")
            return search_response
            
        except Exception as ai_error:
            LOGGER.warning(f"⚠️ AI統合検索失敗: {ai_error}")
            
            # フォールバック処理へ
            if not basic_search_service:
                raise SearchException("AI統合検索が失敗し、フォールバック検索も利用できません。")
    
    # 2. 基本検索（フォールバック）
    if basic_search_service:
        try:
            LOGGER.info(f"📄 基本検索開始（フォールバック）: {question_trimmed}")
            
            result = await basic_search_service.search(
                question_trimmed,
                query.category,
                exclude_faqs=False
            )
            
            # 検索時間を計算
            search_time = (datetime.now() - search_start_time).total_seconds()
            
            # SearchResponse形式に変換
            search_response = SearchResponse(
                answer=result.answer,
                confidence=result.confidence,
                source=result.source,
                question=result.question,
                response_type="basic_search",
                category=query.category,
                sources_used=[result.source] if result.source else [],
                ai_generated=False,
                category_optimized=False,
                search_time=search_time,
                method="basic_fallback"
            )
            
            # Slack通知
            try:
                await slack_service.notify_chat_interaction(
                    question=question_trimmed,
                    answer=result.answer,
                    confidence=result.confidence,
                    interaction_type="basic_search_fallback",
                    ai_generated=False,
                    category=query.category or "unknown"
                )
            except Exception as slack_error:
                LOGGER.warning(f"Slack通知失敗: {slack_error}")
            
            LOGGER.info(f"✅ 基本検索成功（フォールバック）: 信頼度={result.confidence:.2f}")
            return search_response
            
        except SearchException:
            raise
        except Exception as exc:
            LOGGER.error(f"❌ 基本検索エラー: {exc}")
            raise SearchException("検索処理中にエラーが発生しました。") from exc
    
    # 3. 全ての検索手段が失敗
    raise SearchException("検索サービスが利用できません。システム管理者にお問い合わせください。")

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

# === 対話フロー用エンドポイント ===

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
        raise ConversationFlowException(
            "対話フローサービスが利用できません",
            conversation_id=request.conversation_id,
            state="service_unavailable"
        )
    
    try:
        LOGGER.info(f"カテゴリー選択: {request.category_id} (会話ID: {request.conversation_id})")
        
        result = await conversation_flow_service.select_category(
            request.conversation_id, 
            request.category_id
        )
        
        LOGGER.info(f"カテゴリー選択処理完了: {request.category_id}")
        return result
        
    except ValueError as exc:
        raise ConversationFlowException(
            f"カテゴリー選択でエラーが発生しました: {str(exc)}",
            conversation_id=request.conversation_id,
            state="category_selection"
        ) from exc
    except Exception as exc:
        LOGGER.error(f"カテゴリー選択処理エラー: {exc}")
        raise ConversationFlowException(
            "カテゴリー選択でエラーが発生しました。もう一度お試しください。",
            conversation_id=request.conversation_id,
            state="category_selection"
        ) from exc

@app.post("/api/conversation/faq")
async def select_faq_endpoint(request: FAQSelectionRequest) -> Dict[str, Any]:
    """FAQ選択処理"""
    if not conversation_flow_service:
        raise ConversationFlowException(
            "対話フローサービスが利用できません",
            conversation_id=request.conversation_id,
            state="service_unavailable"
        )
    
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
        raise ConversationFlowException(
            f"FAQ選択でエラーが発生しました: {str(exc)}",
            conversation_id=request.conversation_id,
            state="faq_selection"
        ) from exc
    except Exception as exc:
        LOGGER.error(f"FAQ選択処理エラー: {exc}")
        raise ConversationFlowException(
            "FAQ選択でエラーが発生しました。もう一度お試しください。",
            conversation_id=request.conversation_id,
            state="faq_selection"
        ) from exc

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

# === Phase 2: AI統合デバッグエンドポイント ===

@app.get("/debug/ai-status")
async def debug_ai_status() -> Dict[str, Any]:
    """AI統合システムのステータス確認"""
    ai_status = {
        "timestamp": datetime.now().isoformat(),
        "phase": "2.0-ai-integration",
        "components": {},
        "configuration": {},
        "health_checks": {}
    }
    
    # コンポーネント状態
    ai_status["components"] = {
        "data_service": {
            "available": data_service is not None,
            "type": type(data_service).__name__ if data_service else None
        },
        "openai_service": {
            "available": openai_service is not None,
            "configured": bool(settings.openai_api_key)
        },
        "intent_classifier": {
            "available": intent_classifier is not None,
            "ai_enabled": bool(intent_classifier and openai_service)
        },
        "category_search_engine": {
            "available": category_search_engine is not None,
            "ai_enhanced": bool(category_search_engine and openai_service)
        },
        "basic_search_service": {
            "available": basic_search_service is not None,
            "fallback_ready": bool(basic_search_service)
        }
    }
    
    # 設定情報
    ai_status["configuration"] = {
        "ai_answer_generation": settings.ai_answer_generation,
        "ai_intent_classification": settings.ai_intent_classification,
        "category_search_enabled": settings.category_search_enabled,
        "openai_model": settings.openai_model,
        "openai_requests_per_minute": settings.openai_requests_per_minute,
        "openai_daily_budget": settings.openai_daily_budget
    }
    
    # ヘルスチェック
    if openai_service:
        try:
            openai_health = await openai_service.health_check()
            ai_status["health_checks"]["openai"] = openai_health
        except Exception as e:
            ai_status["health_checks"]["openai"] = {"status": "error", "error": str(e)}
    
    if category_search_engine:
        try:
            category_health = await category_search_engine.health_check()
            ai_status["health_checks"]["category_search"] = category_health
        except Exception as e:
            ai_status["health_checks"]["category_search"] = {"status": "error", "error": str(e)}
    
    return ai_status

@app.get("/debug/status")
async def debug_status() -> Dict[str, Any]:
    """総合デバッグ情報を表示（Phase 2対応）"""
    csv_path = getattr(settings, 'csv_file_path', 'unknown')
    
    debug_info = {
        "system": {
            "working_directory": os.getcwd(),
            "phase": "2.0-ai-integration",
            "timestamp": datetime.now().isoformat()
        },
        "data_sources": {
            "csv_path": csv_path,
            "csv_absolute_path": os.path.abspath(csv_path) if csv_path != 'unknown' else 'unknown',
            "csv_exists": os.path.exists(csv_path) if csv_path != 'unknown' else False,
            "google_sheets_configured": settings.is_google_sheets_configured
        },
        "services": {
            "data_service": type(data_service).__name__ if data_service else "None",
            "conversation_flow_service": type(conversation_flow_service).__name__ if conversation_flow_service else "None",
            "basic_search_service": type(basic_search_service).__name__ if basic_search_service else "None"
        },
        "ai_services": {
            "openai_service": type(openai_service).__name__ if openai_service else "None",
            "intent_classifier": type(intent_classifier).__name__ if intent_classifier else "None",
            "category_search_engine": type(category_search_engine).__name__ if category_search_engine else "None"
        },
        "environment": {
            "directory_contents": list(os.listdir(os.getcwd())),
            "src_directory_contents": list(os.listdir('./src')) if os.path.exists('./src') else "src directory not found"
        }
    }
    
    # データサービスの詳細情報
    if data_service and hasattr(data_service, 'get_cache_info'):
        debug_info['data_service_cache'] = data_service.get_cache_info()
    
    # OpenAI使用統計
    if openai_service and hasattr(openai_service, 'get_usage_stats'):
        debug_info['openai_usage_stats'] = openai_service.get_usage_stats()
    
    return debug_info

# === Phase 2: AI管理エンドポイント ===

@app.post("/admin/ai/reload")
async def reload_ai_services() -> Dict[str, Any]:
    """AIサービスの再読み込み（管理者用）"""
    global openai_service, intent_classifier, category_search_engine
    
    try:
        LOGGER.info("🔄 AIサービス再読み込み開始...")
        
        # AIコンポーネントを再作成
        new_components = create_complete_ai_system()
        
        # グローバル変数を更新
        openai_service = new_components.get('openai_service')
        intent_classifier = new_components.get('intent_classifier')
        category_search_engine = new_components.get('category_search_engine')
        
        # Slack通知
        await slack_service.notify_ai_service_status(
            "AI_SYSTEM", 
            "RELOADED",
            {
                "openai": openai_service is not None,
                "intent_classifier": intent_classifier is not None,
                "category_search": category_search_engine is not None
            }
        )
        
        return {
            "status": "success",
            "message": "AIサービスが正常に再読み込みされました",
            "components_reloaded": {
                "openai_service": openai_service is not None,
                "intent_classifier": intent_classifier is not None,
                "category_search_engine": category_search_engine is not None
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        LOGGER.error(f"❌ AIサービス再読み込み失敗: {e}")
        return {
            "status": "error",
            "message": f"AIサービスの再読み込みに失敗しました: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

# 静的ファイル配信
project_root = Path(__file__).parent.parent
static_paths_to_try = [
    Path(__file__).parent / "static",
    project_root / "static",
    project_root / "src" / "static",
]