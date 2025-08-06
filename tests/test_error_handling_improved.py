# test_error_handling.py - エラーハンドリングテスト用スクリプト

"""
エラーハンドリングの動作確認用テストスクリプト
各種エラーシナリオをテストします
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
import json
import aiohttp
import requests
import sys
import os

BASE_URL = "http://localhost:8000"

async def test_api_endpoint(session, endpoint, method="GET", data=None, expected_status=200, test_name=""):
    """APIエンドポイントのテスト（改善版）"""
    try:
        timeout = aiohttp.ClientTimeout(total=10)  # 🔧 タイムアウト設定
        
        if method == "POST":
            async with session.post(
                f"{BASE_URL}{endpoint}", 
                json=data,
                timeout=timeout
            ) as response:
                status = response.status
                try:
                    content = await response.json()
                    message = content.get('error', content.get('answer', 'Success'))
                except:
                    content = await response.text()
                    message = content[:100] + "..." if len(content) > 100 else content
                    
                print(f"✅ {test_name or endpoint}: {status} - {message}")
                return status, content
        else:
            async with session.get(f"{BASE_URL}{endpoint}", timeout=timeout) as response:
                status = response.status
                if response.content_type == 'application/json':
                    content = await response.json()
                else:
                    content = await response.text()
                print(f"✅ {test_name or endpoint}: {status}")
                return status, content
                
    except asyncio.TimeoutError:
        print(f"⏰ {test_name or endpoint}: タイムアウト")
        return None, "timeout"
    except aiohttp.ClientConnectorError as e:
        print(f"🔌 {test_name or endpoint}: 接続エラー - サーバーが起動していることを確認してください")
        return None, f"connection_error: {e}"
    except Exception as e:
        print(f"❌ {test_name or endpoint}: Exception - {e}")
        return None, str(e)

async def run_improved_tests():
    """改善されたエラーハンドリングテスト"""
    
    print("🧪 === 改善版エラーハンドリングテスト ===\n")
    
    # 🔧 接続設定を改善
    connector = aiohttp.TCPConnector(
        limit=10,
        limit_per_host=5,
        keepalive_timeout=30,
        enable_cleanup_closed=True
    )
    
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout
    ) as session:
        
        # === 1. 正常動作テスト ===
        print("📋 1. 正常動作テスト")
        
        await test_api_endpoint(session, "/health", test_name="ヘルスチェック")
        await test_api_endpoint(session, "/api/conversation/welcome", test_name="歓迎メッセージ")
        await test_api_endpoint(
            session, 
            "/api/search", 
            method="POST",
            data={"question": "PIP-Makerとは何ですか？"},
            test_name="正常な検索"
        )
        
        print("\n" + "="*60 + "\n")
        
        # === 2. 改善された検索エラーテスト ===
        print("📋 2. 検索エラーテスト（改善版）")
        
        # 空の質問
        await test_api_endpoint(
            session,
            "/api/search",
            method="POST", 
            data={"question": ""},
            test_name="空の質問"
        )
        
        # 短すぎる質問
        await test_api_endpoint(
            session,
            "/api/search",
            method="POST", 
            data={"question": "a"},
            test_name="短い質問"
        )
        
        # 存在しない質問  
        await test_api_endpoint(
            session,
            "/api/search",
            method="POST",
            data={"question": "完全に存在しない質問xyzabc123"},
            test_name="存在しない質問"
        )
        
        print("\n" + "="*60 + "\n")
        
        # === 3. 対話フローエラーテスト ===
        print("📋 3. 対話フローエラーテスト")
        
        # 正常なカテゴリー選択
        await test_api_endpoint(
            session,
            "/api/conversation/category",
            method="POST",
            data={"conversation_id": "test_123", "category_id": "about"},
            test_name="正常なカテゴリー選択"
        )
        
        # 無効なカテゴリーID
        await test_api_endpoint(
            session,
            "/api/conversation/category",
            method="POST",
            data={"conversation_id": "test_123", "category_id": "invalid_category"},
            test_name="無効なカテゴリー"
        )
        
        print("\n🎉 改善版テスト完了!")

if __name__ == "__main__":
    print("🚀 改善版エラーハンドリングテストを開始...")
    
    # サーバー接続確認
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ サーバー接続確認完了\n")
        else:
            print("❌ サーバーが正常に応答していません")
            sys.exit(1)
    except Exception as e:
        print(f"❌ サーバーに接続できません: {e}")
        print("サーバーを起動してから再度実行してください")
        sys.exit(1)
    
    asyncio.run(run_improved_tests())