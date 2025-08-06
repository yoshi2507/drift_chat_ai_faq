# src/ai_services/openai_service.py - OpenAI統合サービス

"""
Phase 2: OpenAI API統合サービス
カテゴリー対応検索とコンテキスト生成機能
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
import json

# OpenAI のインポート（条件付き）
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

# 相対インポートを修正
try:
    from ..error_handling import AIServiceException
except ImportError:
    # フォールバック
    class AIServiceException(Exception):
        pass

LOGGER = logging.getLogger(__name__)

class OpenAIConfig(BaseModel):
    """OpenAI API設定"""
    api_key: str
    model: str = "gpt-4"
    embedding_model: str = "text-embedding-ada-002"
    max_tokens: int = 1000
    temperature: float = 0.3
    requests_per_minute: int = 20
    daily_budget: float = 10.0

class TokenUsageTracker:
    """トークン使用量追跡"""
    
    def __init__(self):
        self.daily_usage = {}
        self.minute_requests = []
        
    def track_request(self, tokens_used: int, cost: float):
        """リクエストを記録"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if today not in self.daily_usage:
            self.daily_usage[today] = {"tokens": 0, "cost": 0.0, "requests": 0}
        
        self.daily_usage[today]["tokens"] += tokens_used
        self.daily_usage[today]["cost"] += cost
        self.daily_usage[today]["requests"] += 1
        
        # 1分間のリクエスト追跡
        now = datetime.now()
        self.minute_requests.append(now)
        
        # 1分以上古いリクエストを削除
        cutoff = now - timedelta(minutes=1)
        self.minute_requests = [req for req in self.minute_requests if req > cutoff]
    
    def can_make_request(self, config: OpenAIConfig) -> tuple[bool, str]:
        """リクエスト可能かチェック"""
        
        # 1分間のリクエスト制限チェック
        if len(self.minute_requests) >= config.requests_per_minute:
            return False, f"分間リクエスト制限に達しています ({config.requests_per_minute}/min)"
        
        # 日予算チェック
        today = datetime.now().strftime("%Y-%m-%d")
        if today in self.daily_usage:
            daily_cost = self.daily_usage[today]["cost"]
            if daily_cost >= config.daily_budget:
                return False, f"日予算制限に達しています (${daily_cost:.2f}/${config.daily_budget})"
        
        return True, "OK"
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """使用統計を取得"""
        today = datetime.now().strftime("%Y-%m-%d")
        today_usage = self.daily_usage.get(today, {"tokens": 0, "cost": 0.0, "requests": 0})
        
        return {
            "today": today_usage,
            "minute_requests": len(self.minute_requests),
            "total_days": len(self.daily_usage)
        }

