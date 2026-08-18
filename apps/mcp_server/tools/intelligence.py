import re
from collections import Counter
from typing import Any

from mcp.server import MCPServer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from apps.mcp_server.tools.articles import request

FRENCH_STOP = {
    "alors",
    "au",
    "aux",
    "avec",
    "ce",
    "ces",
    "dans",
    "de",
    "des",
    "du",
    "elle",
    "en",
    "et",
    "eux",
    "il",
    "je",
    "la",
    "le",
    "les",
    "leur",
    "lui",
    "ma",
    "mais",
    "me",
    "meme",
    "mes",
    "moi",
    "mon",
    "ne",
    "nos",
    "notre",
    "nous",
    "on",
    "ou",
    "par",
    "pas",
    "pour",
    "qu",
    "que",
    "qui",
    "sa",
    "se",
    "ses",
    "son",
    "sur",
    "ta",
    "te",
    "tes",
    "toi",
    "ton",
    "tu",
    "un",
    "une",
    "vos",
    "votre",
    "vous",
}
STOP = set(ENGLISH_STOP_WORDS) | FRENCH_STOP


def words(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9-]{1,}", text.lower())
        if token not in STOP
    ]


def keyword_scores(text: str, limit: int = 12) -> list[dict[str, Any]]:
    tokens = words(text)
    counts = Counter(tokens)
    total = max(len(tokens), 1)
    return [
        {"keyword": term, "score": round(count / total, 4), "count": count}
        for term, count in counts.most_common(limit)
    ]


def readability(text: str) -> dict[str, Any]:
    sentences = [item for item in re.split(r"[.!?]+", text) if item.strip()]
    tokens = re.findall(r"\b\w+\b", text)
    syllables = sum(
        max(1, len(re.findall(r"[aeiouyàâäéèêëîïôöùûü]+", word.lower()))) for word in tokens
    )
    sentence_count = max(len(sentences), 1)
    word_count = len(tokens)
    score = (
        206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllables / max(word_count, 1))
    )
    return {
        "word_count": word_count,
        "sentence_count": len(sentences),
        "average_sentence_words": round(word_count / sentence_count, 2),
        "estimated_syllables": syllables,
        "flesch_like_score": round(score, 2),
        "heuristic": "English Flesch-like estimate; raw metrics are authoritative for mixed-language text",
    }


def rank_corpus(
    query: str, articles: list[dict[str, Any]], limit: int = 10
) -> list[dict[str, Any]]:
    if not articles or not query.strip():
        return []
    documents = [query] + [
        f"{item.get('title', '')} {item.get('excerpt', '')} {item.get('content_markdown', '')}"
        for item in articles
    ]
    matrix = TfidfVectorizer(
        stop_words=list(STOP), ngram_range=(1, 2), max_features=5000
    ).fit_transform(documents)
    scores = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
    ranked = sorted(zip(articles, scores, strict=True), key=lambda pair: pair[1], reverse=True)
    return [
        {
            "article_id": item["id"],
            "title": item["title"],
            "slug": item["slug"],
            "status": item["status"],
            "score": round(float(score), 4),
        }
        for item, score in ranked[:limit]
        if score > 0
    ]


def shingles(text: str, size: int = 5) -> set[tuple[str, ...]]:
    tokens = words(text)
    return {tuple(tokens[index : index + size]) for index in range(max(0, len(tokens) - size + 1))}


async def corpus() -> list[dict[str, Any]]:
    result = await request("GET", "/articles", params={"limit": 100})
    items = result.get("items", [])
    return items if isinstance(items, list) else []


async def article(article_id: str) -> dict[str, Any]:
    return await request("GET", f"/articles/{article_id}")


