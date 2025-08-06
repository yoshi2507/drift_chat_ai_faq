# src/error_handling.py - エラーハンドリング実装

"""
PIP-Maker チャットボット エラーハンドリング
回答精度向上開発に必要な最小限の実装
"""

import logging
import traceback
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger(__name__)

class ChatBotException(Exception):
    """チャットボット基底例外"""
    def __init__(self, message: str, error_code: str = "GENERAL_ERROR", details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.now()
        super().__init__(message)

class DataSourceException(ChatBotException):
    """データソース関連例外"""
    def __init__(self, message: str, source_type: str = "unknown"):
        super().__init__(
            message=message, 
            error_code="DATA_SOURCE_ERROR",
            details={"source_type": source_type}
        )

class SearchException(ChatBotException):
    """検索関連例外"""
    def __init__(self, message: str, query: str = ""):
        super().__init__(
            message=message,
            error_code="SEARCH_ERROR", 
            details={"query": query}
        )

class ConversationFlowException(ChatBotException):
    """対話フロー関連例外"""
    def __init__(self, message: str, conversation_id: str = "", state: str = ""):
        super().__init__(
            message=message,
            error_code="CONVERSATION_ERROR",
            details={"conversation_id": conversation_id, "state": state}
        )

class AIServiceException(ChatBotException):
    """AI サービス関連例外"""
    def __init__(self, message: str, service_name: str = "openai", error_type: str = "general"):
        super().__init__(
            message=message,
            error_code="AI_SERVICE_ERROR",
            details={"service": service_name, "error_type": error_type}
        )

def log_error_with_context(
    error: Exception, 
    context: Dict[str, Any] = None,
    user_friendly_message: str = None
) -> str:
    """
    エラーを詳細ログに記録し、ユーザー向けメッセージを返す
    """
    error_id = f"ERR_{uuid.uuid4().hex[:8]}"
    
    # 詳細ログ出力（開発者向け）
    log_data = {
        "error_id": error_id,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context or {},
        "traceback": traceback.format_exc()
    }
    
    LOGGER.error(f"🚨 エラー発生 [ID: {error_id}]: {error}")
    LOGGER.debug(f"詳細情報: {log_data}")
    
    # ユーザー向けメッセージ
    if user_friendly_message:
        return user_friendly_message
    elif isinstance(error, ChatBotException):
        return error.message
    else:
        return "システムエラーが発生しました。しばらく待ってから再度お試しください。"

def create_error_response(
    error: Exception,
    context: Dict[str, Any] = None,
    fallback_message: str = "申し訳ございません。担当者までお問い合わせください。"
) -> Dict[str, Any]:
    """
    API レスポンス用のエラー辞書を作成
    """
    user_message = log_error_with_context(error, context)
    
    return {
        "error": user_message,
        "fallback_message": fallback_message,
        "error_type": type(error).__name__,
        "timestamp": datetime.now().isoformat(),
        "support_message": "エラーが継続する場合は、お問い合わせフォームからご連絡ください。"
    }

# FastAPI 例外ハンドラー
async def chatbot_exception_handler(request: Request, exc: ChatBotException) -> JSONResponse:
    """ChatBotException 用ハンドラー"""
    error_response = create_error_response(
        exc, 
        context={
            "endpoint": str(request.url.path),
            "method": request.method,
            "error_code": exc.error_code,
            "details": exc.details
        }
    )
    return JSONResponse(status_code=500, content=error_response)

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """一般例外用ハンドラー"""
    error_response = create_error_response(
        exc,
        context={
            "endpoint": str(request.url.path),
            "method": request.method,
            "user_agent": request.headers.get("user-agent", "unknown")
        },
        fallback_message="予期しないエラーが発生しました。"
    )
    return JSONResponse(status_code=500, content=error_response)

class VectorSearchException(ChatBotException):
    """ベクトル検索関連例外"""
    def __init__(self, message: str, collection_name: str = ""):
        super().__init__(
            message=message,
            error_code="VECTOR_SEARCH_ERROR",
            details={"collection": collection_name}
        )

class CategoryException(ChatBotException):
    """カテゴリー処理関連例外"""
    def __init__(self, message: str, category: str = "", operation: str = ""):
        super().__init__(
            message=message,
            error_code="CATEGORY_ERROR",
            details={"category": category, "operation": operation}
        )

# 使用例サンプル（参考用）
"""
# app.py での使用方法

from .error_handling import *

# 例外ハンドラー登録
app.add_exception_handler(ChatBotException, chatbot_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# SearchService での使用例
class SearchService:
    async def search(self, query: str) -> SearchResponse:
        try:
            data = await self.data_service.get_qa_data()
        except Exception as e:
            raise DataSourceException(
                f"Q&Aデータの取得に失敗しました",
                source_type=type(self.data_service).__name__
            ) from e
        
        if not data:
            raise SearchException(
                "該当する回答が見つかりませんでした。より具体的なキーワードでお試しください。",
                query=query
            )

# ConversationFlowService での使用例  
class ConversationFlowService:
    async def select_category(self, conversation_id: str, category_id: str):
        try:
            # 処理...
            pass
        except Exception as e:
            raise ConversationFlowException(
                f"カテゴリー選択でエラーが発生しました",
                conversation_id=conversation_id,
                state="category_selection"
            ) from e
"""