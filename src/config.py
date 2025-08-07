# src/config.py - AI統合対応版 (インポートエラー修正)

"""
PIP-Maker チャットボットの設定管理（AI統合対応版）
"""

import os
import json
import tempfile
from datetime import datetime, timedelta  # 🔧 修正: timedelta追加
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

    # 引用機能基本設定
    citations_enabled: bool = Field(default=True, alias="CITATIONS_ENABLED")
    max_citations_display: int = Field(default=3, alias="MAX_CITATIONS_DISPLAY")
    citation_confidence_threshold: float = Field(default=0.3, alias="CITATION_CONFIDENCE_THRESHOLD")
    
    # URL検証設定
    url_verification_enabled: bool = Field(default=True, alias="URL_VERIFICATION_ENABLED")
    url_verification_timeout: int = Field(default=10, alias="URL_VERIFICATION_TIMEOUT")
    url_cache_duration_hours: int = Field(default=24, alias="URL_CACHE_DURATION_HOURS")
    
    # PIP-Maker関連URL設定
    pip_maker_website_base: str = Field(default="https://www.pip-maker.com", alias="PIP_MAKER_WEBSITE_BASE")
    pip_maker_manual_base: str = Field(default="https://info.pip-maker.com/manual", alias="PIP_MAKER_MANUAL_BASE")
    pip_maker_support_base: str = Field(default="https://support.pip-maker.com", alias="PIP_MAKER_SUPPORT_BASE")
    
    # 引用品質設定
    citation_excerpt_max_length: int = Field(default=200, alias="CITATION_EXCERPT_MAX_LENGTH")
    citation_title_max_length: int = Field(default=80, alias="CITATION_TITLE_MAX_LENGTH")
    preferred_source_types: List[str] = Field(
        default=["official_website", "pdf_manual", "faq", "documentation"], 
        alias="PREFERRED_SOURCE_TYPES"
    )
    
    # 自動引用生成設定
    auto_suggest_citations: bool = Field(default=True, alias="AUTO_SUGGEST_CITATIONS")
    citation_relevance_threshold: float = Field(default=0.6, alias="CITATION_RELEVANCE_THRESHOLD")

    # AI回答生成
    ai_answer_generation: bool = Field(default=True, alias="AI_ANSWER_GENERATION")
    ai_fallback_enabled: bool = Field(default=True, alias="AI_FALLBACK_ENABLED")
    
    # ログ設定
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # セキュリティ設定
    rate_limit_per_minute: int = Field(default=10, alias="RATE_LIMIT_PER_MINUTE")
    
    # キャッシュ設定
    cache_ttl_seconds: int = Field(default=300, alias="CACHE_TTL_SECONDS")
    
    def get_citation_config(self) -> Dict[str, Any]:
        """引用システムの設定を取得"""
        return {
            "enabled": self.citations_enabled,
            "max_display": self.max_citations_display,
            "confidence_threshold": self.citation_confidence_threshold,
            "url_verification": {
                "enabled": self.url_verification_enabled,
                "timeout": self.url_verification_timeout,
                "cache_duration_hours": self.url_cache_duration_hours
            },
            "pip_maker_urls": {
                "website_base": self.pip_maker_website_base,
                "manual_base": self.pip_maker_manual_base,
                "support_base": self.pip_maker_support_base
            },
            "quality_settings": {
                "excerpt_max_length": self.citation_excerpt_max_length,
                "title_max_length": self.citation_title_max_length,
                "preferred_source_types": self.preferred_source_types
            },
            "auto_generation": {
                "auto_suggest": self.auto_suggest_citations,
                "relevance_threshold": self.citation_relevance_threshold
            }
        }
    
    @property
    def is_citation_system_configured(self) -> bool:
        """引用システムが適切に設定されているかチェック"""
        return (
            self.citations_enabled and
            self.max_citations_display > 0 and
            0.0 <= self.citation_confidence_threshold <= 1.0 and
            self.url_verification_timeout > 0
        )
    
    def validate_phase3_configuration(self) -> Dict[str, bool]:
        """Phase 3設定の妥当性をチェック"""
        validation_results = {
            'citations_enabled': self.citations_enabled,
            'citation_config_valid': self.is_citation_system_configured,
            'url_bases_configured': all([
                self.pip_maker_website_base,
                self.pip_maker_manual_base,
                self.pip_maker_support_base
            ]),
            'quality_settings_valid': (
                self.citation_excerpt_max_length > 0 and
                self.citation_title_max_length > 0 and
                len(self.preferred_source_types) > 0
            ),
            'thresholds_valid': (
                0.0 <= self.citation_confidence_threshold <= 1.0 and
                0.0 <= self.citation_relevance_threshold <= 1.0
            )
        }
        
        validation_results['fully_operational'] = all(validation_results.values())
        
        return validation_results

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


