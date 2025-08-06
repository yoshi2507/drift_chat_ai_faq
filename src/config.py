"""
PIP-Maker チャットボットの設定管理（最終修正版）
"""

import os
import json
import tempfile
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """環境変数から読み込まれるアプリケーション設定"""
    
    # アプリケーション基本設定
    app_name: str = Field(default="PIP-Maker Chat API", alias="APP_NAME")
    app_version: str = Field(default="1.5.1", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    
    # サーバー設定
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    
    # データソース設定 - CSVフォールバック
    csv_file_path: str = Field(default="src/qa_data.csv", alias="CSV_FILE_PATH")
    
    # Google Sheets設定
    google_sheets_enabled: bool = Field(default=False, alias="GOOGLE_SHEETS_ENABLED")
    google_sheets_id: Optional[str] = Field(default=None, alias="GOOGLE_SHEETS_ID")
    google_sheets_range: str = Field(default="A:G", alias="GOOGLE_SHEETS_RANGE")
    
    # 🔧 認証方法を2つサポート（フィールド追加）
    # 方法1: ファイルパス（ローカル開発用）
    google_credentials_path: Optional[str] = Field(default=None, alias="GOOGLE_CREDENTIALS_PATH")
    
    # 方法2: JSON文字列（Render本番用）
    google_service_account_json: Optional[str] = Field(default=None, alias="GOOGLE_SERVICE_ACCOUNT_JSON")
    
    # Slack通知設定
    slack_webhook_url: Optional[str] = Field(default=None, alias="SLACK_WEBHOOK_URL")
    
    # 検索設定
    search_similarity_threshold: float = Field(default=0.3, alias="SEARCH_SIMILARITY_THRESHOLD")  # 0.1 → 0.3
    
    # ログ設定
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # セキュリティ設定
    rate_limit_per_minute: int = Field(default=10, alias="RATE_LIMIT_PER_MINUTE")
    
    # キャッシュ設定
    cache_ttl_seconds: int = Field(default=300, alias="CACHE_TTL_SECONDS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"
    
    def get_google_credentials_path(self) -> Optional[str]:
        """Google認証情報のファイルパスを取得"""
        
        # 方法1: 直接ファイルパスが指定されている場合（ローカル開発）
        if self.google_credentials_path and os.path.exists(self.google_credentials_path):
            print(f"✅ Google認証: ファイルパス方式 ({self.google_credentials_path})")
            return self.google_credentials_path
        
        # 方法2: JSON文字列から一時ファイルを作成（Render本番）
        if self.google_service_account_json:
            try:
                # JSON文字列をパース
                credentials_data = json.loads(self.google_service_account_json)
                
                # 一時ファイルに保存
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w', 
                    suffix='.json', 
                    delete=False
                )
                json.dump(credentials_data, temp_file, indent=2)
                temp_file.close()
                
                print(f"✅ Google認証: JSON環境変数方式 (一時ファイル: {temp_file.name})")
                return temp_file.name
                
            except json.JSONDecodeError as e:
                print(f"❌ Google認証JSON解析エラー: {e}")
                print(f"JSON文字列の最初の100文字: {self.google_service_account_json[:100]}...")
                return None
            except Exception as e:
                print(f"❌ Google認証情報処理エラー: {e}")
                return None
        
        print("⚠️ Google認証情報が設定されていません")
        return None
    
    @property
    def is_google_sheets_configured(self) -> bool:
        """Google Sheetsが正しく設定されているかチェック"""
        return (
            self.google_sheets_enabled and 
            bool(self.google_sheets_id) and 
            (bool(self.google_credentials_path) or bool(self.google_service_account_json))
        )
    
    def get_data_source_config(self) -> dict:
        """データソース設定を取得"""
        credentials_available = bool(self.get_google_credentials_path())
        
        return {
            'google_sheets_enabled': self.google_sheets_enabled,
            'google_sheets_configured': self.is_google_sheets_configured,
            'sheets_config': {
                'id': self.google_sheets_id,
                'credentials_method': 'file' if self.google_credentials_path else 'env_json' if self.google_service_account_json else 'none',
                'credentials_available': credentials_available,
                'range': self.google_sheets_range
            } if self.is_google_sheets_configured else None,
            'csv_fallback': self.csv_file_path
        }
        
    def debug_settings(self):
        """デバッグ用：設定値を表示"""
        print("=== 設定値デバッグ（最終修正版）===")
        print(f"current directory: {os.getcwd()}")
        print(f"google_sheets_enabled: {self.google_sheets_enabled}")
        print(f"google_sheets_id: {self.google_sheets_id}")
        print(f"google_credentials_path: {self.google_credentials_path}")
        print(f"google_credentials_path exists: {os.path.exists(self.google_credentials_path) if self.google_credentials_path else False}")
        print(f"google_service_account_json: {'設定済み' if self.google_service_account_json else '未設定'}")
        print(f"is_google_sheets_configured: {self.is_google_sheets_configured}")
        print(f"csv_fallback: {self.csv_file_path}")


# グローバル設定インスタンス
settings = Settings()


def get_settings() -> Settings:
    """アプリケーション設定を取得"""
    return settings


# データサービスファクトリー関数
def create_data_service():
    """設定に基づいて適切なデータサービスを作成"""
    try:
        from .google_sheets_service import GoogleSheetsService
        from .enhanced_sheet_service import EnhancedGoogleSheetsService
        
        if settings.is_google_sheets_configured:
            print(f"✅ Google Sheets統合モードで起動")
            print(f"📊 スプレッドシートID: {settings.google_sheets_id}")
            
            credentials_path = settings.get_google_credentials_path()
            if not credentials_path:
                print(f"❌ Google認証情報の取得に失敗。CSVフォールバックモードに切り替えます。")
                return EnhancedGoogleSheetsService(settings.csv_file_path)
            
            return GoogleSheetsService(
                spreadsheet_id=settings.google_sheets_id,
                credentials_path=credentials_path,
                fallback_csv_path=settings.csv_file_path
            )
        else:
            print(f"📄 CSVフォールバックモードで起動")
            print(f"📂 CSVファイル: {settings.csv_file_path}")
            
            return EnhancedGoogleSheetsService(settings.csv_file_path)
            
    except ImportError as e:
        print(f"⚠️ Import error in create_data_service: {e}")
        # フォールバック実装
        from enhanced_sheet_service import EnhancedGoogleSheetsService
        return EnhancedGoogleSheetsService(settings.csv_file_path)


# デバッグ情報を表示（開発時のみ）
if __name__ == "__main__":
    settings.debug_settings()