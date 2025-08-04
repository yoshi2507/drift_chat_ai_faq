"""
PIP-Maker チャットボットアプリケーションのテスト
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

# アプリケーションのインポート
try:
    from src.app import app, sheet_service
except ImportError as e:
    print(f"インポートエラー: {e}")
    print(f"現在のPythonパス: {sys.path}")
    print(f"プロジェクトルート: {project_root}")
    raise

client = TestClient(app)


def test_health_endpoint():
    """ヘルスチェックエンドポイントのテスト"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_index_endpoint():
    """インデックスHTMLページのテスト"""
    response = client.get("/")
    # index.htmlが存在する場合は200、存在しない場合は404
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_search_endpoint_success():
    """検索リクエスト成功時のテスト"""
    mock_qa_data = [
        {
            "question": "PIP-Makerとは何ですか？",
            "answer": "PIP-Makerは素晴らしいツールです。",
            "category": "general",
            "source": "公式サイト",
            "notes": ""
        }
    ]
    
    with patch.object(sheet_service, 'get_qa_data', return_value=mock_qa_data):
        response = client.post(
            "/api/search",
            json={"question": "PIP-Makerとは"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "confidence" in data
        assert data["confidence"] > 0


@pytest.mark.asyncio
async def test_search_endpoint_no_match():
    """マッチする結果がない検索リクエストのテスト"""
    mock_qa_data = [
        {
            "question": "コンピューターサイエンスの理論",
            "answer": "専門的な回答",
            "category": "technical",
            "source": "",
            "notes": ""
        }
    ]
    
    with patch.object(sheet_service, 'get_qa_data', return_value=mock_qa_data):
        response = client.post(
            "/api/search",
            json={"question": "料理のレシピについて教えて"}
        )
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert "error_id" in data


@pytest.mark.asyncio
async def test_search_endpoint_empty_data():
    """空のQ&Aデータでの検索リクエストのテスト"""
    with patch.object(sheet_service, 'get_qa_data', return_value=[]):
        response = client.post(
            "/api/search",
            json={"question": "何でも質問"}
        )
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "システムエラーが発生しました。"


def test_search_endpoint_invalid_input():
    """無効な入力での検索リクエストのテスト"""
    response = client.post(
        "/api/search",
        json={"invalid_field": "test"}
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data


def test_feedback_endpoint_success():
    """フィードバック送信成功時のテスト"""
    response = client.post(
        "/api/feedback",
        json={
            "conversation_id": "test123",
            "rating": "positive",
            "comment": "とても役に立ちました！"
        }
    )
    assert response.status_code == 200
    assert response.json() == {"status": "received"}


def test_feedback_endpoint_invalid_rating():
    """無効な評価でのフィードバック送信のテスト"""
    response = client.post(
        "/api/feedback",
        json={
            "conversation_id": "test123",
            "rating": "invalid_rating",
            "comment": "テスト"
        }
    )
    assert response.status_code == 422


def test_feedback_endpoint_missing_fields():
    """必須フィールドが欠けているフィードバック送信のテスト"""
    response = client.post(
        "/api/feedback",
        json={"rating": "positive"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_csv_field_mapping():
    """CSVフィールドマッピング（日本語→英語キー）のテスト"""
    mock_csv_data = {
        "質問": "テスト質問",
        "回答": "テスト回答", 
        "対応カテゴリー": "テスト",
        "根拠資料": "テスト資料",
        "備考": "テスト備考"
    }
    
    normalized = sheet_service._normalize_row(mock_csv_data)
    
    assert normalized["question"] == "テスト質問"
    assert normalized["answer"] == "テスト回答"
    assert normalized["category"] == "テスト"
    assert normalized["source"] == "テスト資料"
    assert normalized["notes"] == "テスト備考"


@pytest.mark.asyncio
async def test_sheet_service_file_not_found():
    """CSVファイルが見つからない場合のGoogleSheetsServiceのテスト"""
    from src.app import GoogleSheetsService, SheetAccessException
    
    service = GoogleSheetsService("nonexistent.csv")
    
    with pytest.raises(SheetAccessException) as exc_info:
        await service.get_qa_data()
    
    assert "CSVファイルが見つかりません" in str(exc_info.value)


@pytest.mark.asyncio
async def test_slack_notification_service():
    """Slack通知サービス（スタブ）のテスト"""
    from src.app import SlackNotificationService
    
    service = SlackNotificationService()
    
    # これらのメソッドは現在ログ出力のみなので、例外が発生しないことを確認
    await service.notify_chat_interaction(
        question="テスト質問",
        answer="テスト回答", 
        confidence=0.8,
        user_info={"ip": "127.0.0.1"}
    )
    
    await service.notify_negative_feedback({
        "conversation_id": "test123",
        "rating": "negative",
        "comment": "役に立たなかった"
    })


@pytest.mark.asyncio
async def test_search_service_category_filter():
    """カテゴリフィルターを使用した検索サービスのテスト"""
    from src.app import SearchService, GoogleSheetsService
    
    mock_qa_data = [
        {
            "question": "一般的な質問",
            "answer": "一般的な回答",
            "category": "general",
            "source": "",
            "notes": ""
        },
        {
            "question": "技術的な質問", 
            "answer": "技術的な回答",
            "category": "technical",
            "source": "",
            "notes": ""
        }
    ]
    
    mock_service = GoogleSheetsService("dummy.csv")
    with patch.object(mock_service, 'get_qa_data', return_value=mock_qa_data):
        search_service_instance = SearchService(mock_service)
        
        # カテゴリフィルター適用のテスト
        result = await search_service_instance.search("技術", category="technical")
        assert "技術的な回答" in result.answer
        
        # 異なるカテゴリでは見つからないことのテスト
        with pytest.raises(Exception):  # SearchExceptionが期待される
            await search_service_instance.search("技術", category="general")


@pytest.mark.asyncio 
async def test_search_endpoint_low_confidence():
    """低い信頼度でのマッチングテスト"""
    mock_qa_data = [
        {
            "question": "PIP-Makerの機能について",
            "answer": "機能の説明です",
            "category": "general",
            "source": "",
            "notes": ""
        }
    ]
    
    with patch.object(sheet_service, 'get_qa_data', return_value=mock_qa_data):
        response = client.post(
            "/api/search",
            json={"question": "PIP-Maker"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "confidence" in data
        # 部分的なマッチでも閾値を超えていることを確認
        assert data["confidence"] >= 0.1


if __name__ == "__main__":
    # テストファイルを直接実行する場合
    pytest.main([__file__, "-v"])