# グローバル設定インスタンス
settings = Settings()

def get_settings() -> Settings:
    """アプリケーション設定を取得"""
    return settings


# === 🔧 修正: デバッグ関数をここで定義 ===

def debug_settings():
    """設定値デバッグ（Phase 3.1対応版）"""
    print("=== 設定値デバッグ（Phase 3.1対応版）===")
    print(f"current directory: {os.getcwd()}")

    # === 基本設定 ===
    print("\n【基本設定】")
    print(f"app_name: {settings.app_name}")
    print(f"app_version: {settings.app_version}")
    print(f"debug: {settings.debug}")

    # === データソース設定 ===
    print("\n【データソース設定】")
    print(f"google_sheets_enabled: {settings.google_sheets_enabled}")
    print(f"google_sheets_id: {settings.google_sheets_id}")
    print(f"google_credentials_path: {settings.google_credentials_path}")
    print(f"google_credentials_path exists: {os.path.exists(settings.google_credentials_path) if settings.google_credentials_path else False}")
    print(f"google_service_account_json: {'設定済み' if settings.google_service_account_json else '未設定'}")
    print(f"is_google_sheets_configured: {settings.is_google_sheets_configured}")
    print(f"csv_fallback: {settings.csv_file_path}")

    # === AI設定 ===
    print("\n【AI設定】")
    print(f"openai_api_key: {'設定済み' if settings.openai_api_key else '未設定'}")
    print(f"openai_model: {settings.openai_model}")
    print(f"ai_answer_generation: {settings.ai_answer_generation}")
    print(f"ai_intent_classification: {settings.ai_intent_classification}")
    print(f"is_ai_enabled: {settings.is_ai_enabled}")

    # === Phase 3.1: 引用設定 ===
    print("\n【Phase 3.1: 引用設定】")
    print(f"citations_enabled: {settings.citations_enabled}")
    print(f"max_citations_display: {settings.max_citations_display}")
    print(f"citation_confidence_threshold: {settings.citation_confidence_threshold}")
    print(f"url_verification_enabled: {settings.url_verification_enabled}")
    print(f"url_verification_timeout: {settings.url_verification_timeout}秒")
    print(f"url_cache_duration_hours: {settings.url_cache_duration_hours}時間")

    print("\n【PIP-Maker URL設定】")
    print(f"website_base: {settings.pip_maker_website_base}")
    print(f"manual_base: {settings.pip_maker_manual_base}")
    print(f"support_base: {settings.pip_maker_support_base}")

    print("\n【引用品質設定】")
    print(f"excerpt_max_length: {settings.citation_excerpt_max_length}")
    print(f"title_max_length: {settings.citation_title_max_length}")
    print(f"preferred_source_types: {settings.preferred_source_types}")
    print(f"auto_suggest_citations: {settings.auto_suggest_citations}")
    print(f"citation_relevance_threshold: {settings.citation_relevance_threshold}")

    # === 設定検証 ===
    print("\n【設定検証結果】")
    print(f"is_citation_system_configured: {settings.is_citation_system_configured}")

    validation_results = settings.validate_phase3_configuration()
    print(f"Phase 3設定検証:")
    for key, value in validation_results.items():
        status = "✅" if value else "❌"
        print(f"  {status} {key}: {value}")


def debug_phase3_settings():
    """Phase 3設定のデバッグ情報を表示"""
    print("=== Phase 3.1 設定デバッグ ===")
    print(f"引用機能有効: {settings.citations_enabled}")
    print(f"最大表示引用数: {settings.max_citations_display}")
    print(f"信頼度閾値: {settings.citation_confidence_threshold}")
    print(f"URL検証有効: {settings.url_verification_enabled}")
    print(f"URL検証タイムアウト: {settings.url_verification_timeout}秒")
    print(f"URLキャッシュ期間: {settings.url_cache_duration_hours}時間")
    
    print("\nPIP-Maker URL設定:")
    print(f"  Website: {settings.pip_maker_website_base}")
    print(f"  Manual: {settings.pip_maker_manual_base}")
    print(f"  Support: {settings.pip_maker_support_base}")
    
    print(f"\n引用システム設定完了: {settings.is_citation_system_configured}")
    
    validation_results = settings.validate_phase3_configuration()
    print(f"Phase 3設定検証結果:")
    for key, value in validation_results.items():
        status = "✅" if value else "❌"
        print(f"  {status} {key}")