class OpenAIService:
    """OpenAI API統合サービス"""
    
    def __init__(self, config: OpenAIConfig):
        if not OPENAI_AVAILABLE:
            raise AIServiceException("OpenAI ライブラリがインストールされていません。pip install openai を実行してください。")
        
        self.config = config
        self.client = openai.AsyncOpenAI(api_key=config.api_key)
        self.usage_tracker = TokenUsageTracker()
        
        LOGGER.info(f"OpenAI サービス初期化: {config.model}")
    
    async def generate_embeddings(self, text: str) -> List[float]:
        """テキストの埋め込みベクトルを生成"""
        
        # 使用量チェック
        can_request, reason = self.usage_tracker.can_make_request(self.config)
        if not can_request:
            raise AIServiceException(f"OpenAI API使用制限: {reason}")
        
        try:
            response = await self.client.embeddings.create(
                model=self.config.embedding_model,
                input=text
            )
            
            # 使用量を記録
            tokens_used = response.usage.total_tokens
            estimated_cost = tokens_used * 0.0001 / 1000  # 概算コスト
            self.usage_tracker.track_request(tokens_used, estimated_cost)
            
            return response.data[0].embedding
            
        except openai.RateLimitError:
            raise AIServiceException("OpenAI API レート制限に達しました")
        except openai.AuthenticationError:
            raise AIServiceException("OpenAI API認証エラー")
        except Exception as e:
            raise AIServiceException(f"埋め込み生成エラー: {str(e)}")
    
    async def generate_contextual_answer(
        self, 
        question: str, 
        contexts: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """コンテキストを基に回答を生成"""
        
        # 使用量チェック
        can_request, reason = self.usage_tracker.can_make_request(self.config)
        if not can_request:
            raise AIServiceException(f"OpenAI API使用制限: {reason}")
        
        # デフォルトシステムプロンプト
        if not system_prompt:
            system_prompt = """
あなたはPIP-Makerの専門カスタマーサポートAIです。
以下のルールに従って回答してください：

1. 提供されたコンテキスト情報のみを使用してください
2. 情報が不足している場合は正直に「情報が不足している」と伝えてください
3. 丁寧で分かりやすい日本語で回答してください
4. PIP-Makerの製品に関する専門的な質問に答えてください
5. 不確実な情報は提供せず、確認を促してください
6. 回答は簡潔で実用的にしてください
"""
        
        # コンテキストテキストを構築
        context_text = "\n\n".join([
            f"【関連情報{i+1}】\n"
            f"質問: {ctx.get('question', 'N/A')}\n"
            f"回答: {ctx.get('content', ctx.get('answer', ''))}\n"
            f"ソース: {ctx.get('source', 'Unknown')}\n"
            f"信頼度: {ctx.get('confidence', 0):.2f}"
            for i, ctx in enumerate(contexts)
        ])
        
        user_message = f"""
ユーザーの質問: {question}

関連するコンテキスト情報:
{context_text}

上記の情報を参考に、ユーザーの質問に適切に回答してください。
コンテキスト情報にない内容については言及せず、「詳細については担当者にお問い合わせください」と案内してください。
"""
        
        # メッセージ履歴を構築
        messages = [{"role": "system", "content": system_prompt}]
        
        # 会話履歴があれば追加
        if conversation_history:
            messages.extend(conversation_history[-3:])  # 直近3回のやり取り
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            # 使用量を記録
            tokens_used = response.usage.total_tokens
            estimated_cost = tokens_used * 0.002 / 1000  # GPT-4概算コスト
            self.usage_tracker.track_request(tokens_used, estimated_cost)
            
            answer = response.choices[0].message.content.strip()
            
            LOGGER.info(f"AI回答生成成功: {len(answer)}文字, {tokens_used}トークン")
            return answer
            
        except openai.RateLimitError:
            raise AIServiceException("OpenAI API レート制限に達しました")
        except openai.AuthenticationError:
            raise AIServiceException("OpenAI API認証エラー")
        except Exception as e:
            raise AIServiceException(f"AI回答生成エラー: {str(e)}")
    
    async def evaluate_answer_quality(
        self, 
        question: str, 
        answer: str, 
        contexts: List[Dict]
    ) -> float:
        """回答品質を評価（0.0-1.0のスコア）"""
        
        # 簡易評価（API使用量節約のため）
        try:
            # 基本的な品質指標
            quality_score = 0.5  # ベースライン
            
            # 回答の長さ評価
            if 50 <= len(answer) <= 500:
                quality_score += 0.1
            
            # キーワードマッチ評価
            question_keywords = set(question.lower().split())
            answer_keywords = set(answer.lower().split())
            keyword_overlap = len(question_keywords & answer_keywords) / len(question_keywords)
            quality_score += keyword_overlap * 0.2
            
            # コンテキスト利用度評価
            context_used = any(
                any(word in answer.lower() for word in ctx.get('content', '').lower().split()[:10])
                for ctx in contexts
            )
            if context_used:
                quality_score += 0.2
            
            return min(1.0, quality_score)
            
        except Exception as e:
            LOGGER.warning(f"回答品質評価エラー: {e}")
            return 0.5  # デフォルトスコア
    
    async def classify_question_intent(self, question: str) -> Dict[str, Any]:
        """質問の意図を分類"""
        
        # 使用量チェック
        can_request, reason = self.usage_tracker.can_make_request(self.config)
        if not can_request:
            # API制限時はルールベース分類にフォールバック
            return self._rule_based_intent_classification(question)
        
        classification_prompt = f"""
以下の質問を分析して、最も適切なカテゴリーと具体的な意図を特定してください。

質問: {question}

カテゴリー選択肢:
- about: PIP-Makerの概要、特徴、メリット
- cases: 導入事例、成功事例、実績
- features: 機能、操作方法、使い方
- pricing: 料金、価格、プラン、ライセンス
- other: その他、サポート、FAQ

具体的意図の例:
- pricing_plan: プラン詳細
- pricing_comparison: 料金比較
- features_howto: 使い方
- features_setup: 設定方法

JSON形式で回答してください:
{{
  "category": "選択したカテゴリー",
  "specific_intent": "具体的意図",
  "confidence": 0.0-1.0の信頼度,
  "keywords": ["抽出したキーワード"]
}}
"""
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # 分類には軽量モデル
                messages=[{"role": "user", "content": classification_prompt}],
                max_tokens=200,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # JSON解析
            try:
                result = json.loads(result_text)
                
                # 使用量を記録
                tokens_used = response.usage.total_tokens
                estimated_cost = tokens_used * 0.0005 / 1000  # GPT-3.5概算コスト
                self.usage_tracker.track_request(tokens_used, estimated_cost)
                
                return result
            except json.JSONDecodeError:
                # JSON解析失敗時はルールベース
                return self._rule_based_intent_classification(question)
                
        except Exception as e:
            LOGGER.warning(f"AI意図分類失敗: {e}")
            return self._rule_based_intent_classification(question)
    
    def _rule_based_intent_classification(self, question: str) -> Dict[str, Any]:
        """ルールベースの意図分類（フォールバック）"""
        
        question_lower = question.lower()
        
        # キーワードベース分類
        category_keywords = {
            "about": ["とは", "概要", "説明", "紹介", "特徴", "メリット"],
            "cases": ["事例", "導入", "実績", "成功", "効果", "企業"],
            "features": ["機能", "操作", "使い方", "方法", "設定", "画面"],
            "pricing": ["料金", "価格", "プラン", "ライセンス", "費用", "コスト"],
            "other": ["サポート", "問い合わせ", "ヘルプ", "その他"]
        }
        
        # カテゴリー判定
        best_category = "other"
        best_score = 0
        matched_keywords = []
        
        for category, keywords in category_keywords.items():
            matches = [kw for kw in keywords if kw in question_lower]
            score = len(matches) / len(keywords)
            
            if score > best_score:
                best_score = score
                best_category = category
                matched_keywords = matches
        
        return {
            "category": best_category,
            "specific_intent": f"{best_category}_general",
            "confidence": best_score,
            "keywords": matched_keywords,
            "method": "rule_based"
        }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """使用統計を取得"""
        return self.usage_tracker.get_usage_stats()
    
    async def health_check(self) -> Dict[str, Any]:
        """サービスのヘルスチェック"""
        try:
            # 簡単なテストリクエスト
            test_response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            
            return {
                "status": "healthy",
                "model": self.config.model,
                "api_accessible": True,
                "usage_stats": self.get_usage_stats()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "api_accessible": False,
                "usage_stats": self.get_usage_stats()
            }