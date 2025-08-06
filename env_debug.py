# env_debug.py - .env設定デバッグスクリプト

"""
.env ファイルの設定問題をデバッグするスクリプト
"""

import os
import sys
from pathlib import Path

def check_env_file_existence():
    """=== 📁 .envファイル存在確認 ==="""
    print("=== 📁 .envファイル存在確認 ===")
    
    current_dir = Path.cwd()
    env_file_path = current_dir / ".env"
    
    print(f"現在のディレクトリ: {current_dir}")
    print(f".env ファイルパス: {env_file_path}")
    print(f".env ファイル存在: {env_file_path.exists()}")
    
    if env_file_path.exists():
        print(f"✅ .env ファイルが見つかりました")
        return env_file_path
    else:
        print(f"❌ .env ファイルが見つかりません")
        
        # 他の場所を確認
        possible_locations = [
            current_dir.parent / ".env",
            Path(sys.argv[0]).parent / ".env",
            Path("src") / ".env"
        ]
        
        print("\n📍 他の場所を確認中...")
        for location in possible_locations:
            if location.exists():
                print(f"✅ 発見: {location}")
                return location
            else:
                print(f"❌ なし: {location}")
        
        return None

def read_env_file_content(env_file_path):
    """=== 📄 .envファイル内容確認 ==="""
    print("\n=== 📄 .envファイル内容確認 ===")
    
    try:
        with open(env_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"ファイルサイズ: {len(content)} 文字")
        print("\n--- ファイル内容 ---")
        print(content)
        print("--- ファイル内容終了 ---\n")
        
        # 行ごとに分析
        lines = content.strip().split('\n')
        slack_lines = [line for line in lines if 'SLACK_WEBHOOK_URL' in line]
        
        print(f"総行数: {len(lines)}")
        print(f"SLACK_WEBHOOK_URL を含む行数: {len(slack_lines)}")
        
        for i, line in enumerate(slack_lines):
            print(f"  行{i+1}: {line}")
        
        return content, slack_lines
        
    except Exception as e:
        print(f"❌ ファイル読み込みエラー: {e}")
        return None, []