def debug_all_settings():
    """全設定の包括的デバッグ"""
    print("🔍 === 全設定包括デバッグ ===")
    
    # 基本情報
    print(f"📂 作業ディレクトリ: {os.getcwd()}")
    print(f"🗓️  実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Phase別設定状況
    print(f"\n📊 Phase別設定状況:")
    print(f"  Phase 1 (基本機能): ✅ 完了")
    print(f"  Phase 2 (AI統合): {'✅ 有効' if settings.is_ai_enabled else '❌ 無効'}")
    print(f"  Phase 3.1 (引用機能): {'✅ 有効' if settings.is_citation_system_configured else '❌ 無効'}")
    
    # データソース優先順位
    enabled_sources = settings.enabled_data_sources
    print(f"\n📚 有効なデータソース: {', '.join(enabled_sources)}")
    
    # 機能フラグ一覧
    print(f"\n🚩 機能フラグ:")
    feature_flags = {
        "Google Sheets統合": settings.is_google_sheets_configured,
        "OpenAI統合": settings.is_ai_enabled,
        "カテゴリー検索": settings.category_search_enabled,
        "AI意図分類": settings.ai_intent_classification,
        "引用表示": settings.citations_enabled,
        "URL検証": settings.url_verification_enabled,
        "自動引用提案": settings.auto_suggest_citations,
        "Slack通知": bool(settings.slack_webhook_url)
    }
    
    for feature, enabled in feature_flags.items():
        status = "✅" if enabled else "❌"
        print(f"  {status} {feature}")
    
    # 設定ファイル情報
    print(f"\n📄 設定ファイル情報:")
    env_file_exists = os.path.exists('.env')
    print(f"  .env ファイル: {'✅ 存在' if env_file_exists else '❌ 不在'}")
    
    if env_file_exists:
        try:
            with open('.env', 'r') as f:
                env_lines = len(f.readlines())
            print(f"  .env 行数: {env_lines}行")
        except Exception as e:
            print(f"  .env 読み込みエラー: {e}")


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

def create_citation_service():
    """設定に基づいて引用サービスを作成"""
    try:
        from .source_citation_service import SourceCitationService
        
        citation_service = SourceCitationService()
        
        # 設定を適用
        citation_service.pip_maker_base_url = settings.pip_maker_website_base
        citation_service.manual_base_url = settings.pip_maker_manual_base
        citation_service.cache_duration = timedelta(hours=settings.url_cache_duration_hours)
        
        print(f"✅ 引用サービス初期化完了")
        print(f"📊 最大表示引用数: {settings.max_citations_display}")
        print(f"🔍 URL検証: {'有効' if settings.url_verification_enabled else '無効'}")
        
        return citation_service
        
    except ImportError as e:
        print(f"⚠️ 引用サービス Import error: {e}")
        return None
    except Exception as e:
        print(f"❌ 引用サービス初期化失敗: {e}")
        return None

def create_complete_phase3_system():
    """Phase 3の完全なシステムを作成"""
    try:
        # 既存のPhase 2システム
        ai_components = create_complete_ai_system()
        
        # Phase 3.1: 引用サービス追加
        citation_service = create_citation_service()
        
        # 統合システム
        phase3_components = ai_components.copy()
        phase3_components['citation_service'] = citation_service
        
        print(f"🚀 Phase 3システム初期化完了")
        print(f"📚 引用機能: {'有効' if citation_service else '無効'}")
        
        return phase3_components
        
    except Exception as e:
        print(f"❌ Phase 3システム初期化失敗: {e}")
        
        # フォールバック: Phase 2システム
        return create_complete_ai_system()


# === メイン実行部分 ===

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "phase3":
            debug_phase3_settings()
        elif sys.argv[1] == "all":
            debug_all_settings()
        else:
            print("使用方法:")
            print("  python config.py        # 基本デバッグ")
            print("  python config.py phase3 # Phase 3設定のみ")
            print("  python config.py all    # 全設定包括デバッグ")
    else:
        debug_settings()  # 既存のデバッグメソッド