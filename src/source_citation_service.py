# src/source_citation_service.py - Phase 3.1 根拠URL表示機能

"""
Phase 3.1: 根拠URL表示機能
回答の信頼性向上とユーザー体験改善のための情報源引用システム
"""

import logging
import re
import aiohttp
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, HttpUrl
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
from enum import Enum

LOGGER = logging.getLogger(__name__)

class SourceType(str, Enum):
    """情報源の種類"""
    INTERNAL_DATA = "internal_data"      # 内部Q&Aデータ
    OFFICIAL_WEBSITE = "official_website" # 公式サイト
    PDF_MANUAL = "pdf_manual"            # PDFマニュアル
    FAQ = "faq"                          # FAQ
    DOCUMENTATION = "documentation"      # ドキュメント
    BLOG_POST = "blog_post"             # ブログ記事
    UNKNOWN = "unknown"                  # 不明

@dataclass
class SourceCitation:
    """情報源の引用情報"""
    title: str
    url: str
    source_type: SourceType
    confidence: float
    last_verified: Optional[datetime] = None
    excerpt: Optional[str] = None
    section: Optional[str] = None
    page_number: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "title": self.title,
            "url": self.url,
            "source_type": self.source_type.value,
            "confidence": self.confidence,
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
            "excerpt": self.excerpt,
            "section": self.section,
            "page_number": self.page_number
        }

