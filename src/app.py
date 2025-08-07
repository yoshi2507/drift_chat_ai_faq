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
import aiohttp
import asyncio
import json
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .source_citation_service import SourceCitationService, SourceType, SourceCitation

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

# Phase 3.1: 根拠URL表示サービス
citation_service = SourceCitationService()
LOGGER.info("✅ SourceCitationService initialized")

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
    
    # === Phase 3.1: 新フィールド ===
    citations: Optional[Dict[str, Any]] = None  # 引用情報
    source_count: Optional[int] = None          # ソース数
    verified_sources: Optional[int] = None      # 検証済みソース数


class FeedbackRequest(BaseModel):
    conversation_id: str = Field(..., description="会話の一意識別子")
    rating: str = Field(..., description="positive または negative")
    comment: Optional[str] = Field(None, description="追加コメント")

# Slack通知サービス
class SlackNotificationService:
    """Slack通知送信用のサービス（実際の送信機能付き）"""

    def __init__(self, webhook_url: Optional[str] = None) -> None:
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)
        
        # 通知統計（デバッグ用）
        self.notification_count = 0
        self.successful_notifications = 0
        self.failed_notifications = 0
        self.last_notification_time = None
        
        if self.enabled:
            LOGGER.info(f"✅ Slack通知サービス: 有効")
            LOGGER.info(f"   Webhook URL: {webhook_url[:50]}...")
        else:
            LOGGER.info("⚠️ Slack通知サービス: 無効 (Webhook URLが設定されていません)")

    async def _send_to_slack(self, message: dict) -> bool:
        """Slackにメッセージを実際に送信"""
        if not self.enabled:
            LOGGER.debug("Slack通知: 無効のためスキップ")
            return False
        
        self.notification_count += 1
        
        try:
            LOGGER.info(f"📤 Slack通知送信開始 (#{self.notification_count})")
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.webhook_url,
                    json=message,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    status = response.status
                    response_text = await response.text()
                    
                    if status == 200:
                        self.successful_notifications += 1
                        self.last_notification_time = datetime.now()
                        LOGGER.info(f"✅ Slack通知送信成功 (#{self.notification_count})")
                        return True
                    else:
                        self.failed_notifications += 1
                        LOGGER.error(f"❌ Slack通知送信失敗 (#{self.notification_count}) - HTTP {status}: {response_text}")
                        return False
                        
        except asyncio.TimeoutError:
            self.failed_notifications += 1
            LOGGER.error(f"⏰ Slack通知タイムアウト (#{self.notification_count})")
            return False
        except aiohttp.ClientConnectorError as e:
            self.failed_notifications += 1
            LOGGER.error(f"🔌 Slack通知接続エラー (#{self.notification_count}): {e}")
            return False
        except Exception as e:
            self.failed_notifications += 1
            LOGGER.error(f"❌ Slack通知予期しないエラー (#{self.notification_count}): {e}")
            return False

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
        """チャット対話の通知（実際の送信機能付き）"""
        
        # ログ出力（従来通り）
        ai_info = "🤖 AI生成" if ai_generated else "📊 データベース"
        sources_info = f"({len(sources_used)}件のソース)" if sources_used else ""
        
        LOGGER.info(
            f"[Slack] {ai_info} {interaction_type}: question={question[:50]}{'...' if len(question) > 50 else ''}, "
            f"answer={answer[:50]}{'...' if len(answer) > 50 else ''}, confidence={confidence:.2f}, "
            f"category={category} {sources_info}"
        )
        
        if not self.enabled:
            return
        
        # 実際のSlackメッセージを構築・送信
        try:
            # 信頼度の色分け
            confidence_color = "#28a745" if confidence >= 0.8 else "#ffc107" if confidence >= 0.6 else "#dc3545"
            
            message = {
                "attachments": [
                    {
                        "color": confidence_color,
                        "blocks": [
                            {
                                "type": "header",
                                "text": {
                                    "type": "plain_text",
                                    "text": f"🗨️ 新しいチャット対話 {ai_info}"
                                }
                            },
                            {
                                "type": "section",
                                "fields": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*🙋 質問:*\n{question[:200]}{'...' if len(question) > 200 else ''}"
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*🤖 回答:*\n{answer[:300]}{'...' if len(answer) > 300 else ''}"
                                    }
                                ]
                            },
                            {
                                "type": "section",
                                "fields": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*📊 信頼度:* {confidence:.0%}"
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*🏷️ カテゴリー:* {category}"
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*🔍 検索タイプ:* {interaction_type}"
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*📚 ソース:* {len(sources_used)}件"
                                    }
                                ]
                            },
                            {
                                "type": "context",
                                "elements": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
            
            success = await self._send_to_slack(message)
            
            if success:
                LOGGER.info("✅ チャット対話のSlack通知が正常に送信されました")
            else:
                LOGGER.warning("⚠️ チャット対話のSlack通知送信に失敗しました")
                
        except Exception as e:
            LOGGER.error(f"❌ チャット対話通知処理でエラー: {e}")

    async def notify_inquiry_submission(self, inquiry_data: Dict[str, str]) -> None:
        """お問い合わせ送信時の通知（実際の送信機能付き）"""
        try:
            company = inquiry_data.get('company', '')
            name = inquiry_data.get('name', '')
            email = inquiry_data.get('email', '')
            inquiry = inquiry_data.get('inquiry', '')
            
            # ログ出力（従来通り）
            LOGGER.info(f"[Slack] 🔥 新しいお問い合わせ: {name} ({company}) - {email}")
            LOGGER.info(f"[Slack] 内容: {inquiry[:100]}{'...' if len(inquiry) > 100 else ''}")
            
            if not self.enabled:
                return
            
            # 重要度の高い通知なので目立つデザイン
            message = {
                "attachments": [
                    {
                        "color": "#ff6b35",  # オレンジ色（重要）
                        "blocks": [
                            {
                                "type": "header",
                                "text": {
                                    "type": "plain_text",
                                    "text": "🔥 新しいお問い合わせが届きました！"
                                }
                            },
                            {
                                "type": "section",
                                "fields": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*👤 お名前:*\n{name}"
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*🏢 会社名:*\n{company}"
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*📧 メール:*\n{email}"
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*⏰ 受信時刻:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                    }
                                ]
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"*💬 お問い合わせ内容:*\n```{inquiry}```"
                                }
                            },
                            {
                                "type": "actions",
                                "elements": [
                                    {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "📧 メールで返信"
                                        },
                                        "url": f"mailto:{email}?subject=Re: PIP-Makerについてのお問い合わせ",
                                        "style": "primary"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
            
            success = await self._send_to_slack(message)
            
            if success:
                LOGGER.info("✅ お問い合わせのSlack通知が正常に送信されました")
            else:
                LOGGER.warning("⚠️ お問い合わせのSlack通知送信に失敗しました")
                
        except Exception as e:
            LOGGER.error(f"❌ お問い合わせ通知処理でエラー: {e}")

    async def notify_faq_selection(
        self, 
        faq_id: str, 
        question: str, 
        category: str,
        user_info: Optional[Dict[str, str]] = None
    ) -> None:
        """FAQ選択の通知"""
        LOGGER.info(f"[Slack] FAQ選択: faq_id={faq_id}, category={category}, question={question}")
        
        if not self.enabled:
            return
        
        try:
            message = {
                "attachments": [
                    {
                        "color": "#36a64f",  # 緑色
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"📋 *FAQ選択*\n*ID:* {faq_id}\n*カテゴリー:* {category}\n*質問:* {question[:100]}{'...' if len(question) > 100 else ''}"
                                }
                            }
                        ]
                    }
                ]
            }
            
            await self._send_to_slack(message)
            
        except Exception as e:
            LOGGER.error(f"❌ FAQ選択通知でエラー: {e}")

    async def notify_negative_feedback(self, feedback: Dict[str, str]) -> None:
        """ネガティブフィードバックの通知"""
        LOGGER.info(f"[Slack] ⚠️ ネガティブフィードバック: {feedback}")
        
        if not self.enabled:
            return
        
        try:
            message = {
                "attachments": [
                    {
                        "color": "#dc3545",  # 赤色
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"⚠️ *ネガティブフィードバック*\n会話ID: {feedback.get('conversation_id', 'N/A')}\nコメント: {feedback.get('comment', 'なし')}"
                                }
                            }
                        ]
                    }
                ]
            }
            
            await self._send_to_slack(message)
            
        except Exception as e:
            LOGGER.error(f"❌ ネガティブフィードバック通知でエラー: {e}")

    async def notify_ai_service_status(self, service_name: str, status: str, details: Dict = None) -> None:
        """AIサービス状態変更の通知"""
        LOGGER.info(f"[Slack] 🤖 AIサービス状態: {service_name} - {status}")
        
        if not self.enabled:
            return
        
        try:
            color = "#28a745" if status == "RELOADED" else "#ffc107"
            
            message = {
                "attachments": [
                    {
                        "color": color,
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"🤖 *AIサービス状態変更*\nサービス: {service_name}\nステータス: {status}\n詳細: {details if details else 'なし'}"
                                }
                            }
                        ]
                    }
                ]
            }
            
            await self._send_to_slack(message)
            
        except Exception as e:
            LOGGER.error(f"❌ AIサービス状態通知でエラー: {e}")

    def get_notification_stats(self) -> Dict[str, any]:
        """通知統計を取得"""
        return {
            "enabled": self.enabled,
            "webhook_configured": bool(self.webhook_url),
            "total_notifications": self.notification_count,
            "successful_notifications": self.successful_notifications,
            "failed_notifications": self.failed_notifications,
            "success_rate": round(self.successful_notifications / max(self.notification_count, 1) * 100, 1),
            "last_notification_time": self.last_notification_time.isoformat() if self.last_notification_time else None
        }

    async def test_notification(self) -> bool:
        """テスト通知を送信"""
        if not self.enabled:
            LOGGER.warning("Slack通知が無効のため、テスト通知を送信できません")
            return False
        
        test_message = {
            "attachments": [
                {
                    "color": "#36a64f",
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": "🧪 テスト通知"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*PIP-Maker チャットボット*\nSlack通知機能のテストメッセージです。\n送信時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            }
                        }
                    ]
                }
            ]
        }
        
        return await self._send_to_slack(test_message)

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
    
    # Phase 3.1: 引用システム情報を追加
    health_info["phase3_features"] = {
        "citation_service": citation_service is not None,
        "citation_stats": citation_service.get_citation_stats() if citation_service else None
    }
    
    return health_info

