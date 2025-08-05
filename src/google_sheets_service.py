# src/google_sheets_service.py - Render対応版

"""
Google SheetsからリアルタイムでQ&Aデータを取得するサービス
Phase 1.5.1 - Render環境対応版
"""

import json
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    Credentials = None
    build = None
    HttpError = Exception

LOGGER = logging.getLogger(__name__)

class GoogleSheetsException(Exception):
    """Google Sheets関連の例外"""
    pass

class GoogleSheetsService:
    """Google Sheets API統合サービス（Render対応版）"""
    
    def __init__(
        self, 
        spreadsheet_id: str,
        credentials_path: Optional[str] = None,
        fallback_csv_path: Optional[str] = None
    ):
        """
        Args:
            spreadsheet_id: Google Sheets ID（URLから取得）
            credentials_path: サービスアカウント認証JSONファイルパス
            fallback_csv_path: API失敗時のフォールバックCSVファイル
        """
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.fallback_csv_path = fallback_csv_path
        
        self._service = None
        self._cache: Optional[List[Dict[str, str]]] = None
        self._cache_timestamp: Optional[datetime] = None
        self.cache_ttl_seconds = 300  # 5分間キャッシュ
        
        # フィールドマッピング（CSVヘッダー → 内部キー）
        self.field_mapping = {
            '質問': 'question',
            '回答': 'answer', 
            '対応カテゴリー': 'category',
            '根拠資料': 'source',
            '備考': 'notes',
            'FAQ_ID': 'faq_id',
            '表示順序': 'display_order'
        }
        
        self._initialize_service()

    def _initialize_service(self):
        """Google Sheets APIサービスを初期化"""
        if not GOOGLE_SHEETS_AVAILABLE:
            LOGGER.warning("Google Sheets APIライブラリが利用できません。pip install google-api-python-client でインストールしてください。")
            return
            
        if not self.credentials_path:
            LOGGER.warning("Google Sheets認証ファイルパスが設定されていません。")
            return
            
        if not os.path.exists(self.credentials_path):
            LOGGER.warning(f"Google Sheets認証ファイルが見つかりません: {self.credentials_path}")
            return
            
        try:
            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
            )
            self._service = build('sheets', 'v4', credentials=credentials)
            LOGGER.info(f"✅ Google Sheets APIサービスを初期化しました (ID: {self.spreadsheet_id[:10]}...)")
            
        except Exception as e:
            LOGGER.error(f"❌ Google Sheets API初期化エラー: {e}")
            self._service = None

    def _normalize_row(self, row_values: List[str], headers: List[str]) -> Dict[str, str]:
        """行データを正規化"""
        normalized = {}
        
        for i, header in enumerate(headers):
            # 値を取得（範囲外の場合は空文字）
            value = row_values[i] if i < len(row_values) else ''
            value = str(value).strip()
            
            # フィールドマッピング適用
            en_key = self.field_mapping.get(header, header.lower().replace(' ', '_'))
            
            # 表示順序は数値に変換
            if en_key == 'display_order' and value:
                try:
                    normalized[en_key] = int(float(value))
                except (ValueError, TypeError):
                    normalized[en_key] = 999  # デフォルト値（最後に表示）
            else:
                normalized[en_key] = value
                
        return normalized

    async def _fetch_from_sheets(self) -> List[Dict[str, str]]:
        """Google SheetsからデータをAPI経由で取得"""
        if not self._service:
            raise GoogleSheetsException("Google Sheets APIサービスが初期化されていません")
            
        try:
            # スプレッドシートからデータ取得
            range_name = 'A:G'  # A列からG列まで（質問〜表示順序）
            
            result = self._service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueRenderOption='FORMATTED_VALUE'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                LOGGER.warning("スプレッドシートにデータが見つかりません")
                return []
            
            # ヘッダー行を取得
            headers = values[0] if values else []
            if not headers:
                raise GoogleSheetsException("ヘッダー行が見つかりません")
            
            LOGGER.info(f"📊 スプレッドシートヘッダー: {headers}")
            
            # データ行を処理
            data_rows = []
            for row_num, row_values in enumerate(values[1:], start=2):
                # 空行をスキップ
                if not any(str(val).strip() for val in row_values):
                    continue
                    
                try:
                    normalized_row = self._normalize_row(row_values, headers)
                    data_rows.append(normalized_row)
                except Exception as e:
                    LOGGER.warning(f"行 {row_num} の処理でエラー: {e}")
                    continue
            
            LOGGER.info(f"✅ Google Sheetsから {len(data_rows)} 件のデータを取得しました")
            return data_rows
            
        except HttpError as e:
            error_details = e.error_details if hasattr(e, 'error_details') else str(e)
            LOGGER.error(f"❌ Google Sheets API HTTP エラー: {error_details}")
            
            if e.resp.status == 403:
                raise GoogleSheetsException("アクセス権限がありません。スプレッドシートにサービスアカウントを共有してください。")
            elif e.resp.status == 404:
                raise GoogleSheetsException("スプレッドシートが見つかりません。IDが正しいか確認してください。")
            else:
                raise GoogleSheetsException(f"Google Sheets APIエラー: {error_details}")
                
        except Exception as e:
            LOGGER.error(f"❌ Google Sheets データ取得エラー: {e}")
            raise GoogleSheetsException(f"データ取得に失敗しました: {str(e)}")

    async def _fetch_from_fallback_csv(self) -> List[Dict[str, str]]:
        """フォールバックCSVからデータを取得"""
        if not self.fallback_csv_path or not os.path.exists(self.fallback_csv_path):
            raise GoogleSheetsException("フォールバックCSVファイルが見つかりません")
            
        try:
            # 既存のCSV読み込みロジックを使用
            import sys
            import os
            sys.path.append(os.path.dirname(__file__))
            
            from enhanced_sheet_service import EnhancedGoogleSheetsService
            csv_service = EnhancedGoogleSheetsService(self.fallback_csv_path)
            return await csv_service.get_qa_data()
            
        except Exception as e:
            LOGGER.error(f"❌ フォールバックCSV読み込みエラー: {e}")
            raise GoogleSheetsException(f"フォールバックCSVの読み込みに失敗: {str(e)}")

    def _is_cache_valid(self) -> bool:
        """キャッシュが有効かどうかチェック"""
        if self._cache is None or self._cache_timestamp is None:
            return False
            
        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed < self.cache_ttl_seconds

    async def get_qa_data(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        """Q&Aデータを取得（Google Sheets優先、CSV フォールバック）"""
        
        # キャッシュが有効な場合はそれを返す
        if not force_refresh and self._is_cache_valid():
            LOGGER.debug(f"キャッシュからQ&Aデータを返却: {len(self._cache)}件")
            return self._cache
            
        data = []
        error_messages = []
        
        # まずGoogle Sheetsから取得を試行
        if self._service:
            try:
                data = await self._fetch_from_sheets()
                LOGGER.info("✅ Google Sheetsからデータを取得しました")
            except GoogleSheetsException as e:
                error_messages.append(f"Google Sheets: {str(e)}")
                LOGGER.warning(f"⚠️ Google Sheets取得失敗: {e}")
            except Exception as e:
                error_messages.append(f"Google Sheets: 予期しないエラー: {str(e)}")
                LOGGER.error(f"❌ Google Sheets予期しないエラー: {e}")
        else:
            error_messages.append("Google Sheets: APIサービスが初期化されていません")
        
        # Google Sheets取得失敗時はCSVフォールバック
        if not data and self.fallback_csv_path:
            try:
                data = await self._fetch_from_fallback_csv()
                LOGGER.info("📄 フォールバックCSVからデータを取得しました")
            except Exception as e:
                error_messages.append(f"フォールバックCSV: {str(e)}")
                LOGGER.error(f"❌ フォールバックCSV取得も失敗: {e}")
        
        if not data:
            error_summary = " | ".join(error_messages)
            raise GoogleSheetsException(f"すべてのデータソースからの取得に失敗: {error_summary}")
        
        # キャッシュ更新
        self._cache = data
        self._cache_timestamp = datetime.now()
        
        return data

    async def get_faqs_by_category(self, category: str) -> List[Dict[str, str]]:
        """カテゴリー別のFAQを取得"""
        try:
            data = await self.get_qa_data()
            
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

    def clear_cache(self):
        """キャッシュをクリア"""
        self._cache = None
        self._cache_timestamp = None
        LOGGER.info("Google Sheets データキャッシュをクリアしました")

    def get_cache_info(self) -> Dict[str, any]:
        """キャッシュ情報を取得"""
        return {
            'cached': self._cache is not None,
            'cache_size': len(self._cache) if self._cache else 0,
            'cache_timestamp': self._cache_timestamp.isoformat() if self._cache_timestamp else None,
            'cache_valid': self._is_cache_valid(),
            'sheets_id': self.spreadsheet_id,
            'api_available': self._service is not None,
            'fallback_csv': self.fallback_csv_path,
            'credentials_path': self.credentials_path,
            'credentials_exists': os.path.exists(self.credentials_path) if self.credentials_path else False
        }

    def get_connection_status(self) -> Dict[str, any]:
        """接続状況を取得"""
        return {
            'google_sheets_available': GOOGLE_SHEETS_AVAILABLE,
            'service_initialized': self._service is not None,
            'spreadsheet_id': self.spreadsheet_id,
            'credentials_configured': bool(self.credentials_path and os.path.exists(self.credentials_path)),
            'fallback_csv_available': bool(self.fallback_csv_path and os.path.exists(self.fallback_csv_path))
        }