class SourceCitationService:
    """根拠URL表示とソース管理サービス"""
    
    def __init__(self):
        """初期化"""
        self.pip_maker_base_url = "https://www.pip-maker.com"
        self.manual_base_url = "https://info.pip-maker.com/manual"
        
        # URL検証キャッシュ（24時間）
        self.url_cache: Dict[str, Tuple[bool, datetime]] = {}
        self.cache_duration = timedelta(hours=24)
        
        # PIP-Maker関連のURL パターン
        self.pip_maker_patterns = [
            r"pip-maker\.com",
            r"info\.pip-maker\.com",
            r"support\.pip-maker\.com",
            r"blog\.pip-maker\.com"
        ]
        
        LOGGER.info("✅ SourceCitationService initialized")
    
    def classify_source_type(self, url: str, content_type: str = "") -> SourceType:
        """URLと内容からソースタイプを分類"""
        url_lower = url.lower()
        
        if any(re.search(pattern, url_lower) for pattern in self.pip_maker_patterns):
            if "faq" in url_lower or "よくある質問" in content_type:
                return SourceType.FAQ
            elif ".pdf" in url_lower or "manual" in url_lower:
                return SourceType.PDF_MANUAL
            elif "doc" in url_lower or "guide" in url_lower:
                return SourceType.DOCUMENTATION
            elif "blog" in url_lower or "news" in url_lower:
                return SourceType.BLOG_POST
            else:
                return SourceType.OFFICIAL_WEBSITE
        
        return SourceType.UNKNOWN
    
    async def verify_url_accessibility(self, url: str) -> Tuple[bool, str]:
        """URLのアクセス可能性を検証"""
        
        # キャッシュから確認
        if url in self.url_cache:
            is_accessible, cached_time = self.url_cache[url]
            if datetime.now() - cached_time < self.cache_duration:
                return is_accessible, "cached"
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.head(url) as response:
                    is_accessible = response.status < 400
                    status_info = f"HTTP {response.status}"
                    
                    # キャッシュに保存
                    self.url_cache[url] = (is_accessible, datetime.now())
                    
                    return is_accessible, status_info
                    
        except aiohttp.ClientError as e:
            LOGGER.warning(f"URL検証失敗: {url} - {e}")
            self.url_cache[url] = (False, datetime.now())
            return False, f"接続エラー: {type(e).__name__}"
        except Exception as e:
            LOGGER.error(f"URL検証エラー: {url} - {e}")
            self.url_cache[url] = (False, datetime.now())
            return False, f"検証エラー: {str(e)}"
    
    def extract_citations_from_qa_data(self, qa_item: Dict[str, str]) -> List[SourceCitation]:
        """Q&Aデータから引用情報を抽出"""
        citations = []
        
        # 根拠資料フィールドから URL を抽出
        source_field = qa_item.get('source', '') or qa_item.get('根拠資料', '')
        
        if source_field:
            # URL パターンマッチング
            url_pattern = r'https?://[^\s\)]+(?:\([^\)]*\))?[^\s\)]*'
            urls = re.findall(url_pattern, source_field)
            
            for url in urls:
                # 不要な文字を削除
                url = url.rstrip('.,;)')
                
                citation = SourceCitation(
                    title=self._extract_title_from_source(source_field, url),
                    url=url,
                    source_type=self.classify_source_type(url, qa_item.get('category', '')),
                    confidence=0.9,  # 内部データなので高信頼度
                    excerpt=qa_item.get('answer', '')[:200],
                    section=qa_item.get('category', '')
                )
                citations.append(citation)
        
        # URLがない場合は内部データとして記録
        if not citations:
            citation = SourceCitation(
                title=qa_item.get('question', 'PIP-Maker Q&A'),
                url="",  # 内部データなのでURLなし
                source_type=SourceType.INTERNAL_DATA,
                confidence=0.8,
                excerpt=qa_item.get('answer', '')[:200],
                section=qa_item.get('category', '')
            )
            citations.append(citation)
        
        return citations
    
    def _extract_title_from_source(self, source_text: str, url: str) -> str:
        """ソーステキストからタイトルを抽出"""
        
        # URLの前後のテキストからタイトルを推測
        parts = source_text.split(url)
        
        if len(parts) >= 2:
            # URLの前のテキスト
            before = parts[0].strip().rstrip('-()')
            if before and len(before) > 5:
                return before[-50:]  # 最後の50文字
        
        # URLからタイトルを推測
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        
        if path_parts and path_parts[-1]:
            title = path_parts[-1].replace('-', ' ').replace('_', ' ')
            title = title.replace('.html', '').replace('.pdf', '')
            return title.title()
        
        return parsed.netloc or "参考資料"
    
    async def enhance_citations_with_verification(
        self, 
        citations: List[SourceCitation]
    ) -> List[SourceCitation]:
        """引用情報をURL検証で強化"""
        
        enhanced_citations = []
        
        for citation in citations:
            if citation.url:
                try:
                    is_accessible, status = await self.verify_url_accessibility(citation.url)
                    
                    if is_accessible:
                        citation.last_verified = datetime.now()
                        citation.confidence = min(citation.confidence + 0.1, 1.0)
                    else:
                        citation.confidence = max(citation.confidence - 0.2, 0.3)
                        LOGGER.warning(f"URL not accessible: {citation.url} - {status}")
                        
                except Exception as e:
                    LOGGER.error(f"Citation verification error: {e}")
                    citation.confidence = max(citation.confidence - 0.1, 0.3)
            
            enhanced_citations.append(citation)
        
        return enhanced_citations
    
    def format_citations_for_display(
        self, 
        citations: List[SourceCitation],
        max_citations: int = 3
    ) -> Dict[str, Any]:
        """表示用に引用情報をフォーマット"""
        
        # 信頼度とソースタイプで並び替え
        sorted_citations = sorted(
            citations, 
            key=lambda c: (c.source_type != SourceType.INTERNAL_DATA, -c.confidence)
        )
        
        # 表示する引用を選択
        display_citations = sorted_citations[:max_citations]
        
        formatted_citations = []
        for i, citation in enumerate(display_citations, 1):
            formatted = {
                "id": f"source_{i}",
                "title": citation.title,
                "url": citation.url if citation.url else None,
                "type": citation.source_type.value,
                "type_label": self._get_source_type_label(citation.source_type),
                "confidence": round(citation.confidence, 2),
                "excerpt": citation.excerpt,
                "section": citation.section,
                "verified": citation.last_verified is not None,
                "icon": self._get_source_icon(citation.source_type)
            }
            formatted_citations.append(formatted)
        
        return {
            "citations": formatted_citations,
            "total_sources": len(citations),
            "showing": len(display_citations),
            "has_more": len(citations) > max_citations
        }
    
    def _get_source_type_label(self, source_type: SourceType) -> str:
        """ソースタイプのラベルを取得"""
        labels = {
            SourceType.INTERNAL_DATA: "内部データ",
            SourceType.OFFICIAL_WEBSITE: "公式サイト",
            SourceType.PDF_MANUAL: "PDFマニュアル",
            SourceType.FAQ: "よくある質問",
            SourceType.DOCUMENTATION: "ドキュメント",
            SourceType.BLOG_POST: "ブログ記事",
            SourceType.UNKNOWN: "参考資料"
        }
        return labels.get(source_type, "参考資料")
    
    def _get_source_icon(self, source_type: SourceType) -> str:
        """ソースタイプのアイコンを取得"""
        icons = {
            SourceType.INTERNAL_DATA: "📊",
            SourceType.OFFICIAL_WEBSITE: "🌐",
            SourceType.PDF_MANUAL: "📄",
            SourceType.FAQ: "❓",
            SourceType.DOCUMENTATION: "📚",
            SourceType.BLOG_POST: "📝",
            SourceType.UNKNOWN: "🔗"
        }
        return icons.get(source_type, "🔗")
    
    async def enrich_search_result_with_citations(
        self, 
        search_result: Dict[str, Any], 
        qa_items: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """検索結果に引用情報を追加"""
        
        all_citations = []
        
        # 各Q&Aアイテムから引用を抽出
        for qa_item in qa_items:
            citations = self.extract_citations_from_qa_data(qa_item)
            all_citations.extend(citations)
        
        # 引用情報を検証・強化
        enhanced_citations = await self.enhance_citations_with_verification(all_citations)
        
        # 表示用にフォーマット
        citation_display = self.format_citations_for_display(enhanced_citations)
        
        # 検索結果に追加
        enriched_result = search_result.copy()
        enriched_result["citations"] = citation_display
        enriched_result["source_count"] = len(enhanced_citations)
        enriched_result["verified_sources"] = len([c for c in enhanced_citations if c.last_verified])
        
        return enriched_result
    
    def generate_pip_maker_related_urls(self, query: str, category: str = "") -> List[SourceCitation]:
        """PIP-Maker関連のおすすめURLを生成"""
        
        query_lower = query.lower()
        category_lower = category.lower() if category else ""
        
        suggested_citations = []
        
        # カテゴリーベースの提案
        if "about" in category_lower or "概要" in query_lower or "とは" in query_lower:
            suggested_citations.append(SourceCitation(
                title="PIP-Maker製品概要",
                url="https://www.pip-maker.com/product",
                source_type=SourceType.OFFICIAL_WEBSITE,
                confidence=0.8
            ))
        
        if "cases" in category_lower or "事例" in query_lower:
            suggested_citations.append(SourceCitation(
                title="PIP-Maker導入事例",
                url="https://www.pip-maker.com/case-studies",
                source_type=SourceType.OFFICIAL_WEBSITE,
                confidence=0.8
            ))
        
        if "features" in category_lower or "機能" in query_lower:
            suggested_citations.append(SourceCitation(
                title="PIP-Maker機能一覧",
                url="https://www.pip-maker.com/features",
                source_type=SourceType.OFFICIAL_WEBSITE,
                confidence=0.8
            ))
            
            suggested_citations.append(SourceCitation(
                title="PIP-Maker操作マニュアル",
                url="https://info.pip-maker.com/manual/pdf/PIP-Maker_creator.pdf",
                source_type=SourceType.PDF_MANUAL,
                confidence=0.9
            ))
        
        if "pricing" in category_lower or "料金" in query_lower or "価格" in query_lower:
            suggested_citations.append(SourceCitation(
                title="PIP-Maker料金プラン",
                url="https://www.pip-maker.com/pricing",
                source_type=SourceType.OFFICIAL_WEBSITE,
                confidence=0.9
            ))
        
        # 常に含める基本的な参考URL
        if not suggested_citations:
            suggested_citations.append(SourceCitation(
                title="PIP-Maker公式サイト",
                url="https://www.pip-maker.com/",
                source_type=SourceType.OFFICIAL_WEBSITE,
                confidence=0.7
            ))
        
        return suggested_citations
    
    async def get_comprehensive_citations(
        self, 
        query: str, 
        category: str,
        qa_results: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """包括的な引用情報を取得"""
        
        all_citations = []
        
        # 1. Q&Aデータから引用を抽出
        for qa_item in qa_results:
            citations = self.extract_citations_from_qa_data(qa_item)
            all_citations.extend(citations)
        
        # 2. PIP-Maker関連URLを追加
        suggested_citations = self.generate_pip_maker_related_urls(query, category)
        all_citations.extend(suggested_citations)
        
        # 3. 引用情報を検証・強化
        enhanced_citations = await self.enhance_citations_with_verification(all_citations)
        
        # 4. 表示用にフォーマット
        citation_display = self.format_citations_for_display(enhanced_citations, max_citations=5)
        
        return citation_display
    
    def get_citation_stats(self) -> Dict[str, Any]:
        """引用システムの統計情報を取得"""
        total_cached = len(self.url_cache)
        accessible_urls = len([url for url, (accessible, _) in self.url_cache.items() if accessible])
        
        return {
            "total_cached_urls": total_cached,
            "accessible_urls": accessible_urls,
            "cache_hit_rate": round(accessible_urls / max(total_cached, 1) * 100, 1),
            "cache_duration_hours": self.cache_duration.total_seconds() / 3600
        }