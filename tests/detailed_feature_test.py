# detailed_feature_test.py - 詳細機能テスト

"""
実装済み機能の詳細動作確認
"""

async def test_openai_usage_stats():
    """OpenAI使用統計の詳細確認"""
    print("=== 🤖 OpenAI使用統計詳細確認 ===")
    
    try:
        from src.app import openai_service
        
        if openai_service and hasattr(openai_service, 'get_usage_stats'):
            stats = openai_service.get_usage_stats()
            print("✅ OpenAI使用統計:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
            
            # 制限チェック機能の確認
            if hasattr(openai_service, 'usage_tracker'):
                tracker = openai_service.usage_tracker
                if hasattr(tracker, 'can_make_request'):
                    can_request, reason = tracker.can_make_request(openai_service.config)
                    print(f"✅ API制限チェック: {can_request} - {reason}")
                else:
                    print("⚠️ can_make_request メソッドなし")
            else:
                print("⚠️ usage_tracker なし")
        else:
            print("❌ OpenAI使用統計機能なし")
            
    except Exception as e:
        print(f"❌ OpenAI使用統計エラー: {e}")

def test_slack_notification_stats():
    """Slack通知統計の詳細確認"""
    print("\n=== 📱 Slack通知統計詳細確認 ===")
    
    try:
        from src.app import slack_service
        
        if hasattr(slack_service, 'get_notification_stats'):
            stats = slack_service.get_notification_stats()
            print("✅ Slack通知統計:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        else:
            print("❌ Slack通知統計機能なし")
            
    except Exception as e:
        print(f"❌ Slack通知統計エラー: {e}")

async def test_slack_test_notification():
    """Slackテスト通知の実行"""
    print("\n=== 📤 Slackテスト通知実行 ===")
    
    try:
        from src.app import slack_service
        
        if hasattr(slack_service, 'test_notification'):
            print("📤 テスト通知送信中...")
            success = await slack_service.test_notification()
            print(f"✅ テスト通知結果: {'成功' if success else '失敗'}")
            print("Slackチャンネルを確認してください")
        else:
            print("❌ テスト通知機能なし")
            
    except Exception as e:
        print(f"❌ テスト通知エラー: {e}")

def check_debug_endpoints():
    """デバッグエンドポイントの確認"""
    print("\n=== 🔍 デバッグエンドポイント確認 ===")
    
    try:
        import requests
        base_url = "http://localhost:8000"
        
        endpoints = [
            ("/health", "ヘルスチェック"),
            ("/debug/ai-status", "AI統計"),
            ("/debug/slack-status", "Slack統計"),
            ("/debug/status", "総合デバッグ")
        ]
        
        for endpoint, name in endpoints:
            try:
                response = requests.get(f"{base_url}{endpoint}", timeout=5)
                if response.status_code == 200:
                    print(f"✅ {endpoint} ({name}): 正常")
                    
                    # AI統計の詳細表示
                    if endpoint == "/debug/ai-status":
                        data = response.json()
                        ai_features = data.get('ai_features', {})
                        print(f"  AI機能: {ai_features}")
                    
                    # Slack統計の詳細表示
                    elif endpoint == "/debug/slack-status":
                        data = response.json()
                        slack_stats = data.get('slack_service', {})
                        print(f"  Slack統計: {slack_stats}")
                        
                else:
                    print(f"⚠️ {endpoint}: HTTP {response.status_code}")
            except Exception as e:
                print(f"❌ {endpoint}: {e}")
                
    except ImportError:
        print("⚠️ requests ライブラリが必要: pip install requests")
    except Exception as e:
        print(f"❌ エンドポイント確認エラー: {e}")

async def test_chat_interaction():
    """チャット対話のテスト"""
    print("\n=== 💬 チャット対話テスト ===")
    
    try:
        from src.app import category_search_engine, slack_service
        
        if category_search_engine:
            print("🤖 AI統合検索テスト実行中...")
            
            test_query = "PIP-Makerの料金について教えてください"
            result = await category_search_engine.search_with_category_context(
                query=test_query,
                use_ai_generation=True
            )
            
            print(f"✅ 検索結果:")
            print(f"  質問: {test_query}")
            print(f"  回答: {result['answer'][:100]}...")
            print(f"  信頼度: {result['confidence']:.2f}")
            print(f"  カテゴリー: {result.get('category', 'unknown')}")
            print(f"  AI生成: {result.get('ai_generated', False)}")
            
            # Slack通知のテスト
            if slack_service:
                print("\n📱 Slack通知テスト送信中...")
                await slack_service.notify_chat_interaction(
                    question=test_query,
                    answer=result['answer'],
                    confidence=result['confidence'],
                    interaction_type="test",
                    ai_generated=result.get('ai_generated', False),
                    category=result.get('category', 'test'),
                    sources_used=result.get('sources_used', [])
                )
                print("✅ Slack通知送信完了")
        else:
            print("❌ カテゴリー検索エンジンが利用できません")
            
    except Exception as e:
        print(f"❌ チャット対話テストエラー: {e}")

async def main():
    """メイン実行"""
    print("🧪 === Phase 2 詳細機能テスト ===\n")
    
    # OpenAI統計確認
    await test_openai_usage_stats()
    
    # Slack統計確認
    test_slack_notification_stats()
    
    # Slackテスト通知
    await test_slack_test_notification()
    
    # デバッグエンドポイント確認
    check_debug_endpoints()
    
    # チャット対話テスト
    await test_chat_interaction()
    
    print(f"\n🎯 === テスト完了 ({datetime.now().strftime('%H:%M:%S')}) ===")
    print("Slackチャンネルでリッチ通知が届いているか確認してください！")

if __name__ == "__main__":
    import asyncio
    from datetime import datetime
    
    asyncio.run(main())