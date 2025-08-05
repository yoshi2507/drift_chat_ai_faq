"""
PIP-Maker チャットボットの設定管理（Google Sheets対応版）
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """環境変数から読み込まれるアプリケーション設定"""
    
    # アプリケーション基本設定
    app_name: str = Field(default="PIP-Maker Chat API", alias="APP_NAME")
    app_version: str = Field(default="1.5.1", alias="APP_VERSION")  # Google Sheets対応版
    debug: bool = Field(default=False, alias="DEBUG")
    
    # サーバー設定
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    
    # データソース設定
    csv_file_path: str = Field(default="qa_data.csv", alias="CSV_FILE_PATH")
    
    # Google Sheets設定（Phase 1.5.1で追加）
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
    cache_ttl_seconds: int = Field(default=300, alias="CACHE_TTL_SECONDS")  # 5分
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # 🔧 追加: 未定義のフィールドを無視
        
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
        print("=== 設定値デバッグ（Google Sheets対応版）===")
        print(f"current directory: {os.getcwd()}")
        print(f"env_file path: {os.path.abspath('.env')}")
        print(f"env_file exists: {os.path.exists('.env')}")
        print(f"app_name: {self.app_name}")
        print(f"app_version: {self.app_version}")
        print(f"debug: {self.debug}")
        print(f"csv_file_path: {self.csv_file_path}")
        print(f"google_sheets_enabled: {self.google_sheets_enabled}")
        print(f"google_sheets_id: {self.google_sheets_id}")
        print(f"google_credentials_path: {self.google_credentials_path}")
        print(f"is_google_sheets_configured: {self.is_google_sheets_configured}")
        print(f"slack_webhook_url: {'設定済み' if self.slack_webhook_url else '未設定'}")
        
        if self.google_credentials_path:
            print(f"credentials file exists: {os.path.exists(self.google_credentials_path)}")
        
        if os.path.exists('.env'):
            print(f"\n.env file content (sensitive info masked):")
            try:
                with open('.env', 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 機密情報をマスク
                    lines = content.split('\n')
                    for line in lines:
                        if any(sensitive in line.upper() for sensitive in ['WEBHOOK', 'KEY', 'SECRET', 'TOKEN']):
                            if '=' in line:
                                key, _ = line.split('=', 1)
                                print(f"{key}=***MASKED***")
                        else:
                            print(line)
            except Exception as e:
                print(f"Error reading .env: {e}")
        else:
            print("\n.env file not found!")


# グローバル設定インスタンス
settings = Settings()


def get_settings() -> Settings:
    """アプリケーション設定を取得"""
    return settings


# データサービスファクトリー関数
def create_data_service():
    """設定に基づいて適切なデータサービスを作成"""
    from src.google_sheets_service import GoogleSheetsService
    from src.enhanced_sheet_service import EnhancedGoogleSheetsService
    
    if settings.is_google_sheets_configured:
        # Google Sheets統合サービスを使用
        return GoogleSheetsService(
            spreadsheet_id=settings.google_sheets_id,
            credentials_path=settings.google_credentials_path,
            fallback_csv_path=settings.csv_file_path
        )
    else:
        # 従来のCSVサービスを使用
        return EnhancedGoogleSheetsService(settings.csv_file_path)


# デバッグ情報を表示（開発時のみ）
if __name__ == "__main__":
    settings.debug_settings()