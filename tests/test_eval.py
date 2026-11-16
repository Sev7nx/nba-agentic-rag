from scripts.eval import EvalQuestion, evaluate


def test_retrieval_hit_rate_counts_expected_source(fake_service):
    question = EvalQuestion(
        id="1",
        question="勇士交易",
        expected_facts=["交易"],
        expected_source_types=["news"],
        needs_link=True,
    )
    report = evaluate([question], fake_service)
    assert report.retrieval_hit_rate == 1.0
    assert report.citation_coverage == 1.0


def test_report_markdown_contains_metrics(fake_service, tmp_path):
    report = evaluate([], fake_service)
    text = report.to_markdown()
    assert "retrieval_hit_rate" in text
    assert "citation_coverage" in text
    assert "p95_latency_ms" in text