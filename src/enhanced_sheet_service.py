# enhanced_sheet_service.py - Phase 1.5 拡張シートサービス（修正版）

"""
拡張されたGoogle Sheets/CSVサービス
FAQ機能とカテゴリー検索に対応
"""

import csv
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime

LOGGER = logging.getLogger(__name__)

class SheetAccessException(Exception):
    """シートアクセス関連の例外"""
    pass

class EnhancedGoogleSheetsService:
    """拡張されたCSV/スプレッドシートサービス（FAQ対応）"""
    
    def __init__(self, csv_path: str):
        """
        Args:
            csv_path: CSVファイルのパス
        """
        # 相対パスを絶対パスに変換
        if not os.path.isabs(csv_path):
            self.csv_path = os.path.join(os.path.dirname(__file__), csv_path)
        else:
            self.csv_path = csv_path
            
        self._cache: Optional[List[Dict[str, str]]] = None
        self._cache_timestamp: Optional[datetime] = None
        self.cache_ttl_seconds = 300  # 5分間キャッシュ
        
        # CSVのヘッダー（日本語）から英語キーへのマッピング
        self.field_mapping = {
            '質問': 'question',
            '回答': 'answer',
            '対応カテゴリー': 'category',
            '根拠資料': 'source',
            '備考': 'notes',
            'FAQ_ID': 'faq_id',
            '表示順序': 'display_order'
        }
        
        LOGGER.info(f"EnhancedGoogleSheetsService initialized with CSV: {self.csv_path}")

    def _normalize_row(self, row: Dict[str, str]) -> Dict[str, str]:
        """CSVの行データを正規化（日本語キー → 英語キー）"""
        normalized = {}
        
        for jp_key, en_key in self.field_mapping.items():
            value = row.get(jp_key, '').strip()
            
            # 表示順序は数値に変換
            if en_key == 'display_order' and value:
                try:
                    normalized[en_key] = int(value)
                except ValueError:
                    normalized[en_key] = 999  # デフォルト値（最後に表示）
            else:
                normalized[en_key] = value
                
        return normalized

    def _is_cache_valid(self) -> bool:
        """キャッシュが有効かどうかチェック"""
        if self._cache is None or self._cache_timestamp is None:
            return False
            
        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed < self.cache_ttl_seconds

    async def get_qa_data(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        """Q&Aデータを取得（キャッシュ機能付き）"""
        
        # キャッシュが有効な場合はそれを返す
        if not force_refresh and self._is_cache_valid():
            LOGGER.debug(f"キャッシュからQ&Aデータを返却: {len(self._cache)}件")
            return self._cache
        
        try:
            # CSVファイルの存在確認
            if not os.path.exists(self.csv_path):
                raise SheetAccessException(f"CSVファイルが見つかりません: {self.csv_path}")
            
            with open(self.csv_path, newline='', encoding='utf-8') as fp:
                reader = csv.DictReader(fp)
                rows = []
                
                for row_num, row in enumerate(reader, start=2):  # ヘッダーを考慮して2から開始
                    # 空行をスキップ
                    if not any(value.strip() for value in row.values()):
                        continue
                        
                    try:
                        normalized_row = self._normalize_row(row)
                        rows.append(normalized_row)
                    except Exception as e:
                        LOGGER.warning(f"行 {row_num} の処理でエラー: {e}")
                        continue
                
                self._cache = rows
                self._cache_timestamp = datetime.now()
                
                LOGGER.info(f"{self.csv_path} から {len(self._cache)} 件のQ&Aエントリを読み込みました")
                return self._cache
                
        except FileNotFoundError as exc:
            raise SheetAccessException(f"CSVファイルが見つかりません: {self.csv_path}") from exc
        except UnicodeDecodeError as exc:
            raise SheetAccessException(f"CSVファイルの文字エンコーディングエラー: {exc}") from exc
        except Exception as exc:
            raise SheetAccessException(f"CSVファイルの読み込みに失敗しました: {exc}") from exc

    async def get_faqs_by_category(self, category: str) -> List[Dict[str, str]]:
        """カテゴリー別のFAQを取得"""
        try:
            data = await self.get_qa_data()
            
            # FAQのみを抽出（備考が「よくある質問」でFAQ_IDが存在するもの）
            faqs = []
            for row in data:
                row_category = row.get('category', '').lower().strip()
                row_notes = row.get('notes', '').strip()
                row_faq_id = row.get('faq_id', '').strip()
                
                if (row_category == category.lower() and 
                    row_notes == 'よくある質問' and 
                    row_faq_id):
                    faqs.append(row)
            
            # 表示順序でソート
            faqs.sort(key=lambda x: x.get('display_order', 999))
            
            LOGGER.info(f"カテゴリー '{category}' のFAQ {len(faqs)}件を取得")
            return faqs
            
        except Exception as e:
            LOGGER.error(f"カテゴリー別FAQ取得エラー: {e}")
            return []

    async def get_faq_by_id(self, faq_id: str) -> Optional[Dict[str, str]]:
        """FAQ IDで特定のFAQを取得"""
        try:
            data = await self.get_qa_data()
            
            for row in data:
                if row.get('faq_id') == faq_id:
                    LOGGER.info(f"FAQ ID '{faq_id}' を取得")
                    return row
            
            LOGGER.warning(f"FAQ ID '{faq_id}' が見つかりません")
            return None
            
        except Exception as e:
            LOGGER.error(f"FAQ ID検索エラー: {e}")
            return None

    async def get_categories_summary(self) -> Dict[str, Dict[str, any]]:
        """カテゴリー別の統計情報を取得"""
        try:
            data = await self.get_qa_data()
            categories = {}
            
            for row in data:
                category = row.get('category', '').strip()
                if not category:
                    continue
                    
                if category not in categories:
                    categories[category] = {
                        'total_count': 0,
                        'faq_count': 0,
                        'general_count': 0
                    }
                
                categories[category]['total_count'] += 1
                
                if row.get('notes') == 'よくある質問':
                    categories[category]['faq_count'] += 1
                else:
                    categories[category]['general_count'] += 1
            
            LOGGER.info(f"カテゴリー統計: {len(categories)}カテゴリー")
            return categories
            
        except Exception as e:
            LOGGER.error(f"カテゴリー統計取得エラー: {e}")
            return {}

    async def search_qa_data(
        self, 
        query: str, 
        category: Optional[str] = None,
        include_faqs_only: bool = False
    ) -> List[Dict[str, str]]:
        """Q&Aデータの検索（カテゴリーフィルター付き）"""
        try:
            data = await self.get_qa_data()
            results = []
            
            query_lower = query.lower().strip()
            
            for row in data:
                # カテゴリーフィルター
                if category:
                    row_category = row.get('category', '').lower().strip()
                    if row_category != category.lower():
                        continue
                
                # FAQのみフィルター
                if include_faqs_only and row.get('notes') != 'よくある質問':
                    continue
                
                # テキスト検索（質問と回答の両方で検索）
                question = row.get('question', '').lower()
                answer = row.get('answer', '').lower()
                
                if query_lower in question or query_lower in answer:
                    results.append(row)
            
            LOGGER.info(f"検索クエリ '{query}' (カテゴリー: {category}): {len(results)}件")
            return results
            
        except Exception as e:
            LOGGER.error(f"Q&A検索エラー: {e}")
            return []

    def clear_cache(self):
        """キャッシュをクリア"""
        self._cache = None
        self._cache_timestamp = None
        LOGGER.info("Q&Aデータキャッシュをクリアしました")

    def get_cache_info(self) -> Dict[str, any]:
        """キャッシュ情報を取得"""
        return {
            'cached': self._cache is not None,
            'cache_size': len(self._cache) if self._cache else 0,
            'cache_timestamp': self._cache_timestamp.isoformat() if self._cache_timestamp else None,
            'cache_valid': self._is_cache_valid(),
            'csv_path': self.csv_path,
            'csv_exists': os.path.exists(self.csv_path)
        }