def register(mcp: MCPServer) -> None:
    @mcp.tool(name="extract_keywords")
    async def extract_keywords(
        article_id: str | None = None, text: str | None = None, limit: int = 12
    ) -> dict[str, Any]:
        """Extract explainable local keyword frequencies."""
        source = text or (await article(article_id or ""))["content_markdown"]
        return {"engine": "local-frequency", "keywords": keyword_scores(str(source), limit)}

    @mcp.tool(name="calculate_readability")
    async def calculate_readability(
        article_id: str | None = None, text: str | None = None
    ) -> dict[str, Any]:
        """Calculate documented readability metrics locally."""
        source = text or (await article(article_id or ""))["content_markdown"]
        return readability(str(source))

    @mcp.tool(name="analyze_article_seo")
    async def analyze_article_seo(article_id: str) -> dict[str, Any]:
        """Run a deterministic SEO checklist."""
        item = await article(article_id)
        checks = {
            "title_length": 10 <= len(item["title"]) <= 80,
            "slug_quality": bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item["slug"])),
            "content_words": readability(item["content_markdown"])["word_count"] >= 150,
            "seo_title": not item.get("seo_title") or len(item["seo_title"]) <= 60,
            "seo_description": bool(
                item.get("seo_description") and 70 <= len(item["seo_description"]) <= 160
            ),
            "taxonomy": bool(item.get("tags") or item.get("categories")),
        }
        return {
            "article_id": article_id,
            "engine": "deterministic-rules",
            "score": round(100 * sum(checks.values()) / len(checks)),
            "checks": checks,
        }

    @mcp.tool(name="find_similar_articles")
    async def find_similar_articles(article_id: str, limit: int = 10) -> dict[str, Any]:
        """Rank other articles with local TF-IDF cosine similarity."""
        target = await article(article_id)
        items = [item for item in await corpus() if item["id"] != article_id]
        return {
            "engine": "tfidf",
            "items": rank_corpus(f"{target['title']} {target['content_markdown']}", items, limit),
        }

    @mcp.tool(name="detect_duplicate_content")
    async def detect_duplicate_content(
        article_id: str, cosine_threshold: float = 0.75, jaccard_threshold: float = 0.6
    ) -> dict[str, Any]:
        """Flag content overlap with cosine and five-word shingle Jaccard evidence."""
        target = await article(article_id)
        source_shingles = shingles(target["content_markdown"])
        similar = rank_corpus(
            target["content_markdown"],
            [item for item in await corpus() if item["id"] != article_id],
            10,
        )
        by_id = {item["id"]: item for item in await corpus()}
        matches = []
        for candidate in similar:
            other = shingles(by_id[candidate["article_id"]]["content_markdown"])
            union = source_shingles | other
            jaccard = len(source_shingles & other) / len(union) if union else 0.0
            matches.append(
                {
                    **candidate,
                    "jaccard": round(jaccard, 4),
                    "duplicate": candidate["score"] >= cosine_threshold
                    or jaccard >= jaccard_threshold,
                }
            )
        return {
            "engine": "tfidf+shingle-jaccard",
            "thresholds": {"cosine": cosine_threshold, "jaccard": jaccard_threshold},
            "items": matches,
        }

    @mcp.tool(name="recommend_internal_links")
    async def recommend_internal_links(article_id: str, limit: int = 5) -> dict[str, Any]:
        """Recommend related published articles, excluding self."""
        target = await article(article_id)
        published = [
            item
            for item in await corpus()
            if item["id"] != article_id and item["status"] == "published"
        ]
        items = rank_corpus(target["content_markdown"], published, limit)
        for item in items:
            item["anchor_hints"] = [
                entry["keyword"]
                for entry in keyword_scores(by_id_text(published, item["article_id"]), 3)
            ]
        return {"engine": "tfidf", "items": items}

    @mcp.tool(name="recommend_tags")
    async def recommend_tags(article_id: str, limit: int = 5) -> dict[str, Any]:
        """Recommend existing tags without creating them."""
        item = await article(article_id)
        tags = await request("GET", "/tags")
        terms = {
            entry["keyword"]
            for entry in keyword_scores(f"{item['title']} {item['content_markdown']}", 30)
        }
        suggestions = [
            {
                "id": tag["id"],
                "name": tag["name"],
                "score": round(
                    len(set(words(f"{tag['name']} {tag['description']}")) & terms)
                    / max(len(words(tag["name"])), 1),
                    3,
                ),
            }
            for tag in tags.get("items", [])
        ]
        return {
            "engine": "keyword-overlap",
            "items": sorted(suggestions, key=lambda row: row["score"], reverse=True)[:limit],
        }

    @mcp.tool(name="keyword_cannibalization_report")
    async def keyword_cannibalization_report(query: str) -> dict[str, Any]:
        """Find multiple pages competing for a local keyword cluster."""
        matches = rank_corpus(query, await corpus(), 20)
        strong = [item for item in matches if item["score"] >= 0.1]
        return {
            "engine": "tfidf",
            "query": query,
            "risk": "high" if len([i for i in strong if i["status"] == "published"]) > 1 else "low",
            "items": strong,
        }

    @mcp.tool(name="content_gap_report")
    async def content_gap_report() -> dict[str, Any]:
        """Report underrepresented corpus terms using frequency heuristics."""
        items = await corpus()
        counts = Counter(
            term
            for item in items
            for term in set(words(f"{item['title']} {item['content_markdown']}"))
        )
        gaps = [
            {"term": term, "article_count": count} for term, count in counts.items() if count == 1
        ]
        return {
            "engine": "keyword-frequency",
            "article_count": len(items),
            "underrepresented_terms": sorted(gaps, key=lambda row: str(row["term"]))[:30],
        }

    @mcp.tool(name="semantic_search_articles")
    async def semantic_search_articles(query: str, limit: int = 10) -> dict[str, Any]:
        """Search locally; result explicitly declares the TF-IDF engine."""
        return {"engine": "tfidf", "items": rank_corpus(query, await corpus(), limit)}


def by_id_text(items: list[dict[str, Any]], article_id: str) -> str:
    for item in items:
        if item["id"] == article_id:
            return f"{item['title']} {item['content_markdown']}"
    return ""
