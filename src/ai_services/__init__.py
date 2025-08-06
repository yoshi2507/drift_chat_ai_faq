# src/ai_services/__init__.py
"""
AI統合サービス モジュール
Phase 2: OpenAI統合とカテゴリー対応検索
"""

# Phase 2で利用可能なAIサービスをエクスポート
__version__ = "2.0.0"
__author__ = "PIP-Maker Development Team"

# 利用可能なクラス/関数を定義
__all__ = [
    "OpenAIService",
    "OpenAIConfig", 
    "AIIntentClassifier",
    "IntentClassificationResult",
    "CategoryAwareSearchEngine"
]

# 条件付きインポート（依存関係がない場合でもエラーにならない）
try:
    from .openai_service import OpenAIService, OpenAIConfig
    OPENAI_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ OpenAI service import failed: {e}")
    OPENAI_AVAILABLE = False
    OpenAIService = None
    OpenAIConfig = None

try:
    from .ai_intent_classifier import AIIntentClassifier, IntentClassificationResult
    INTENT_CLASSIFIER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ AI Intent Classifier import failed: {e}")
    INTENT_CLASSIFIER_AVAILABLE = False
    AIIntentClassifier = None
    IntentClassificationResult = None

try:
    from .category_aware_search import CategoryAwareSearchEngine
    CATEGORY_SEARCH_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Category Aware Search import failed: {e}")
    CATEGORY_SEARCH_AVAILABLE = False
    CategoryAwareSearchEngine = None

# モジュール情報
def get_availability_status():
    """各AIサービスの利用可能性を確認"""
    return {
        "openai_service": OPENAI_AVAILABLE,
        "intent_classifier": INTENT_CLASSIFIER_AVAILABLE,
        "category_search": CATEGORY_SEARCH_AVAILABLE,
        "overall_ai_ready": OPENAI_AVAILABLE and INTENT_CLASSIFIER_AVAILABLE and CATEGORY_SEARCH_AVAILABLE
    }