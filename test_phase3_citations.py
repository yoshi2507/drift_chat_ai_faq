# test_phase3_citations.py - Phase 3.1 根拠URL表示機能のテスト

"""
Phase 3.1: 根拠URL表示機能の動作確認とデモンストレーション
"""

import asyncio
import json
import aiohttp
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8000"

class Phase3CitationTester:
    """Phase 3.1 引用機能のテスター"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        """非同期コンテキストマネージャー（開始）"""
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャー（終了）"""
        if self.session:
            await self.session.close()
    
    async def test_health_check(self) -> Dict[str, Any]:
        """ヘルスチェックでPhase 3機能を確認"""
        print("📋 1. ヘルスチェック（Phase 3機能確認）")
        
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Phase 3機能の確認
                    phase3_features = data.get('phase3_features', {})
                    citation_service = phase3_features.get('citation_service', False)
                    citation_stats = phase3_features.get('citation_stats', {})
                    
                    print(f"✅ サーバー起動: OK")
                    print(f"📚 引用サービス: {'有効' if citation_service else '無効'}")
                    
                    if citation_stats:
                        print(f"📊 引用統計: {citation_stats}")
                    
                    return {
                        "success": True,
                        "citation_service_available": citation_service,
                        "citation_stats": citation_stats
                    }
                else:
                    print(f"❌ ヘルスチェック失敗: HTTP {response.status}")
                    return {"success": False, "status": response.status}
                    
        except Exception as e:
            print(f"❌ ヘルスチェックエラー: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_citation_debug_endpoint(self) -> Dict[str, Any]:
        """引用デバッグエンドポイントのテスト"""
        print("\n📋 2. 引用デバッグエンドポイント")
        
        try:
            async with self.session.get(f"{self.base_url}/debug/citations") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    print(f"✅ 引用デバッグエンドポイント: OK")
                    
                    # 統計情報
                    stats = data.get('citation_service_stats', {})
                    print(f"📊 キャッシュ済みURL: {stats.get('total_cached_urls', 0)}件")
                    print(f"🔗 アクセス可能URL: {stats.get('accessible_urls', 0)}件")
                    print(f"📈 ヒット率: {stats.get('cache_hit_rate', 0)}%")
                    
                    # サンプル引用情報
                    sample = data.get('sample_citation_extraction', {})
                    if sample:
                        print(f"\n📝 サンプル引用抽出:")
                        extracted = sample.get('extracted_citations', [])
                        print(f"  抽出された引用: {len(extracted)}件")
                        for i, citation in enumerate(extracted, 1):
                            print(f"    {i}. {citation.get('title', 'No Title')} ({citation.get('source_type', 'unknown')})")
                    
                    # PIP-Maker URL提案
                    suggestions = data.get('pip_maker_url_suggestions', [])
                    print(f"\n🔗 PIP-Maker URL提案: {len(suggestions)}件")
                    for suggestion in suggestions:
                        print(f"  - {suggestion.get('title', 'No Title')}: {suggestion.get('url', 'No URL')}")
                    
                    return {"success": True, "data": data}
                else:
                    print(f"❌ 引用デバッグエンドポイント失敗: HTTP {response.status}")
                    return {"success": False, "status": response.status}
                    
        except Exception as e:
            print(f"❌ 引用デバッグエンドポイントエラー: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_search_with_citations(self, queries: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """引用付き検索のテスト"""
        print("\n📋 3. 引用付き検索テスト")
        
        results = []
        
        for i, query_data in enumerate(queries, 1):
            question = query_data['question']
            category = query_data.get('category')
            
            print(f"\n🔍 テスト {i}: {question}")
            if category:
                print(f"   カテゴリー: {category}")
            
            try:
                search_payload = {
                    "question": question,
                    "category": category,
                    "conversation_id": f"test_{i}_{int(datetime.now().timestamp())}"
                }
                
                async with self.session.post(
                    f"{self.base_url}/api/search",
                    json=search_payload
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # 基本結果
                        print(f"✅ 検索成功")
                        print(f"   回答: {data.get('answer', 'No Answer')[:100]}...")
                        print(f"   信頼度: {data.get('confidence', 0):.2f}")
                        print(f"   検索方法: {data.get('method', 'unknown')}")
                        
                        # 引用情報
                        citations = data.get('citations', {})
                        if citations and citations.get('citations'):
                            citation_list = citations['citations']
                            print(f"📚 引用情報: {len(citation_list)}件表示 / {citations.get('total_sources', 0)}件総数")
                            
                            for j, citation in enumerate(citation_list, 1):
                                title = citation.get('title', 'No Title')
                                url = citation.get('url', 'No URL')
                                citation_type = citation.get('type_label', 'Unknown')
                                confidence = citation.get('confidence', 0)
                                verified = "✓" if citation.get('verified') else "○"
                                
                                print(f"   {j}. [{verified}] {title} ({citation_type}) - 信頼度: {confidence:.2f}")
                                if url and url != "No URL":
                                    print(f"      URL: {url}")
                        else:
                            print(f"📚 引用情報: なし")
                        
                        # 検証済みソース
                        verified_sources = data.get('verified_sources', 0)
                        total_sources = data.get('source_count', 0)
                        print(f"🔍 検証済みソース: {verified_sources}/{total_sources}件")
                        
                        results.append({
                            "success": True,
                            "query": question,
                            "category": category,
                            "answer_length": len(data.get('answer', '')),
                            "confidence": data.get('confidence', 0),
                            "method": data.get('method', 'unknown'),
                            "citation_count": len(citations.get('citations', [])) if citations else 0,
                            "total_sources": citations.get('total_sources', 0) if citations else 0,
                            "verified_sources": verified_sources,
                            "has_citations": bool(citations and citations.get('citations'))
                        })
                        
                    else:
                        error_text = await response.text()
                        print(f"❌ 検索失敗: HTTP {response.status}")
                        print(f"   エラー: {error_text[:200]}...")
                        
                        results.append({
                            "success": False,
                            "query": question,
                            "category": category,
                            "status": response.status,
                            "error": error_text[:200]
                        })
                        
            except Exception as e:
                print(f"❌ 検索エラー: {e}")
                results.append({
                    "success": False,
                    "query": question,
                    "category": category,
                    "error": str(e)
                })
        
        return results
    
    async def test_url_verification(self) -> Dict[str, Any]:
        """URL検証機能のテスト"""
        print("\n📋 4. URL検証機能テスト")
        
        try:
            async with self.session.post(f"{self.base_url}/admin/citations/verify-urls") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    print(f"✅ URL検証エンドポイント: OK")
                    
                    # 検証結果
                    verification_results = data.get('verification_results', [])
                    print(f"🔍 検証されたURL: {len(verification_results)}件")
                    
                    accessible_count = 0
                    for result in verification_results:
                        url = result.get('url', '')
                        accessible = result.get('accessible', False)
                        status = result.get('status', 'unknown')
                        
                        status_icon = "✅" if accessible else "❌"
                        print(f"   {status_icon} {url[:50]}... - {status}")
                        
                        if accessible:
                            accessible_count += 1
                    
                    # 統計
                    cache_stats = data.get('cache_stats', {})
                    print(f"\n📊 キャッシュ統計:")
                    print(f"   総キャッシュ数: {cache_stats.get('total_cached_urls', 0)}")
                    print(f"   アクセス可能数: {cache_stats.get('accessible_urls', 0)}")
                    print(f"   ヒット率: {cache_stats.get('cache_hit_rate', 0)}%")
                    
                    success_rate = accessible_count / max(len(verification_results), 1) * 100
                    print(f"   今回の成功率: {success_rate:.1f}%")
                    
                    return {
                        "success": True,
                        "verified_count": len(verification_results),
                        "accessible_count": accessible_count,
                        "success_rate": success_rate,
                        "cache_stats": cache_stats
                    }
                else:
                    print(f"❌ URL検証エンドポイント失敗: HTTP {response.status}")
                    return {"success": False, "status": response.status}
                    
        except Exception as e:
            print(f"❌ URL検証エラー: {e}")
            return {"success": False, "error": str(e)}
    
    def print_test_summary(self, results: Dict[str, Any]):
        """テスト結果のサマリーを表示"""
        print("\n" + "="*60)
        print("🎯 Phase 3.1 テスト結果サマリー")
        print("="*60)
        
        # ヘルスチェック
        health = results.get('health', {})
        if health.get('success'):
            citation_available = health.get('citation_service_available', False)
            print(f"🟢 ヘルスチェック: OK (引用サービス: {'有効' if citation_available else '無効'})")
        else:
            print(f"🔴 ヘルスチェック: FAILED")
        
        # 引用デバッグ
        debug = results.get('debug', {})
        if debug.get('success'):
            print(f"🟢 引用デバッグエンドポイント: OK")
        else:
            print(f"🔴 引用デバッグエンドポイント: FAILED")
        
        # 検索テスト
        searches = results.get('searches', [])
        if searches:
            successful_searches = [s for s in searches if s.get('success')]
            searches_with_citations = [s for s in successful_searches if s.get('has_citations')]
            
            print(f"🟢 検索テスト: {len(successful_searches)}/{len(searches)}件成功")
            print(f"📚 引用付き回答: {len(searches_with_citations)}/{len(successful_searches)}件")
            
            if successful_searches:
                avg_confidence = sum(s.get('confidence', 0) for s in successful_searches) / len(successful_searches)
                total_citations = sum(s.get('citation_count', 0) for s in successful_searches)
                total_verified = sum(s.get('verified_sources', 0) for s in successful_searches)
                
                print(f"📊 平均信頼度: {avg_confidence:.2f}")
                print(f"📚 総引用数: {total_citations}件")
                print(f"🔍 検証済み: {total_verified}件")
        
        # URL検証
        url_verification = results.get('url_verification', {})
        if url_verification.get('success'):
            success_rate = url_verification.get('success_rate', 0)
            print(f"🟢 URL検証: OK (成功率: {success_rate:.1f}%)")
        else:
            print(f"🔴 URL検証: FAILED")
        
        # 総合評価
        all_tests = [
            health.get('success', False),
            debug.get('success', False),
            len([s for s in searches if s.get('success')]) > 0 if searches else False,
            url_verification.get('success', False)
        ]
        
        success_count = sum(all_tests)
        total_tests = len(all_tests)
        
        print(f"\n🎯 総合評価: {success_count}/{total_tests}件のテストが成功")
        
        if success_count == total_tests:
            print("🎉 Phase 3.1 根拠URL表示機能は正常に動作しています！")
        elif success_count >= total_tests * 0.75:
            print("⚠️ Phase 3.1 機能は概ね動作していますが、一部改善が必要です。")
        else:
            print("❌ Phase 3.1 機能に問題があります。設定とログを確認してください。")

async def main():
    """メインテスト実行"""
    print("🧪 Phase 3.1: 根拠URL表示機能テスト開始")
    print("=" * 60)
    
    # テスト用クエリ
    test_queries = [
        {
            "question": "PIP-Makerとは何ですか？",
            "category": "about"
        },
        {
            "question": "PIP-Makerの機能を教えてください",
            "category": "features"
        },
        {
            "question": "PIP-Makerの導入事例はありますか？",
            "category": "cases"
        },
        {
            "question": "PIP-Makerの料金プランについて教えてください",
            "category": "pricing"
        },
        {
            "question": "PIP-Makerのサポート体制はどうなっていますか？",
            "category": "other"
        }
    ]
    
    results = {}
    
    async with Phase3CitationTester() as tester:
        # 1. ヘルスチェック
        results['health'] = await tester.test_health_check()
        
        # 2. 引用デバッグエンドポイント
        results['debug'] = await tester.test_citation_debug_endpoint()
        
        # 3. 引用付き検索テスト
        results['searches'] = await tester.test_search_with_citations(test_queries)
        
        # 4. URL検証テスト
        results['url_verification'] = await tester.test_url_verification()
        
        # 5. 結果サマリー表示
        tester.print_test_summary(results)
    
    # 詳細結果をJSONファイルに保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"phase3_test_results_{timestamp}.json"
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n📄 詳細結果を {output_file} に保存しました")
    except Exception as e:
        print(f"⚠️ 結果ファイルの保存に失敗: {e}")

if __name__ == "__main__":
    asyncio.run(main())