# src/config.py - AI統合対応版 (インポートエラー修正)

"""
PIP-Maker チャットボットの設定管理（AI統合対応版）
"""

import os
import json
import tempfile
from typing import Optional, List, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """環境変数から読み込まれるアプリケーション設定"""
    
    # アプリケーション基本設定
    app_name: str = Field(default="PIP-Maker Chat API", alias="APP_NAME")
    app_version: str = Field(default="2.0.0", alias="APP_VERSION")
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
    
    # 認証方法を2つサポート
    google_credentials_path: Optional[str] = Field(default=None, alias="GOOGLE_CREDENTIALS_PATH")
    google_service_account_json: Optional[str] = Field(default=None, alias="GOOGLE_SERVICE_ACCOUNT_JSON")
    
    # Slack通知設定
    slack_webhook_url: Optional[str] = Field(default=None, alias="SLACK_WEBHOOK_URL")
    
    # 検索設定
    search_similarity_threshold: float = Field(default=0.3, alias="SEARCH_SIMILARITY_THRESHOLD")
    
    # OpenAI API設定
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-ada-002", alias="OPENAI_EMBEDDING_MODEL")
    openai_max_tokens: int = Field(default=1000, alias="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.3, alias="OPENAI_TEMPERATURE")

    # OpenAI使用制限
    openai_requests_per_minute: int = Field(default=20, alias="OPENAI_REQUESTS_PER_MINUTE")
    openai_daily_budget: float = Field(default=10.0, alias="OPENAI_DAILY_BUDGET")

    # カテゴリー対応検索設定
    category_search_enabled: bool = Field(default=True, alias="CATEGORY_SEARCH_ENABLED")
    category_confidence_boost: float = Field(default=0.15, alias="CATEGORY_CONFIDENCE_BOOST")
    category_early_termination: bool = Field(default=True, alias="CATEGORY_EARLY_TERMINATION")
    category_early_termination_threshold: float = Field(default=0.8, alias="CATEGORY_EARLY_TERMINATION_THRESHOLD")

    # AI意図分類
    ai_intent_classification: bool = Field(default=True, alias="AI_INTENT_CLASSIFICATION")
    intent_classification_fallback: bool = Field(default=True, alias="INTENT_CLASSIFICATION_FALLBACK")

    # 外部データソース設定
    pip_maker_website_enabled: bool = Field(default=True, alias="PIP_MAKER_WEBSITE_ENABLED")
    pip_maker_base_url: str = Field(default="https://www.pip-maker.com", alias="PIP_MAKER_BASE_URL")
    website_search_timeout: int = Field(default=30, alias="WEBSITE_SEARCH_TIMEOUT")

    pip_maker_manual_enabled: bool = Field(default=True, alias="PIP_MAKER_MANUAL_ENABLED")
    pip_maker_manual_url: str = Field(
        default="https://info.pip-maker.com/manual/pdf/PIP-Maker_creator.pdf", 
        alias="PIP_MAKER_MANUAL_URL"
    )
    pdf_search_timeout: int = Field(default=60, alias="PDF_SEARCH_TIMEOUT")

    # AI回答生成
    ai_answer_generation: bool = Field(default=True, alias="AI_ANSWER_GENERATION")
    ai_fallback_enabled: bool = Field(default=True, alias="AI_FALLBACK_ENABLED")
    
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
    
    @property
    def is_ai_enabled(self) -> bool:
        """AI機能が有効かチェック"""
        return bool(self.openai_api_key)
    
    @property  
    def enabled_data_sources(self) -> List[str]:
        """有効なデータソースのリストを取得"""
        sources = []
    
        if self.is_google_sheets_configured:
            sources.append("google_sheets")
        else:
            sources.append("csv_fallback")
    
        if self.pip_maker_website_enabled:
            sources.append("website")
        
        if self.pip_maker_manual_enabled:
            sources.append("pdf_manual")
    
        return sources

    def get_category_config(self) -> Dict[str, Any]:
        """カテゴリー検索設定を取得"""
        return {
            "enabled": self.category_search_enabled,
            "confidence_boost": self.category_confidence_boost,
            "early_termination": self.category_early_termination,
            "early_termination_threshold": self.category_early_termination_threshold,
            "ai_intent_classification": self.ai_intent_classification and self.is_ai_enabled,
            "fallback_classification": self.intent_classification_fallback
        }

    def get_openai_config(self) -> Optional[Dict[str, Any]]:
        """OpenAI設定を取得"""
        if not self.is_ai_enabled:
            return None
    
        return {
            "api_key": self.openai_api_key,
            "model": self.openai_model,
            "embedding_model": self.openai_embedding_model,
            "max_tokens": self.openai_max_tokens,
            "temperature": self.openai_temperature,
            "requests_per_minute": self.openai_requests_per_minute,
            "daily_budget": self.openai_daily_budget
        }

    def debug_settings(self):
        """デバッグ用：設定値を表示"""
        print("=== 設定値デバッグ（AI統合版）===")
        print(f"current directory: {os.getcwd()}")
        print(f"google_sheets_enabled: {self.google_sheets_enabled}")
        print(f"is_google_sheets_configured: {self.is_google_sheets_configured}")
        print(f"openai_api_key: {'設定済み' if self.openai_api_key else '未設定'}")
        print(f"ai機能有効: {self.is_ai_enabled}")

# グローバル設定インスタンス
settings = Settings()

def get_settings() -> Settings:
    """アプリケーション設定を取得"""
    return settings

# === データサービスファクトリー関数 ===

def create_data_service():
    """設定に基づいて適切なデータサービスを作成"""
    try:
        if settings.is_google_sheets_configured:
            print(f"✅ Google Sheets統合モードで起動")
            
            from .google_sheets_service import GoogleSheetsService
            
            credentials_path = settings.get_google_credentials_path()
            if not credentials_path:
                print(f"❌ Google認証情報の取得に失敗。CSVフォールバックモードに切り替えます。")
                from .enhanced_sheet_service import EnhancedGoogleSheetsService
                return EnhancedGoogleSheetsService(settings.csv_file_path)
            
            return GoogleSheetsService(
                spreadsheet_id=settings.google_sheets_id,
                credentials_path=credentials_path,
                fallback_csv_path=settings.csv_file_path
            )
        else:
            print(f"📄 CSVフォールバックモードで起動")
            from .enhanced_sheet_service import EnhancedGoogleSheetsService
            return EnhancedGoogleSheetsService(settings.csv_file_path)
            
    except ImportError as e:
        print(f"⚠️ データサービスインポートエラー: {e}")
        try:
            from .enhanced_sheet_service import EnhancedGoogleSheetsService
            return EnhancedGoogleSheetsService(settings.csv_file_path)
        except Exception as fallback_error:
            print(f"❌ フォールバックデータサービス作成失敗: {fallback_error}")
            return None
    except Exception as e:
        print(f"❌ データサービス作成失敗: {e}")
        return None

# === AI統合サービスファクトリー（修正版） ===

def create_openai_service():
    """OpenAI サービスを作成（安全なインポート）"""
    if not settings.is_ai_enabled:
        print("⚠️ OpenAI APIキーが設定されていません")
        return None
    
    try:
        # 安全なインポート
        from .ai_services.openai_service import OpenAIService, OpenAIConfig
        
        config = OpenAIConfig(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            embedding_model=settings.openai_embedding_model,
            max_tokens=settings.openai_max_tokens,
            temperature=settings.openai_temperature,
            requests_per_minute=settings.openai_requests_per_minute,
            daily_budget=settings.openai_daily_budget
        )
        
        service = OpenAIService(config)
        print(f"✅ OpenAI サービス初期化完了: {settings.openai_model}")
        return service
        
    except ImportError as e:
        print(f"⚠️ OpenAI サービスインポート失敗: {e}")
        print("    → pip install openai が必要かもしれません")
        return None
    except Exception as e:
        print(f"⚠️ OpenAI サービス作成失敗: {e}")
        return None

def create_ai_intent_classifier(openai_service=None):
    """AI意図分類サービスを作成（安全なインポート）"""
    try:
        from .ai_services.ai_intent_classifier import AIIntentClassifier
        
        classifier = AIIntentClassifier(openai_service=openai_service)
        print(f"✅ AI意図分類サービス初期化完了")
        return classifier
        
    except ImportError as e:
        print(f"⚠️ AI意図分類サービスインポート失敗: {e}")
        return None
    except Exception as e:
        print(f"⚠️ AI意図分類サービス作成失敗: {e}")
        return None

def create_category_aware_search_service():
    """カテゴリー対応検索サービスを作成（安全なインポート）"""
    try:
        # データサービス作成
        data_service = create_data_service()
        if not data_service:
            print("❌ データサービスが利用できません")
            return None, None, None
        
        # OpenAI サービス作成
        openai_service = create_openai_service()
        
        # AI意図分類サービス作成
        intent_classifier = create_ai_intent_classifier(openai_service)
        if not intent_classifier:
            print("❌ AI意図分類サービスが利用できません")
            return None, data_service, openai_service
        
        # 基本検索サービス（循環インポート回避）
        basic_search_service = None  # app.pyで作成される
        
        # カテゴリー対応検索エンジン作成
        from .ai_services.category_aware_search import CategoryAwareSearchEngine
        
        category_engine = CategoryAwareSearchEngine(
            data_service=data_service,
            intent_classifier=intent_classifier,
            openai_service=openai_service,
            basic_search_service=basic_search_service
        )
        
        print(f"✅ カテゴリー対応検索エンジン初期化完了")
        print(f"    - データソース: {type(data_service).__name__}")
        print(f"    - OpenAI: {'有効' if openai_service else '無効'}")
        print(f"    - 意図分類: 有効")
        
        return category_engine, data_service, openai_service
        
    except ImportError as e:
        print(f"⚠️ カテゴリー対応検索サービスインポート失敗: {e}")
        data_service = create_data_service()
        return None, data_service, None
    except Exception as e:
        print(f"⚠️ カテゴリー対応検索サービス作成失敗: {e}")
        data_service = create_data_service()
        return None, data_service, None

def create_complete_ai_system():
    """完全なAIシステムを作成（安全版）"""
    print("🚀 Phase 2 AI統合システム初期化開始...")
    
    # 1. データサービス
    data_service = create_data_service()
    
    # 2. OpenAI サービス
    openai_service = create_openai_service()
    
    # 3. AI意図分類
    intent_classifier = create_ai_intent_classifier(openai_service)
    
    # 4. カテゴリー対応検索
    category_engine, _, _ = create_category_aware_search_service()
    
    # 5. 基本検索（後でapp.pyで設定）
    basic_search_service = None
    
    components = {
        'data_service': data_service,
        'openai_service': openai_service,
        'intent_classifier': intent_classifier,
        'category_search_engine': category_engine,
        'basic_search_service': basic_search_service
    }
    
    # 利用可能な機能をログ出力
    available_features = []
    if data_service:
        available_features.append(f"データサービス")
    if openai_service:
        available_features.append("OpenAI統合")
    if intent_classifier:
        available_features.append("AI意図分類")
    if category_engine:
        available_features.append("カテゴリー対応検索")
    
    if available_features:
        print(f"✨ 利用可能機能: {', '.join(available_features)}")
    else:
        print("⚠️ AI機能が利用できません。基本機能で動作します。")
    
    print("🎉 Phase 2 AI統合システム初期化完了!")
    return components

# デバッグ情報を表示（開発時のみ）
if __name__ == "__main__":
    settings.debug_settings()
    
    print("\n🧪 Phase 2 AI統合サービステスト:")
    components = create_complete_ai_system()