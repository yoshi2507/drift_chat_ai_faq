"""
PIP-Maker チャットボットの設定管理（シンプル修正版）
"""

import os
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
    
    # データソース設定 - 🔧 シンプルに src/qa_data.csv に固定
    csv_file_path: str = Field(default="src/qa_data.csv", alias="CSV_FILE_PATH")
    
    # Google Sheets設定
    google_sheets_enabled: bool = Field(default=False, alias="GOOGLE_SHEETS_ENABLED")
    google_sheets_id: Optional[str] = Field(default=None, alias="GOOGLE_SHEETS_ID")
    google_credentials_path: Optional[str] = Field(default=None, alias="GOOGLE_CREDENTIALS_PATH")
    google_sheets_range: str = Field(default="A:G", alias="GOOGLE_SHEETS_RANGE")
    
    # Slack通知設定
    slack_webhook_url: Optional[str] = Field(default=None, alias="SLACK_WEBHOOK_URL")
    
    # 検索設定
    search_similarity_threshold: float = Field(default=0.1, alias="SEARCH_SIMILARITY_THRESHOLD")
    
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
        
    @property
    def is_google_sheets_configured(self) -> bool:
        """Google Sheetsが正しく設定されているかチェック"""
        return (
            self.google_sheets_enabled and 
            bool(self.google_sheets_id) and 
            bool(self.google_credentials_path) and
            os.path.exists(self.google_credentials_path or '')
        )
    
    def get_data_source_config(self) -> dict:
        """データソース設定を取得"""
        return {
            'google_sheets_enabled': self.google_sheets_enabled,
            'google_sheets_configured': self.is_google_sheets_configured,
            'sheets_config': {
                'id': self.google_sheets_id,
                'credentials': self.google_credentials_path,
                'range': self.google_sheets_range
            } if self.is_google_sheets_configured else None,
            'csv_fallback': self.csv_file_path
        }
        
    def debug_settings(self):
        """デバッグ用：設定値を表示"""
        print("=== 設定値デバッグ（シンプル修正版）===")
        print(f"current directory: {os.getcwd()}")
        print(f"csv_file_path: {self.csv_file_path}")
        print(f"csv_file_path (abs): {os.path.abspath(self.csv_file_path)}")
        print(f"csv_file_exists: {os.path.exists(self.csv_file_path)}")
        
        # 🔧 修正: EnhancedGoogleSheetsService のパス解決に任せる
        print(f"\n📝 Note: パス解決は EnhancedGoogleSheetsService に委ねます")


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
            return GoogleSheetsService(
                spreadsheet_id=settings.google_sheets_id,
                credentials_path=settings.google_credentials_path,
                fallback_csv_path=settings.csv_file_path
            )
        else:
            return EnhancedGoogleSheetsService(settings.csv_file_path)
            
    except ImportError as e:
        print(f"⚠️ Import error in create_data_service: {e}")
        # フォールバック実装
        from enhanced_sheet_service import EnhancedGoogleSheetsService
        return EnhancedGoogleSheetsService(settings.csv_file_path)


# デバッグ情報を表示（開発時のみ）
if __name__ == "__main__":
    settings.debug_settings()