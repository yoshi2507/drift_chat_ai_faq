# src/app.py - Google Sheets統合版

"""
PIP-Maker チャットボット Phase 1.5.1 - Google Sheets統合版
リアルタイムスプレッドシート連携機能を追加
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




# 設定をインポート（プロジェクトルートから）
try:
    from config import get_settings, create_data_service
    settings = get_settings()
except ImportError:
    # フォールバック設定
    class FallbackSettings:
        csv_file_path = "qa_data.csv"
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
    
    def create_data_service():
        """設定に基づいて適切なデータサービスを作成"""
        from .google_sheets_service import GoogleSheetsService
        from .enhanced_sheet_service import EnhancedGoogleSheetsService
    
        if settings.is_google_sheets_configured:
            # Google Sheets統合サービスを使用
            return GoogleSheetsService(
                spreadsheet_id=settings.google_sheets_id,
                credentials_path=settings.google_credentials_path,
                fallback_csv_path=settings.csv_file_path
            )
        else:
            # 従来のCSVサービスを使用
            return EnhancedGoogleSheetsService(settings.csv_file_path)

# サービスクラスをインポート（同一ディレクトリから）
from conversation_flow import ConversationFlowService, ConversationState, ConversationContext

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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
    response_type: str = "search"  # "search", "faq", "ai_generated"

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
try:
    # データサービスを設定に基づいて作成
    data_service = create_data_service()
    LOGGER.info(f"データサービス初期化完了: {type(data_service).__name__}")
    
    # データソース設定の表示
    data_config = settings.get_data_source_config()
    LOGGER.info(f"データソース設定: {data_config}")
    
except Exception as e:
    LOGGER.error(f"データサービス初期化エラー: {e}")
    # フォールバック
    from enhanced_sheet_service import EnhancedGoogleSheetsService
    data_service = EnhancedGoogleSheetsService(getattr(settings, 'csv_file_path', 'qa_data.csv'))

conversation_flow_service = ConversationFlowService(data_service)
search_service = SearchService(data_service)

# Slack通知サービスの初期化
slack_webhook_url = getattr(settings, 'slack_webhook_url', None)
slack_service = SlackNotificationService(webhook_url=slack_webhook_url)
feedback_service = FeedbackService(slack_service)

# FastAPIアプリケーションの初期化
app_name = getattr(settings, 'app_name', 'PIP‑Maker Chat API')
app_version = getattr(settings, 'app_version', '1.5.1')  # Google Sheets対応版
app = FastAPI(
    title=f"{app_name} (Google Sheets対応)", 
    version=app_version,
    description="Google Sheetsリアルタイム連携機能を搭載"
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

# 既存エンドポイント
@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """フロントエンドHTMLページを配信"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "index.html")
    try:
        with open(html_path, encoding="utf-8") as fp:
            html = fp.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="index.html not found")
    return HTMLResponse(content=html)

@app.get("/health")
async def health() -> Dict[str, str]:
    """ヘルスチェックエンドポイント"""
    return {
        "status": "ok", 
        "version": app_version,
        "phase": "1.5.1",
        "features": "conversation_flow,faq_system,inquiry_form,google_sheets",
        "data_source": "google_sheets" if getattr(settings, 'is_google_sheets_configured', False) else "csv"
    }

@app.post("/api/search", response_model=SearchResponse)
async def search_endpoint(query: SearchQuery) -> SearchResponse:
    """検索エンドポイント（Google Sheets対応）"""
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
    
    # 会話コンテキストを取得
    context = conversation_flow_service.get_conversation_context(feedback.conversation_id)
    context_data = None
    if context:
        context_data = {
            "state": context.state,
            "category": context.selected_category,
            "interaction_count": context.interaction_count
        }
    
    await feedback_service.record_feedback(
        conversation_id=feedback.conversation_id,
        rating=feedback.rating,
        comment=feedback.comment,
        context=context_data
    )
    
    return {"status": "received"}

# 対話フロー用エンドポイント
@app.get("/api/conversation/welcome")
async def get_welcome_message() -> Dict[str, Any]:
    """初期の歓迎メッセージとカテゴリー選択肢を返す"""
    try:
        return await conversation_flow_service.get_welcome_message()
    except Exception as e:
        LOGGER.error(f"Welcome message error: {e}")
        raise ChatBotException("歓迎メッセージの取得に失敗しました")

