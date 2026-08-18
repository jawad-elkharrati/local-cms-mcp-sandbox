from apps.mcp_server.tools.intelligence import keyword_scores, rank_corpus, readability, shingles


def test_keywords_and_readability_are_deterministic() -> None:
    text = "Docker makes local deployment repeatable. Docker supports safe local testing."
    assert keyword_scores(text, 2)[0]["keyword"] == "docker"
    metrics = readability(text)
    assert metrics["word_count"] == 10
    assert metrics["sentence_count"] == 2


def test_tfidf_ranks_related_document_first() -> None:
    corpus = [
        {
            "id": "docker",
            "title": "Docker ML deployment",
            "slug": "docker-ml",
            "status": "published",
            "excerpt": "",
            "content_markdown": "deploy machine learning models in docker containers",
        },
        {
            "id": "sql",
            "title": "SQL queries",
            "slug": "sql",
            "status": "published",
            "excerpt": "",
            "content_markdown": "window functions and relational queries",
        },
    ]
    result = rank_corpus("deploy a machine learning model with Docker", corpus)
    assert result[0]["article_id"] == "docker"
    assert result[0]["score"] > 0


def test_shingles_detect_exact_overlap() -> None:
    text = "alpha bravo charlie delta echo foxtrot golf"
    assert shingles(text) == shingles(text)
    assert len(shingles(text)) == 3
