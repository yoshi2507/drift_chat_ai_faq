# src/ai_services/ai_intent_classifier.py
"""
AI意図分類サービス
質問をカテゴリーに自動分類
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

# 相対インポートを修正
try:
    from ..error_handling import AIServiceException
except ImportError:
    # フォールバック
    class AIServiceException(Exception):
        pass

LOGGER = logging.getLogger(__name__)

class IntentClassificationResult:
    """意図分類結果"""
    def __init__(
        self, 
        category: str, 
        confidence: float, 
        keywords: List[str], 
        specific_intent: str = None,
        method: str = "rule_based"
    ):
        self.category = category
        self.confidence = confidence
        self.keywords = keywords
        self.specific_intent = specific_intent or f"{category}_general"
        self.method = method
        self.timestamp = datetime.now()

class AIIntentClassifier:
    """AI意図分類サービス"""
    
    def __init__(self, openai_service=None):
        self.openai_service = openai_service
        
        # カテゴリー定義
        self.category_definitions = {
            "about": {
                "name": "PIP-Makerとは？",
                "keywords": ["とは", "概要", "説明", "紹介", "特徴", "メリット", "どんな", "なに"],
                "intents": ["overview", "features", "benefits"]
            },
            "cases": {
                "name": "導入事例",
                "keywords": ["事例", "導入", "実績", "成功", "効果", "企業", "会社", "実例"],
                "intents": ["success_stories", "implementation", "results"]
            },
            "features": {
                "name": "機能",
                "keywords": ["機能", "操作", "使い方", "方法", "設定", "画面", "できる", "やり方"],
                "intents": ["how_to", "setup", "operation", "configuration"]
            },
            "pricing": {
                "name": "料金・ライセンス",
                "keywords": ["料金", "価格", "プラン", "ライセンス", "費用", "コスト", "いくら", "値段"],
                "intents": ["pricing_plan", "license_info", "cost_comparison"]
            },
            "other": {
                "name": "その他",
                "keywords": ["サポート", "問い合わせ", "ヘルプ", "その他", "質問", "相談"],
                "intents": ["support", "contact", "general_inquiry"]
            }
        }
    
    async def classify_intent(self, question: str, use_ai: bool = True) -> IntentClassificationResult:
        """質問の意図を分類"""
        
        # AI分類を試行
        if use_ai and self.openai_service:
            try:
                ai_result = await self._ai_classify(question)
                if ai_result.confidence > 0.7:
                    return ai_result
                LOGGER.info(f"AI分類信頼度が低い({ai_result.confidence:.2f})、ルールベースにフォールバック")
            except Exception as e:
                LOGGER.warning(f"AI分類失敗: {e}")
        
        # ルールベース分類
        return self._rule_based_classify(question)
    
    async def _ai_classify(self, question: str) -> IntentClassificationResult:
        """AI による意図分類"""
        
        try:
            result = await self.openai_service.classify_question_intent(question)
            
            return IntentClassificationResult(
                category=result.get("category", "other"),
                confidence=result.get("confidence", 0.5),
                keywords=result.get("keywords", []),
                specific_intent=result.get("specific_intent"),
                method="ai_openai"
            )
            
        except Exception as e:
            raise AIServiceException(f"AI意図分類エラー: {str(e)}")
    
    def _rule_based_classify(self, question: str) -> IntentClassificationResult:
        """ルールベースの意図分類"""
        
        question_lower = question.lower()
        
        # カテゴリー判定
        best_category = "other"
        best_score = 0
        matched_keywords = []
        
        for category, config in self.category_definitions.items():
            keywords = config["keywords"]
            matches = [kw for kw in keywords if kw in question_lower]
            score = len(matches) / len(keywords) if keywords else 0
            
            if score > best_score:
                best_score = score
                best_category = category
                matched_keywords = matches
        
        # 具体的意図の推定
        specific_intent = self._infer_specific_intent(question_lower, best_category)
        
        return IntentClassificationResult(
            category=best_category,
            confidence=min(best_score * 2, 1.0),  # スコア調整
            keywords=matched_keywords,
            specific_intent=specific_intent,
            method="rule_based"
        )
    
    def _infer_specific_intent(self, question_lower: str, category: str) -> str:
        """具体的意図を推定"""
        
        intent_patterns = {
            "pricing": {
                "比較": "pricing_comparison",
                "プラン": "pricing_plan",
                "ライセンス": "license_info",
                "費用": "cost_estimation"
            },
            "features": {
                "使い方": "features_howto",
                "設定": "features_setup",
                "操作": "features_operation",
                "画面": "features_interface"
            },
            "cases": {
                "事例": "success_stories",
                "導入": "implementation",
                "効果": "results"
            },
            "about": {
                "特徴": "overview_features",
                "メリット": "overview_benefits",
                "概要": "overview_general"
            }
        }
        
        if category in intent_patterns:
            for pattern, intent in intent_patterns[category].items():
                if pattern in question_lower:
                    return intent
        
        return f"{category}_general"
    
    def get_category_info(self, category: str) -> Optional[Dict[str, Any]]:
        """カテゴリー情報を取得"""
        return self.category_definitions.get(category)
    
    def get_all_categories(self) -> List[Dict[str, str]]:
        """全カテゴリー情報を取得"""
        return [
            {
                "id": cat_id,
                "name": config["name"],
                "keywords": config["keywords"]
            }
            for cat_id, config in self.category_definitions.items()
        ]