@app.post("/api/conversation/category")
async def select_category_endpoint(request: CategorySelectionRequest) -> Dict[str, Any]:
    """カテゴリー選択処理"""
    try:
        return await conversation_flow_service.select_category(
            request.conversation_id, 
            request.category_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        LOGGER.error(f"Category selection error: {exc}")
        raise ChatBotException("カテゴリー選択処理でエラーが発生しました")

@app.post("/api/conversation/faq")
async def select_faq_endpoint(request: FAQSelectionRequest) -> Dict[str, Any]:
    """FAQ選択処理"""
    try:
        result = await conversation_flow_service.select_faq(
            request.conversation_id,
            request.faq_id
        )
        
        # Slack通知
        context = conversation_flow_service.get_conversation_context(request.conversation_id)
        category = context.selected_category if context else "unknown"
        
        await slack_service.notify_faq_selection(
            faq_id=request.faq_id,
            question=result.get("message", "")[:100],
            category=category
        )
        
        return result
        
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        LOGGER.error(f"FAQ selection error: {exc}")
        raise ChatBotException("FAQ選択処理でエラーが発生しました")

@app.post("/api/conversation/inquiry")
async def submit_inquiry_endpoint(request: InquirySubmissionRequest) -> Dict[str, Any]:
    """お問い合わせ送信処理"""
    try:
        result = await conversation_flow_service.submit_inquiry(
            request.conversation_id,
            request.form_data
        )
        
        # Slack通知
        await slack_service.notify_inquiry_submission(request.form_data)
        
        return result
        
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        LOGGER.error(f"Inquiry submission error: {exc}")
        raise ChatBotException("お問い合わせ送信処理でエラーが発生しました")

# Google Sheets統合用の新しいエンドポイント
@app.get("/api/data-source/status")
async def get_data_source_status() -> Dict[str, Any]:
    """データソースの状態を取得"""
    try:
        if hasattr(data_service, 'get_connection_status'):
            connection_status = data_service.get_connection_status()
        else:
            connection_status = {"type": "csv", "status": "active"}
        
        cache_info = data_service.get_cache_info() if hasattr(data_service, 'get_cache_info') else {}
        
        return {
            "connection": connection_status,
            "cache": cache_info,
            "configuration": settings.get_data_source_config(),
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        LOGGER.error(f"Data source status error: {e}")
        return {"error": str(e)}

@app.post("/api/data-source/refresh")
async def refresh_data_source() -> Dict[str, Any]:
    """データソースを強制リフレッシュ"""
    try:
        if hasattr(data_service, 'refresh_data'):
            success = await data_service.refresh_data()
            message = "データを正常にリフレッシュしました" if success else "データリフレッシュに失敗しました"
        else:
            data_service.clear_cache()
            success = True
            message = "キャッシュをクリアしました"
        
        if success:
            await slack_service.notify_data_source_change("manual_refresh", "success")
        
        return {
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        LOGGER.error(f"Data refresh error: {e}")
        await slack_service.notify_data_source_change("manual_refresh", f"error: {str(e)}")
        return {"success": False, "message": str(e)}

# 管理・デバッグ用エンドポイント
@app.get("/api/admin/categories")
async def get_categories_info() -> Dict[str, Any]:
    """カテゴリー情報と統計を取得"""
    try:
        flow_summary = await conversation_flow_service.get_category_summary()
        
        if hasattr(data_service, 'get_categories_summary'):
            sheet_summary = await data_service.get_categories_summary()
        else:
            sheet_summary = {}
        
        cache_info = data_service.get_cache_info() if hasattr(data_service, 'get_cache_info') else {}
        
        return {
            "categories": flow_summary,
            "statistics": sheet_summary,
            "cache_info": cache_info,
            "data_source": type(data_service).__name__
        }
    except Exception as e:
        LOGGER.error(f"Categories info error: {e}")
        raise ChatBotException("カテゴリー情報の取得に失敗しました")

@app.post("/api/admin/cache/clear")
async def clear_cache() -> Dict[str, str]:
    """キャッシュをクリア"""
    try:
        data_service.clear_cache()
        return {"status": "success", "message": "キャッシュをクリアしました"}
    except Exception as e:
        LOGGER.error(f"Cache clear error: {e}")
        return {"status": "error", "message": str(e)}

# テスト用エンドポイント
@app.get("/test-google-sheets")
async def test_google_sheets() -> Dict[str, Any]:
    """Google Sheets接続テスト"""
    try:
        if not hasattr(data_service, 'get_connection_status'):
            return {
                "status": "info",
                "message": "CSVモードで動作中。Google Sheets機能は無効です。"
            }
        
        connection_status = data_service.get_connection_status()
        
        if connection_status.get('service_initialized'):
            # 実際にデータ取得をテスト
            data = await data_service.get_qa_data()
            return {
                "status": "success",
                "message": f"Google Sheets接続成功！{len(data)}件のデータを取得",
                "connection_details": connection_status,
                "sample_data": data[0] if data else None
            }
        else:
            return {
                "status": "error",
                "message": "Google Sheets接続が初期化されていません",
                "connection_details": connection_status
            }
            
    except Exception as e:
        LOGGER.error(f"Google Sheets test error: {e}")
        return {
            "status": "error", 
            "message": f"Google Sheetsテストでエラー: {str(e)}"
        }

@app.get("/test-slack")
async def test_slack_connection() -> Dict[str, Any]:
    """Slack接続テスト"""
    try:
        webhook_url = getattr(settings, 'slack_webhook_url', None)
        
        if not webhook_url:
            return {
                "status": "error", 
                "message": "SLACK_WEBHOOK_URLが設定されていません。"
            }
        
        # テスト通知を送信
        await slack_service.notify_chat_interaction(
            question="🧪 Google Sheets統合テスト",
            answer="Google Sheets統合機能が正常に動作しています。",
            confidence=1.0,
            interaction_type="sheets_integration_test"
        )
        
        return {
            "status": "success", 
            "message": "Google Sheets統合版 Slack通知テストを送信しました",
            "phase": "1.5.1",
            "features": ["conversation_flow", "faq_system", "inquiry_form", "google_sheets"]
        }
        
    except Exception as e:
        LOGGER.error(f"test-slack エラー: {str(e)}")
        return {"status": "error", "message": f"エラーが発生しました: {str(e)}"}

@app.get("/slack-status")
async def slack_status() -> Dict[str, Any]:
    """Slack設定状況確認"""
    webhook_url = getattr(settings, 'slack_webhook_url', None)
    service_enabled = getattr(slack_service, 'enabled', False)
    
    return {
        "phase": "1.5.1",
        "webhook_configured": bool(webhook_url),
        "service_enabled": service_enabled,
        "features": ["conversation_flow", "faq_system", "inquiry_form", "google_sheets"],
        "google_sheets_enabled": getattr(settings, 'is_google_sheets_configured', False),
        "debug_mode": getattr(settings, 'debug', False)
    }

# 静的ファイル配信

static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")
else:
    LOGGER.warning(f"静的ファイルディレクトリが見つかりません: {static_path}")

project_root = Path(__file__).parent.parent
static_paths_to_try = [
    Path(__file__).parent / "static",  # src/static
    project_root / "static",           # project_root/static
    project_root / "src" / "static",   # project_root/src/static
]

static_mounted = False
for static_path in static_paths_to_try:
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
        LOGGER.info(f"✅ Static files mounted from: {static_path}")
        static_mounted = True
        break

if not static_mounted:
    LOGGER.warning("⚠️ 静的ファイルディレクトリが見つかりません")
    LOGGER.info("以下のパスを確認してください:")
    for path in static_paths_to_try:
        LOGGER.info(f"  - {path} (exists: {path.exists()})")

# アプリケーション起動時の初期化
@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の初期化処理"""
    LOGGER.info("=== PIP-Maker Chatbot Phase 1.5.1 起動（Google Sheets統合版）===")
    
    # データソース情報表示
    data_config = settings.get_data_source_config()
    if data_config['google_sheets_enabled']:
        LOGGER.info("📊 Google Sheetsモードで動作")
        LOGGER.info(f"スプレッドシートID: {data_config['sheets_config']['id'][:10]}...")
    else:
        LOGGER.info("📄 CSVモードで動作")
        LOGGER.info(f"CSV パス: {data_config['csv_fallback']}")
    
    LOGGER.info(f"Slack 通知: {'有効' if slack_service.enabled else '無効'}")
    
    try:
        # データの事前読み込み
        data = await data_service.get_qa_data()
        LOGGER.info(f"Q&Aデータ: {len(data)}件を読み込み完了")
        
        # カテゴリー統計を表示
        summary = await conversation_flow_service.get_category_summary()
        for cat_id, info in summary.items():
            LOGGER.info(f"  {info['emoji']} {info['name']}: FAQ {info['faq_count']}件")
        
        # Google Sheets接続状況表示
        if hasattr(data_service, 'get_connection_status'):
            connection_status = data_service.get_connection_status()
            LOGGER.info(f"Google Sheets接続状況: {connection_status}")
            
    except Exception as e:
        LOGGER.error(f"起動時初期化エラー: {e}")
        
        # フォールバック通知
        if hasattr(data_service, 'get_connection_status'):
            await slack_service.notify_data_source_change("startup", f"fallback_to_csv: {str(e)}")

# デバッグ情報出力
if getattr(settings, 'debug', False):
    LOGGER.info("=== デバッグモード（Google Sheets統合版）===")
    LOGGER.info(f"データサービス: {type(data_service).__name__}")
    if hasattr(settings, 'debug_settings'):
        settings.debug_settings()