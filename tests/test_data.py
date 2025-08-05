import asyncio
from src.config import create_data_service

async def test():
    service = create_data_service()
    data = await service.get_qa_data()
    
    print(f"取得したデータ数: {len(data)}")
    print("=" * 50)
    
    for i, row in enumerate(data):
        question = row.get('question', '')
        answer = row.get('answer', '')
        
        # テストや改行を含む質問を探す
        if any(keyword in question.lower() for keyword in ['テスト', '改行', 'test']) or '\n' in answer:
            print(f"行 {i+1}:")
            print(f"質問: {question}")
            print(f"回答: {repr(answer)}")  # repr() で改行文字が見える
            print(f"回答（実際）: {answer}")
            print("-" * 30)
    
    # 全データの最初の3件も表示
    print("\n=== 最初の3件のデータ ===")
    for i, row in enumerate(data[:3]):
        print(f"行 {i+1}:")
        print(f"質問: {row.get('question', '')}")
        print(f"回答: {repr(row.get('answer', ''))}")
        print("-" * 30)

if __name__ == "__main__":
    asyncio.run(test())