@app.post("/api/search", response_model=SearchResponse)
async def search_endpoint(query: SearchQuery) -> SearchResponse:
    """検索エンドポイント（Phase 3.1: 根拠URL表示機能統合版）"""
    
    # 入力バリデーション
    if not query.question:
        raise SearchException("質問を入力してください。", query="")
    
    question_trimmed = query.question.strip()
    if not question_trimmed:
        raise SearchException("質問を入力してください。", query=query.question)
    
    if len(question_trimmed) < 2:
        raise SearchException("もう少し詳しい質問を入力してください。", query=question_trimmed)
    
    search_start_time = datetime.now()
    
    # 検索実行（既存の検索ロジックは保持）
    search_response = None
    qa_results = []  # Q&Aデータを保存
    
    # === AI統合検索 ===
    if category_search_engine and query.use_category_optimization:
        try:
            LOGGER.info(f"🤖 AI統合検索開始: {question_trimmed}")
            
            conversation_context = {
                "conversation_id": query.conversation_id,
                "selected_category": query.category
            } if query.conversation_id else None
            
            result = await category_search_engine.search_with_category_context(
                query=question_trimmed,
                selected_category=query.category,
                conversation_context=conversation_context,
                use_ai_generation=query.use_ai_generation and bool(openai_service)
            )
            
            # Q&Aデータを取得（引用用）
            if hasattr(category_search_engine, 'get_source_qa_data'):
                qa_results = await category_search_engine.get_source_qa_data(question_trimmed, query.category)
            elif data_service:
                try:
                    all_qa_data = await data_service.get_qa_data()
                    # 簡単なフィルタリング
                    qa_results = [
                        item for item in all_qa_data 
                        if query.category is None or item.get('category', '').lower() == query.category.lower()
                    ][:5]  # 最大5件
                except Exception as e:
                    LOGGER.warning(f"Q&Aデータ取得失敗: {e}")
                    qa_results = []
            
            search_response = SearchResponse(
                answer=result['answer'],
                confidence=result['confidence'],
                source=result.get('sources_used', [None])[0],
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
            
            LOGGER.info(f"✅ AI統合検索成功: 信頼度={result['confidence']:.2f}")
            
        except Exception as ai_error:
            LOGGER.warning(f"⚠️ AI統合検索失敗: {ai_error}")
            search_response = None
    
    # === 基本検索（フォールバック） ===
    if not search_response and basic_search_service:
        try:
            LOGGER.info(f"📄 基本検索開始（フォールバック）: {question_trimmed}")
            
            result = await basic_search_service.search(
                question_trimmed,
                query.category,
                exclude_faqs=False
            )
            
            # Q&Aデータを取得（引用用）
            if data_service:
                try:
                    all_qa_data = await data_service.get_qa_data()
                    qa_results = [
                        item for item in all_qa_data 
                        if question_trimmed.lower() in item.get('question', '').lower() or
                        question_trimmed.lower() in item.get('answer', '').lower()
                    ][:3]  # 最大3件
                except Exception as e:
                    LOGGER.warning(f"Q&Aデータ取得失敗: {e}")
                    qa_results = []
            
            search_time = (datetime.now() - search_start_time).total_seconds()
            
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
            
            LOGGER.info(f"✅ 基本検索成功（フォールバック）: 信頼度={result.confidence:.2f}")
            
        except Exception as exc:
            LOGGER.error(f"❌ 基本検索エラー: {exc}")
            raise SearchException("検索処理中にエラーが発生しました。") from exc
    
    if not search_response:
        raise SearchException("検索サービスが利用できません。システム管理者にお問い合わせください。")
    
    # === Phase 3.1: 根拠URL表示機能の統合 ===
    try:
        LOGGER.info(f"📚 引用情報生成開始: {len(qa_results)}件のQ&Aデータ")
        
        # 包括的な引用情報を取得
        citations = await citation_service.get_comprehensive_citations(
            query=question_trimmed,
            category=query.category or "unknown",
            qa_results=qa_results
        )
        
        # 検索結果に引用情報を追加
        search_response.citations = citations
        search_response.source_count = citations.get('total_sources', 0)
        
        # 検証済みソース数を計算
        verified_count = 0
        for citation in citations.get('citations', []):
            if citation.get('verified'):
                verified_count += 1
        search_response.verified_sources = verified_count
        
        LOGGER.info(f"✅ 引用情報生成完了: {citations['total_sources']}件のソース、{verified_count}件検証済み")
        
    except Exception as citation_error:
        LOGGER.warning(f"⚠️ 引用情報生成失敗: {citation_error}")
        # 引用情報の生成に失敗しても検索結果は返す
        search_response.citations = {
            "citations": [],
            "total_sources": 0,
            "showing": 0,
            "has_more": False
        }
        search_response.source_count = 0
        search_response.verified_sources = 0
    
    # Slack通知（引用情報付き）
    try:
        citation_summary = f"引用: {search_response.source_count}件" if search_response.source_count else "引用なし"
        
        await slack_service.notify_chat_interaction(
            question=question_trimmed,
            answer=search_response.answer,
            confidence=search_response.confidence,
            interaction_type=search_response.method,
            ai_generated=search_response.ai_generated,
            category=search_response.category or "unknown",
            sources_used=search_response.sources_used + [citation_summary]
        )
    except Exception as slack_error:
        LOGGER.warning(f"Slack通知失敗: {slack_error}")
    
    return search_response

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

# === Phase 3.1: 引用システムデバッグエンドポイント ===

@app.get("/debug/citations")
async def debug_citations() -> Dict[str, Any]:
    """引用システムのデバッグ情報"""
    try:
        stats = citation_service.get_citation_stats()
        
        # サンプル引用情報を生成
        sample_qa = {
            'question': 'PIP-Makerとは何ですか？',
            'answer': 'PIP-Makerは効率的なソフトウェア開発を支援するツールです。',
            'source': 'https://www.pip-maker.com/product 製品概要ページ',
            'category': 'about'
        }
        
        sample_citations = citation_service.extract_citations_from_qa_data(sample_qa)
        sample_display = citation_service.format_citations_for_display(sample_citations)
        
        return {
            "citation_service_stats": stats,
            "sample_citation_extraction": {
                "input": sample_qa,
                "extracted_citations": [c.to_dict() for c in sample_citations],
                "formatted_display": sample_display
            },
            "pip_maker_url_suggestions": [
                c.to_dict() for c in citation_service.generate_pip_maker_related_urls(
                    "PIP-Makerの機能について教えてください", "features"
                )
            ],
            "system_info": {
                "cache_enabled": True,
                "cache_duration_hours": citation_service.cache_duration.total_seconds() / 3600,
                "pip_maker_patterns": citation_service.pip_maker_patterns
            }
        }
    except Exception as e:
        return {
            "error": str(e),
            "citation_service_available": citation_service is not None
        }

@app.post("/admin/citations/verify-urls")
async def verify_citations_urls() -> Dict[str, Any]:
    """管理者用：キャッシュ済みURLの一括検証"""
    try:
        verified_results = []
        
        for url in list(citation_service.url_cache.keys())[:10]:  # 最大10件
            is_accessible, status = await citation_service.verify_url_accessibility(url)
            verified_results.append({
                "url": url,
                "accessible": is_accessible,
                "status": status
            })
        
        stats = citation_service.get_citation_stats()
        
        return {
            "verification_results": verified_results,
            "cache_stats": stats,
            "message": f"{len(verified_results)}件のURLを検証しました"
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "message": "URL検証中にエラーが発生しました"
        }

@app.get("/debug/citations/url-patterns")
async def debug_citation_url_patterns() -> Dict[str, Any]:
    """引用URLパターンのテスト"""
    test_urls = [
        "https://www.pip-maker.com/product",
        "https://info.pip-maker.com/manual/pdf/PIP-Maker_creator.pdf",
        "https://support.pip-maker.com/faq",
        "https://blog.pip-maker.com/news/update",
        "https://example.com/unknown"
    ]
    
    pattern_results = []
    for url in test_urls:
        source_type = citation_service.classify_source_type(url)
        pattern_results.append({
            "url": url,
            "classified_type": source_type.value,
            "type_label": citation_service._get_source_type_label(source_type),
            "icon": citation_service._get_source_icon(source_type)
        })
    
    return {
        "pip_maker_patterns": citation_service.pip_maker_patterns,
        "pattern_test_results": pattern_results,
        "source_type_mapping": {
            "INTERNAL_DATA": "内部データ",
            "OFFICIAL_WEBSITE": "公式サイト", 
            "PDF_MANUAL": "PDFマニュアル",
            "FAQ": "よくある質問",
            "DOCUMENTATION": "ドキュメント",
            "BLOG_POST": "ブログ記事",
            "UNKNOWN": "参考資料"
        }
    }

@app.post("/admin/citations/test-extraction")
async def test_citation_extraction(qa_item: Dict[str, str]) -> Dict[str, Any]:
    """管理者用：引用抽出テスト"""
    try:
        # 引用情報を抽出
        citations = citation_service.extract_citations_from_qa_data(qa_item)
        
        # 表示用にフォーマット
        formatted_display = citation_service.format_citations_for_display(citations)
        
        # URL検証（非同期）
        enhanced_citations = await citation_service.enhance_citations_with_verification(citations)
        
        return {
            "input_qa": qa_item,
            "extracted_citations": [c.to_dict() for c in citations],
            "enhanced_citations": [c.to_dict() for c in enhanced_citations],
            "formatted_display": formatted_display,
            "extraction_success": len(citations) > 0
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "input_qa": qa_item
        }

@app.get("/debug/citations/cache-status")
async def debug_citation_cache_status() -> Dict[str, Any]:
    """引用システムのキャッシュ状態確認"""
    cache_details = []
    
    for url, (accessible, timestamp) in citation_service.url_cache.items():
        age_seconds = (datetime.now() - timestamp).total_seconds()
        is_expired = age_seconds > citation_service.cache_duration.total_seconds()
        
        cache_details.append({
            "url": url,
            "accessible": accessible,
            "cached_at": timestamp.isoformat(),
            "age_seconds": age_seconds,
            "age_hours": round(age_seconds / 3600, 2),
            "is_expired": is_expired
        })
    
    # 最新10件のみ表示
    cache_details.sort(key=lambda x: x["cached_at"], reverse=True)
    
    stats = citation_service.get_citation_stats()
    
    return {
        "cache_overview": stats,
        "cache_duration_hours": citation_service.cache_duration.total_seconds() / 3600,
        "recent_cached_urls": cache_details[:10],
        "total_cached_urls": len(cache_details),
        "expired_urls_count": len([c for c in cache_details if c["is_expired"]])
    }

@app.delete("/admin/citations/clear-cache")
async def clear_citation_cache() -> Dict[str, Any]:
    """管理者用：引用キャッシュのクリア"""
    try:
        original_cache_size = len(citation_service.url_cache)
        citation_service.url_cache.clear()
        
        LOGGER.info(f"引用キャッシュをクリア: {original_cache_size}件のURLを削除")
        
        return {
            "status": "success",
            "message": f"{original_cache_size}件のキャッシュをクリアしました",
            "cleared_count": original_cache_size,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        LOGGER.error(f"キャッシュクリアエラー: {e}")
        return {
            "status": "error",
            "message": f"キャッシュクリアに失敗: {str(e)}"
        }

@app.post("/admin/citations/bulk-verify")
async def bulk_verify_pip_maker_urls() -> Dict[str, Any]:
    """管理者用：PIP-Maker関連URLの一括検証"""
    pip_maker_urls = [
        "https://www.pip-maker.com/",
        "https://www.pip-maker.com/product",
        "https://www.pip-maker.com/features", 
        "https://www.pip-maker.com/pricing",
        "https://www.pip-maker.com/case-studies",
        "https://info.pip-maker.com/manual/pdf/PIP-Maker_creator.pdf",
        "https://support.pip-maker.com/",
        "https://blog.pip-maker.com/"
    ]
    
    verification_results = []
    successful_verifications = 0
    
    for url in pip_maker_urls:
        try:
            is_accessible, status = await citation_service.verify_url_accessibility(url)
            
            if is_accessible:
                successful_verifications += 1
            
            verification_results.append({
                "url": url,
                "accessible": is_accessible,
                "status": status,
                "source_type": citation_service.classify_source_type(url).value
            })
            
        except Exception as e:
            verification_results.append({
                "url": url,
                "accessible": False,
                "status": f"エラー: {str(e)}",
                "source_type": "unknown"
            })
    
    return {
        "verification_summary": {
            "total_urls": len(pip_maker_urls),
            "successful_verifications": successful_verifications,
            "success_rate": round(successful_verifications / len(pip_maker_urls) * 100, 1)
        },
        "verification_results": verification_results,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/admin/citations/verify-urls")
async def verify_citations_urls() -> Dict[str, Any]:
    """管理者用：キャッシュ済みURLの一括検証"""
    try:
        verified_results = []
        
        for url in list(citation_service.url_cache.keys())[:10]:  # 最大10件
            is_accessible, status = await citation_service.verify_url_accessibility(url)
            verified_results.append({
                "url": url,
                "accessible": is_accessible,
                "status": status
            })
        
        stats = citation_service.get_citation_stats()
        
        return {
            "verification_results": verified_results,
            "cache_stats": stats,
            "message": f"{len(verified_results)}件のURLを検証しました"
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "message": "URL検証中にエラーが発生しました"
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

# app.pyの最後に以下のコードを追加

# 静的ファイル配信の設定
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# 静的ファイルのパスを設定
static_dir = Path(__file__).parent / "static"

# 静的ファイルディレクトリが存在する場合のみマウント
if static_dir.exists():
    app.mount("/src/static", StaticFiles(directory=str(static_dir)), name="static")
    LOGGER.info(f"✅ 静的ファイル配信を設定: {static_dir}")
else:
    LOGGER.warning(f"⚠️ 静的ファイルディレクトリが見つかりません: {static_dir}")

# プロジェクトルートの静的ファイルも配信（index.htmlと同じ階層）
project_root = Path(__file__).parent.parent
if (project_root / "static").exists():
    app.mount("/static", StaticFiles(directory=str(project_root / "static")), name="root_static")
    LOGGER.info(f"✅ ルート静的ファイル配信を設定: {project_root / 'static'}")

# 個別ファイルの配信（script.js, style.css）
src_static_dir = Path(__file__).parent / "static"
if src_static_dir.exists():
    app.mount("/script.js", StaticFiles(directory=str(src_static_dir)), name="script")
    app.mount("/style.css", StaticFiles(directory=str(src_static_dir)), name="style")

# デバッグ用: 静的ファイルパスの確認
@app.get("/debug/static-paths")
async def debug_static_paths():
    """静的ファイルパスのデバッグ情報"""
    project_root = Path(__file__).parent.parent
    src_static = Path(__file__).parent / "static"
    
    return {
        "project_root": str(project_root),
        "src_static_dir": str(src_static),
        "src_static_exists": src_static.exists(),
        "script_js_exists": (src_static / "script.js").exists(),
        "style_css_exists": (src_static / "style.css").exists(),
        "project_structure": {
            "files_in_src": list(f.name for f in src_static.iterdir()) if src_static.exists() else [],
            "files_in_root": list(f.name for f in project_root.iterdir() if f.is_file())
        }
    }