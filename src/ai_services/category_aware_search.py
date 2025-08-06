# src/ai_services/category_aware_search.py
"""
カテゴリー対応検索エンジン
意図分類に基づく最適化された検索
"""

import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime

# TYPE_CHECKINGを使用して循環インポートを回避
if TYPE_CHECKING:
    from .ai_intent_classifier import AIIntentClassifier

# 相対インポートを修正
try:
    from ..error_handling import SearchException, AIServiceException
except ImportError:
    # フォールバック
    class SearchException(Exception):
        pass
    class AIServiceException(Exception):
        pass

LOGGER = logging.getLogger(__name__)

class CategoryAwareSearchEngine:
    """カテゴリー対応検索エンジン"""
    
    def __init__(
        self, 
        data_service, 
        intent_classifier: Optional["AIIntentClassifier"] = None,  # 文字列として型指定
        openai_service=None,
        basic_search_service=None
    ):
        self.data_service = data_service
        self.intent_classifier = intent_classifier
        self.openai_service = openai_service
        self.basic_search_service = basic_search_service
        
        # 設定
        self.category_confidence_boost = 0.15
        self.early_termination_threshold = 0.8
        self.ai_generation_threshold = 0.6
        
        LOGGER.info("カテゴリー対応検索エンジンが初期化されました")
    
    async def search_with_category_context(
        self,
        query: str,
        selected_category: Optional[str] = None,
        conversation_context: Optional[Dict] = None,
        use_ai_generation: bool = True
    ) -> Dict[str, Any]:
        """カテゴリーコンテキストを使用した検索"""
        
        start_time = datetime.now()
        
        # Step 1: 意図分類
        if not selected_category and self.intent_classifier:
            try:
                intent_result = await self.intent_classifier.classify_intent(
                    query, 
                    use_ai=True
                )
                selected_category = intent_result.category
                intent_confidence = intent_result.confidence
                
                LOGGER.info(f"意図分類結果: {selected_category} (信頼度: {intent_confidence:.2f})")
                
            except Exception as e:
                LOGGER.warning(f"意図分類失敗: {e}")
                selected_category = "other"
                intent_confidence = 0.5
        else:
            intent_confidence = 1.0  # 明示的にカテゴリーが指定された場合
        
        # Step 2: カテゴリー内検索
        category_results = await self._search_within_category(
            query, 
            selected_category
        )
        
        # Step 3: 結果評価と最適化
        best_result = self._evaluate_and_optimize_results(
            category_results,
            query,
            selected_category,
            intent_confidence
        )
        
        # Step 4: AI回答生成（必要に応じて）
        if (use_ai_generation and 
            self.openai_service and 
            best_result['confidence'] < self.ai_generation_threshold):
            
            try:
                ai_enhanced_result = await self._enhance_with_ai(
                    query,
                    best_result,
                    category_results,
                    selected_category
                )
                best_result = ai_enhanced_result
                
            except Exception as e:
                LOGGER.warning(f"AI回答生成失敗: {e}")
        
        # Step 5: 結果のパッケージング
        search_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'answer': best_result['answer'],
            'confidence': best_result['confidence'],
            'category': selected_category,
            'sources_used': best_result.get('sources', []),
            'category_optimized': True,
            'ai_generated': best_result.get('ai_generated', False),
            'search_time': search_time,
            'intent_confidence': intent_confidence,
            'method': 'category_aware'
        }
    
    async def _search_within_category(
        self, 
        query: str, 
        category: str
    ) -> List[Dict[str, Any]]:
        """カテゴリー内での検索"""
        
        try:
            # カテゴリーフィルター付きでQ&Aデータを検索
            if hasattr(self.data_service, 'search_qa_data'):
                data = await self.data_service.search_qa_data(
                    query=query,
                    category=category,
                    include_faqs_only=False
                )
            else:
                # フォールバック：全データを取得してフィルタリング
                all_data = await self.data_service.get_qa_data()
                data = [
                    row for row in all_data 
                    if row.get('category', '').lower() == category.lower()
                ]
            
            # 基本検索サービスも利用（フォールバック）
            if self.basic_search_service and not data:
                basic_result = await self.basic_search_service.search(
                    query=query,
                    category=category,
                    exclude_faqs=False
                )
                
                if basic_result:
                    data = [{
                        'question': basic_result.question,
                        'answer': basic_result.answer,
                        'confidence': basic_result.confidence,
                        'source': basic_result.source,
                        'category': category
                    }]
            
            return data
            
        except Exception as e:
            LOGGER.error(f"カテゴリー内検索エラー: {e}")
            return []
    
    def _evaluate_and_optimize_results(
        self,
        results: List[Dict[str, Any]],
        query: str,
        category: str,
        intent_confidence: float
    ) -> Dict[str, Any]:
        """結果を評価して最適化"""
        
        if not results:
            return {
                'answer': "該当する回答が見つかりませんでした。より具体的なキーワードでお試しください。",
                'confidence': 0.0,
                'sources': [],
                'method': 'no_results'
            }
        
        # 最適な結果を選択
        best_result = max(results, key=lambda x: x.get('confidence', 0))
        
        # カテゴリーマッチによる信頼度ブースト
        if best_result.get('category', '').lower() == category.lower():
            boosted_confidence = min(
                best_result.get('confidence', 0) + self.category_confidence_boost,
                1.0
            )
        else:
            boosted_confidence = best_result.get('confidence', 0)
        
        # 意図分類の信頼度も考慮
        final_confidence = (boosted_confidence + intent_confidence) / 2
        
        return {
            'answer': best_result.get('answer', ''),
            'confidence': final_confidence,
            'sources': [best_result.get('source', '')],
            'method': 'category_optimized',
            'original_confidence': best_result.get('confidence', 0),
            'category_boost': self.category_confidence_boost
        }
    
    async def _enhance_with_ai(
        self,
        query: str,
        base_result: Dict[str, Any],
        all_results: List[Dict[str, Any]],
        category: str
    ) -> Dict[str, Any]:
        """AI によって結果を強化"""
        
        try:
            # コンテキストを構築
            contexts = []
            for result in all_results[:3]:  # 上位3件
                contexts.append({
                    'question': result.get('question', ''),
                    'content': result.get('answer', ''),
                    'source': result.get('source', 'Unknown'),
                    'confidence': result.get('confidence', 0)
                })
            
            # AI 回答生成
            ai_answer = await self.openai_service.generate_contextual_answer(
                question=query,
                contexts=contexts,
                system_prompt=self._get_category_system_prompt(category)
            )
            
            # 回答品質評価
            quality_score = await self.openai_service.evaluate_answer_quality(
                question=query,
                answer=ai_answer,
                contexts=contexts
            )
            
            return {
                'answer': ai_answer,
                'confidence': quality_score,
                'sources': [ctx['source'] for ctx in contexts],
                'method': 'ai_enhanced',
                'ai_generated': True,
                'base_confidence': base_result['confidence']
            }
            
        except Exception as e:
            LOGGER.error(f"AI強化エラー: {e}")
            return base_result
    
    def _get_category_system_prompt(self, category: str) -> str:
        """カテゴリー別のシステムプロンプト"""
        
        prompts = {
            "about": """
あなたはPIP-Makerの概要説明の専門家です。
- PIP-Makerの基本的な特徴と概要を分かりやすく説明してください
- 技術的な詳細よりも、ユーザーメリットに焦点を当ててください
- 具体的な事例やベネフィットを含めて回答してください
""",
            "cases": """
あなたはPIP-Makerの導入事例の専門家です。
- 実際の導入事例と成功例を具体的に説明してください
- 業界別の活用方法や効果を含めて回答してください
- 数値や具体的な成果があれば積極的に含めてください
""",
            "features": """
あなたはPIP-Makerの機能説明の専門家です。
- 具体的な機能と操作方法を段階的に説明してください
- 実際の使用場面を想定した説明を心がけてください
- 設定方法や注意点があれば含めてください
""",
            "pricing": """
あなたはPIP-Makerの料金・ライセンスの専門家です。
- 料金体系を明確に説明してください
- ライセンス条件や制限事項を正確に伝えてください
- コスト面でのメリットがあれば含めてください
""",
            "other": """
あなたはPIP-Makerの総合サポート担当です。
- ユーザーの質問に対して適切なサポート情報を提供してください
- 不明な点があれば正直に伝えて、適切な問い合わせ先を案内してください
- 丁寧で親切な対応を心がけてください
"""
        }
        
        base_prompt = """
あなたはPIP-Makerの専門カスタマーサポートAIです。
以下のルールに従って回答してください：

1. 提供されたコンテキスト情報のみを使用してください
2. 情報が不足している場合は正直に「情報が不足している」と伝えてください
3. 丁寧で分かりやすい日本語で回答してください
4. PIP-Makerの製品に関する専門的な質問に答えてください
5. 不確実な情報は提供せず、確認を促してください
6. 回答は簡潔で実用的にしてください
"""
        
        return base_prompt + "\n" + prompts.get(category, prompts["other"])
    
    async def health_check(self) -> Dict[str, Any]:
        """サービスのヘルスチェック"""
        
        health_status = {
            "status": "healthy",
            "components": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # データサービス
        try:
            test_data = await self.data_service.get_qa_data()
            health_status["components"]["data_service"] = {
                "status": "healthy",
                "data_count": len(test_data)
            }
        except Exception as e:
            health_status["components"]["data_service"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # 意図分類サービス
        if self.intent_classifier:
            try:
                test_result = await self.intent_classifier.classify_intent("テスト")
                health_status["components"]["intent_classifier"] = {
                    "status": "healthy",
                    "method": test_result.method
                }
            except Exception as e:
                health_status["components"]["intent_classifier"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["status"] = "degraded"
        else:
            health_status["components"]["intent_classifier"] = {
                "status": "disabled",
                "reason": "Intent classifier not configured"
            }
        
        # OpenAI サービス
        if self.openai_service:
            try:
                openai_health = await self.openai_service.health_check()
                health_status["components"]["openai_service"] = openai_health
                if openai_health["status"] != "healthy":
                    health_status["status"] = "degraded"
            except Exception as e:
                health_status["components"]["openai_service"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        else:
            health_status["components"]["openai_service"] = {
                "status": "disabled",
                "reason": "OpenAI service not configured"
            }
        
        return health_status