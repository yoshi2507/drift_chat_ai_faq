# test_sheets_connection.py
import asyncio
from src.google_sheets_service import GoogleSheetsService

async def test_connection():
    service = GoogleSheetsService(
        spreadsheet_id="your-spreadsheet-id",
        credentials_path="credentials/google-service-account.json"
    )
    
    try:
        data = await service.get_qa_data()
        print(f"✅ 接続成功！{len(data)}件のデータを取得")
        
        # サンプルデータ表示
        if data:
            print(f"サンプル: {data[0]}")
            
    except Exception as e:
        print(f"❌ 接続失敗: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())