def check_env_file_format(slack_lines):
    """=== 📝 .envファイル形式チェック ==="""
    print("\n=== 📝 .envファイル形式チェック ===")
    
    if not slack_lines:
        print("❌ SLACK_WEBHOOK_URL の設定が見つかりません")
        return False
    
    for line in slack_lines:
        line = line.strip()
        
        if line.startswith('#'):
            print(f"⚠️  コメントアウト: {line}")
            continue
            
        if '=' not in line:
            print(f"❌ 形式エラー（=がない）: {line}")
            continue
            
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        
        print(f"🔍 検証中: {key}={value[:50]}{'...' if len(value) > 50 else ''}")
        
        # 形式チェック
        issues = []
        
        if key != 'SLACK_WEBHOOK_URL':
            issues.append(f"キー名が違う: '{key}' (正しくは: 'SLACK_WEBHOOK_URL')")
        
        if not value:
            issues.append("値が空")
        elif value.startswith('"') and value.endswith('"'):
            print("  ✅ クォート形式")
        elif value.startswith("'") and value.endswith("'"):
            print("  ✅ シングルクォート形式")
        else:
            print("  ✅ クォートなし形式")
        
        if not value.strip('"\'').startswith('https://hooks.slack.com/services/'):
            issues.append("URL形式が正しくない（https://hooks.slack.com/services/ で始まっていない）")
        
        if issues:
            print(f"❌ 問題:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        else:
            print(f"✅ 形式正常")
            return True

def check_environment_variable_loading():
    """=== 🔄 環境変数読み込み確認 ==="""
    print("\n=== 🔄 環境変数読み込み確認 ===")
    
    # 直接os.getenvで確認
    direct_value = os.getenv('SLACK_WEBHOOK_URL')
    print(f"os.getenv('SLACK_WEBHOOK_URL'): {direct_value[:50] + '...' if direct_value and len(direct_value) > 50 else direct_value}")
    
    # python-dotenvで読み込み確認
    try:
        from dotenv import load_dotenv
        print("✅ python-dotenv インポート成功")
        
        # 明示的に.envファイルを読み込み
        load_dotenv_result = load_dotenv()
        print(f"load_dotenv() 結果: {load_dotenv_result}")
        
        # 読み込み後の値確認
        after_dotenv = os.getenv('SLACK_WEBHOOK_URL')
        print(f"load_dotenv後の値: {after_dotenv[:50] + '...' if after_dotenv and len(after_dotenv) > 50 else after_dotenv}")
        
    except ImportError:
        print("❌ python-dotenv がインストールされていません")
        print("   pip install python-dotenv で解決できます")
        return False
    
    return bool(os.getenv('SLACK_WEBHOOK_URL'))

def check_pydantic_settings():
    """=== ⚙️ Pydantic設定確認 ==="""
    print("\n=== ⚙️ Pydantic設定確認 ===")
    
    try:
        from src.config import settings
        print("✅ src.config.settings インポート成功")
        
        print(f"settings.slack_webhook_url: {settings.slack_webhook_url[:50] + '...' if settings.slack_webhook_url and len(settings.slack_webhook_url) > 50 else settings.slack_webhook_url}")
        
        # 設定クラスの詳細確認
        print(f"Pydantic Config.env_file: {getattr(settings.Config, 'env_file', 'Not set')}")
        print(f"Pydantic Config.case_sensitive: {getattr(settings.Config, 'case_sensitive', 'Not set')}")
        
        return bool(settings.slack_webhook_url)
        
    except ImportError as e:
        print(f"❌ src.config インポートエラー: {e}")
        return False
    except Exception as e:
        print(f"❌ 設定確認エラー: {e}")
        return False

def check_app_slack_service():
    """=== 🤖 アプリSlackサービス確認 ==="""
    print("\n=== 🤖 アプリSlackサービス確認 ===")
    
    try:
        from src.app import slack_service
        print("✅ src.app.slack_service インポート成功")
        
        print(f"slack_service.enabled: {slack_service.enabled}")
        print(f"slack_service.webhook_url: {slack_service.webhook_url[:50] + '...' if slack_service.webhook_url and len(slack_service.webhook_url) > 50 else slack_service.webhook_url}")
        
        return slack_service.enabled
        
    except ImportError as e:
        print(f"❌ src.app インポートエラー: {e}")
        return False
    except Exception as e:
        print(f"❌ アプリ確認エラー: {e}")
        return False

def comprehensive_env_debug():
    """包括的な.env設定デバッグ"""
    print("🔍 === .env設定デバッグ開始 ===\n")
    
    # Step 1: ファイル存在確認
    env_file_path = check_env_file_existence()
    
    if not env_file_path:
        print("\n❌ 結論: .envファイルが見つかりません")
        print("📝 解決方法:")
        print("1. プロジェクトルートで .env ファイルを作成")
        print("2. SLACK_WEBHOOK_URL=https://hooks.slack.com/services/... を追加")
        return False
    
    # Step 2: ファイル内容確認
    content, slack_lines = read_env_file_content(env_file_path)
    
    if not content:
        print("\n❌ 結論: .envファイルの読み込みに失敗")
        return False
    
    # Step 3: 形式確認
    format_ok = check_env_file_format(slack_lines)
    
    # Step 4: 環境変数読み込み確認
    env_loaded = check_environment_variable_loading()
    
    # Step 5: Pydantic設定確認
    pydantic_ok = check_pydantic_settings()
    
    # Step 6: アプリ設定確認
    app_ok = check_app_slack_service()
    
    # 総合診断
    print("\n" + "="*60)
    print("🎯 === 総合診断結果 ===")
    
    print(f"📁 .envファイル存在:     {'✅' if env_file_path else '❌'}")
    print(f"📝 設定形式正常:         {'✅' if format_ok else '❌'}")
    print(f"🔄 環境変数読み込み:     {'✅' if env_loaded else '❌'}")
    print(f"⚙️  Pydantic設定:        {'✅' if pydantic_ok else '❌'}")
    print(f"🤖 アプリサービス:       {'✅' if app_ok else '❌'}")
    
    if all([env_file_path, format_ok, env_loaded, pydantic_ok, app_ok]):
        print("\n🎉 すべて正常です！")
    else:
        print("\n🔧 修正が必要な項目があります。")
        print("\n📝 推奨解決手順:")
        
        if not format_ok:
            print("1. .env ファイルの SLACK_WEBHOOK_URL の記述を確認")
            print("   正しい形式: SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...")
        
        if not env_loaded:
            print("2. python-dotenv のインストール確認")
            print("   pip install python-dotenv")
        
        if not pydantic_ok or not app_ok:
            print("3. アプリケーション再起動")
            print("   uvicorn src.app:app --reload")

if __name__ == "__main__":
    comprehensive_env_debug()