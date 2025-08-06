# slack_debug.py - Slack通知デバッグスクリプト

"""
Slack通知機能のデバッグ用スクリプト
問題の特定と解決を支援します
"""

import os
import asyncio
import aiohttp
import json
from datetime import datetime

def check_environment_variables():
    """環境変数の確認"""
    print("=== 🔧 環境変数確認 ===")
    
    slack_url = os.getenv('SLACK_WEBHOOK_URL')
    if slack_url:
        print(f"✅ SLACK_WEBHOOK_URL: 設定済み")
        print(f"   URL: {slack_url[:50]}...")
        
        # URLの形式チェック
        if slack_url.startswith('https://hooks.slack.com/services/'):
            print("✅ URL形式: 正常")
        else:
            print("❌ URL形式: 不正（https://hooks.slack.com/services/ で始まっていません）")
    else:
        print("❌ SLACK_WEBHOOK_URL: 未設定")
    
    return slack_url

async def test_webhook_directly(webhook_url):
    """Webhook URLに直接テスト送信"""
    print("\n=== 🚀 Webhook直接テスト ===")
    
    if not webhook_url:
        print("❌ Webhook URLが設定されていません")
        return False
    
    test_message = {
        "text": f"🧪 テスト通知 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*PIP-Maker チャットボット*\n🧪 Slack通知機能のテストメッセージです。"
                }
            }
        ]
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                webhook_url,
                json=test_message,
                headers={'Content-Type': 'application/json'}
            ) as response:
                status = response.status
                response_text = await response.text()
                
                print(f"📊 ステータスコード: {status}")
                print(f"📝 レスポンス: {response_text}")
                
                if status == 200:
                    print("✅ Slack通知テスト成功！")
                    return True
                else:
                    print(f"❌ Slack通知テスト失敗: HTTP {status}")
                    print(f"   レスポンス詳細: {response_text}")
                    return False
                    
    except asyncio.TimeoutError:
        print("❌ タイムアウト: Slackへの接続がタイムアウトしました")
        return False
    except aiohttp.ClientConnectorError as e:
        print(f"❌ 接続エラー: {e}")
        return False
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        return False

def test_app_slack_service():
    """アプリ内のSlackサービス確認"""
    print("\n=== 📱 アプリ内Slackサービス確認 ===")
    
    try:
        from src.app import slack_service
        
        print(f"✅ SlackNotificationService: インポート成功")
        print(f"   有効状態: {slack_service.enabled}")
        print(f"   Webhook URL設定: {'あり' if slack_service.webhook_url else 'なし'}")
        
        if slack_service.webhook_url:
            print(f"   URL: {slack_service.webhook_url[:50]}...")
        
        return slack_service
        
    except ImportError as e:
        print(f"❌ アプリインポートエラー: {e}")
        return None
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        return None

async def test_app_slack_notification(slack_service):
    """アプリ経由でのSlack通知テスト"""
    print("\n=== 🧪 アプリ経由通知テスト ===")
    
    if not slack_service:
        print("❌ SlackNotificationServiceが利用できません")
        return False
    
    if not slack_service.enabled:
        print("❌ SlackNotificationServiceが無効です")
        return False
    
    try:
        # テスト通知を送信
        await slack_service.notify_chat_interaction(
            question="テスト質問",
            answer="これはSlack通知のテストです",
            confidence=0.95,
            interaction_type="debug_test",
            ai_generated=True,
            category="debug",
            sources_used=["test_source"]
        )
        
        print("✅ アプリ経由通知テスト実行完了")
        print("   Slackを確認してください（通知が届いているはず）")
        return True
        
    except Exception as e:
        print(f"❌ アプリ経由通知テスト失敗: {e}")
        return False

def check_logs_for_slack_errors():
    """ログからSlack関連エラーを確認"""
    print("\n=== 📋 ログ確認 ===")
    print("以下の点を確認してください：")
    print("1. サーバーログに 'Slack通知' 関連のメッセージがあるか")
    print("2. エラーメッセージが出力されていないか")
    print("3. '[Slack]' というプレフィックスのログがあるか")
    print("\nログ例:")
    print("  INFO:src.app:[Slack] 🤖 AI生成 ai_integrated_search: ...")
    print("  WARNING:src.app:Slack通知失敗: ...")

async def comprehensive_slack_debug():
    """包括的なSlack通知デバッグ"""
    print("🔍 === Slack通知デバッグ開始 ===\n")
    
    # Step 1: 環境変数確認
    webhook_url = check_environment_variables()
    
    # Step 2: 直接Webhookテスト
    if webhook_url:
        direct_test_success = await test_webhook_directly(webhook_url)
    else:
        direct_test_success = False
        print("⚠️ Webhook URLが設定されていないため、直接テストをスキップします")
    
    # Step 3: アプリ内サービス確認
    slack_service = test_app_slack_service()
    
    # Step 4: アプリ経由通知テスト
    if slack_service:
        app_test_success = await test_app_slack_notification(slack_service)
    else:
        app_test_success = False
    
    # Step 5: ログ確認案内
    check_logs_for_slack_errors()
    
    # 総合診断結果
    print("\n" + "="*50)
    print("🎯 === 診断結果 ===")
    
    if webhook_url and direct_test_success and app_test_success:
        print("✅ すべてのテストが成功しました！Slack通知は正常に動作しています。")
    elif webhook_url and direct_test_success and not app_test_success:
        print("⚠️ 直接テストは成功しましたが、アプリ経由のテストが失敗しました。")
        print("   → アプリ内のSlack通知処理に問題がある可能性があります。")
    elif webhook_url and not direct_test_success:
        print("❌ Webhook URLに問題があります。")
        print("   → Slack側の設定を確認してください。")
    else:
        print("❌ Webhook URLが設定されていません。")
        print("   → 環境変数 SLACK_WEBHOOK_URL を設定してください。")
    
    print("\n📝 次のステップ:")
    if not webhook_url:
        print("1. Slack Webhook URLを取得して設定")
        print("2. 環境変数 SLACK_WEBHOOK_URL を設定")
        print("3. アプリケーション再起動")
    elif not direct_test_success:
        print("1. Slack Webhook URLが正しいか確認")
        print("2. Slackアプリの権限設定を確認")
        print("3. ネットワーク接続を確認")
    elif not app_test_success:
        print("1. アプリケーション再起動")
        print("2. ログ詳細確認")
        print("3. 開発者に報告")
    else:
        print("1. 実際にチャット機能を使用してテスト")
        print("2. Slackチャンネルで通知を確認")

if __name__ == "__main__":
    asyncio.run(comprehensive_slack_debug())