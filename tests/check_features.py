# check_features.py
try:
    from src.app import slack_service, openai_service
    
    print("=== Slackサービス確認 ===")
    print(f"サービスタイプ: {type(slack_service).__name__}")
    print(f"enabled: {getattr(slack_service, 'enabled', 'unknown')}")
    print(f"get_notification_stats: {hasattr(slack_service, 'get_notification_stats')}")
    print(f"test_notification: {hasattr(slack_service, 'test_notification')}")
    
    print("\n=== OpenAIサービス確認 ===")
    print(f"OpenAI available: {openai_service is not None}")
    if openai_service:
        print(f"usage_tracker: {hasattr(openai_service, 'usage_tracker')}")
        print(f"get_usage_stats: {hasattr(openai_service, 'get_usage_stats')}")
    
except Exception as e:
    print(f"エラー: {e}")