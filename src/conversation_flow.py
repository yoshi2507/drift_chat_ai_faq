# conversation_flow.py - Phase 1.5 対話フロー管理サービス

"""
PIP-Maker チャットボット Phase 1.5
新しい対話フローとFAQ機能を実装するサービス
"""

import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)

class ConversationState(str, Enum):
    """対話の状態を管理"""
    INITIAL = "initial"                # 初期状態
    CATEGORY_SELECTION = "category"    # カテゴリー選択
    FAQ_OR_QUESTION = "faq_question"   # FAQ選択 or 自由質問
    INQUIRY_FORM = "inquiry_form"      # お問い合わせフォーム
    COMPLETED = "completed"            # 完了

class ConversationContext(BaseModel):
    """対話コンテキスト"""
    conversation_id: str
    user_id: Optional[str] = None
    state: ConversationState = ConversationState.INITIAL
    selected_category: Optional[str] = None
    interaction_count: int = 0
    inquiry_data: Optional[Dict[str, str]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class ConversationFlowService:
    """対話フローを管理するサービス"""
    
    def __init__(self, sheet_service):
        """
        Args:
            sheet_service: EnhancedGoogleSheetsService インスタンス
        """
        self.sheet_service = sheet_service
        self.contexts: Dict[str, ConversationContext] = {}
        
        # カテゴリー定義
        self.category_definitions = {
            "about": {
                "name": "PIP-Makerとは？",
                "description": "PIP-Makerの基本的な概要と特徴について説明します。",
                "emoji": "💡"
            },
            "cases": {
                "name": "PIP-Makerの導入事例", 
                "description": "実際の導入事例と成功例をご紹介します。",
                "emoji": "📈"
            },
            "features": {
                "name": "PIP-Makerの機能",
                "description": "PIP-Makerの主要機能と使い方について説明します。",
                "emoji": "⚙️"
            },
            "pricing": {
                "name": "PIP-Makerの料金プラン / ライセンスルール",
                "description": "料金体系とライセンス情報についてご案内します。",
                "emoji": "💰"
            },
            "other": {
                "name": "その他",
                "description": "上記以外のご質問やご相談についてお答えします。",
                "emoji": "❓"
            }
        }

    async def get_welcome_message(self) -> Dict[str, Any]:
        """初期の歓迎メッセージとカテゴリー選択肢を返す"""
        categories = [
            {
                "id": cat_id, 
                "name": f"{cat_info['emoji']} {cat_info['name']}",
                "description": cat_info["description"]
            }
            for cat_id, cat_info in self.category_definitions.items()
        ]
        
        return {
            "message": "こんにちは！PIP-Makerについてお答えできる範囲でお答えします。\n興味があることを以下から選んでください。",
            "type": "category_selection",
            "categories": categories
        }

    async def select_category(self, conversation_id: str, category_id: str) -> Dict[str, Any]:
        """カテゴリーが選択された時の処理"""
        if category_id not in self.category_definitions:
            raise ValueError(f"無効なカテゴリーID: {category_id}")
        
        category_info = self.category_definitions[category_id]
        
        try:
            # FAQデータを取得
            faqs = await self.sheet_service.get_faqs_by_category(category_id)
            LOGGER.info(f"カテゴリー {category_id} のFAQ {len(faqs)}件を取得")
        except Exception as e:
            LOGGER.error(f"FAQ取得エラー: {e}")
            faqs = []
        
        # コンテキスト更新
        if conversation_id not in self.contexts:
            self.contexts[conversation_id] = ConversationContext(conversation_id=conversation_id)
        
        context = self.contexts[conversation_id]
        context.selected_category = category_id
        context.state = ConversationState.FAQ_OR_QUESTION
        context.interaction_count += 1
        context.updated_at = datetime.now()
        
        # FAQ情報を整形
        faq_list = []
        for faq in faqs:
            if faq.get('faq_id') and faq.get('question'):
                faq_list.append({
                    "id": faq["faq_id"],
                    "question": faq["question"],
                    "answer": faq.get("answer", "")
                })
        
        return {
            "message": f"{category_info['description']}\n\nよくあるご質問から選択するか、直接ご質問をご入力ください。",
            "type": "faq_selection",
            "category": {
                "id": category_id,
                "name": category_info["name"],
                "description": category_info["description"],
                "emoji": category_info["emoji"]
            },
            "faqs": faq_list,
            "show_inquiry_button": True
        }

    async def select_faq(self, conversation_id: str, faq_id: str) -> Dict[str, Any]:
        """FAQ選択時の処理"""
        context = self.contexts.get(conversation_id)
        if not context:
            raise ValueError("無効な会話ID")
        
        # FAQ回答を検索
        try:
            data = await self.sheet_service.get_qa_data()
            faq_data = None
            for row in data:
                if row.get('faq_id') == faq_id:
                    faq_data = row
                    break
            
            if not faq_data:
                raise ValueError(f"FAQ ID {faq_id} が見つかりません")
            
            context.interaction_count += 1
            context.updated_at = datetime.now()
            
            LOGGER.info(f"FAQ {faq_id} が選択されました (会話ID: {conversation_id})")
            
            return {
                "message": faq_data["answer"],
                "type": "faq_answer",
                "faq_id": faq_id,
                "source": faq_data.get("source"),
                "show_inquiry_button": True,
                "show_more_questions": True
            }
            
        except Exception as e:
            LOGGER.error(f"FAQ選択エラー: {e}")
            raise ValueError(f"FAQ情報の取得に失敗しました: {str(e)}")

    async def submit_inquiry(self, conversation_id: str, form_data: Dict[str, str]) -> Dict[str, Any]:
        """お問い合わせ送信処理"""
        context = self.contexts.get(conversation_id)
        if context:
            context.inquiry_data = form_data
            context.state = ConversationState.COMPLETED
            context.updated_at = datetime.now()
        
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
        
        # 簡単なメールアドレス形式チェック
        email = form_data.get('email', '').strip()
        if '@' not in email or '.' not in email:
            raise ValueError("正しいメールアドレスを入力してください")
        
        # お問い合わせIDを生成
        inquiry_id = f"INQ_{conversation_id}_{int(datetime.now().timestamp())}"
        
        # ログ出力
        LOGGER.info(f"新しいお問い合わせを受信: {inquiry_id}")
        LOGGER.info(f"会社名: {form_data.get('company')}, 担当者: {form_data.get('name')}")
        
        return {
            "message": "お問合せありがとうございました！担当者からお返事いたしますので、少々お待ちください。",
            "type": "inquiry_completed",
            "inquiry_id": inquiry_id,
            "estimated_response_time": "1営業日以内"
        }

    def get_conversation_context(self, conversation_id: str) -> Optional[ConversationContext]:
        """会話コンテキストを取得"""
        return self.contexts.get(conversation_id)

    def cleanup_old_contexts(self, hours: int = 24):
        """古い会話コンテキストをクリーンアップ"""
        cutoff_time = datetime.now() - datetime.timedelta(hours=hours)
        expired_ids = [
            conv_id for conv_id, context in self.contexts.items()
            if context.updated_at < cutoff_time
        ]
        
        for conv_id in expired_ids:
            del self.contexts[conv_id]
        
        if expired_ids:
            LOGGER.info(f"{len(expired_ids)}件の古い会話コンテキストをクリーンアップしました")

    async def get_category_summary(self) -> Dict[str, Any]:
        """カテゴリー別のFAQ統計を取得"""
        summary = {}
        
        try:
            for cat_id, cat_info in self.category_definitions.items():
                faqs = await self.sheet_service.get_faqs_by_category(cat_id)
                summary[cat_id] = {
                    "name": cat_info["name"],
                    "faq_count": len(faqs),
                    "emoji": cat_info["emoji"]
                }
        except Exception as e:
            LOGGER.error(f"カテゴリー統計取得エラー: {e}")
        
        return summary