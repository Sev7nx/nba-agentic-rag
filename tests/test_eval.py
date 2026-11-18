from app.models import ChatResponse, Source, TraceStep
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
    assert report.fact_hit_rate == 1.0


def test_report_markdown_contains_metrics(fake_service, tmp_path):
    report = evaluate([], fake_service)
    text = report.to_markdown()
    assert "retrieval_hit_rate" in text
    assert "citation_coverage" in text
    assert "fact_hit_rate" in text
    assert "p95_latency_ms" in text


def test_link_validity_counts_dead_sources():
    class DeadService:
        def answer(self, request):
            return ChatResponse(
                answer="answer [1]",
                sources=[
                    Source(
                        id=1,
                        title="t",
                        url="https://example.com",
                        site="x",
                        type="news",
                        link_status="dead",
                    )
                ],
                trace=[],
            )

    question = EvalQuestion(
        id="1",
        question="x",
        expected_source_types=["news"],
        needs_link=True,
    )
    report = evaluate([question], DeadService())
    assert report.link_validity == 0.0


def test_stage_breakdown_aggregates_trace():
    class TimedService:
        def answer(self, request):
            return ChatResponse(
                answer="answer [1]",
                sources=[
                    Source(
                        id=1,
                        title="t",
                        url="https://example.com",
                        site="x",
                        type="news",
                    )
                ],
                trace=[
                    TraceStep(name="analyze", detail="", duration_ms=100),
                    TraceStep(name="plan", detail="", duration_ms=200),
                    TraceStep(name="stats_query", detail="", duration_ms=50),
                    TraceStep(name="link_check", detail="", duration_ms=30),
                    TraceStep(name="synthesize", detail="", duration_ms=400),
                ],
            )

    question = EvalQuestion(
        id="1",
        question="x",
        expected_source_types=["news"],
        needs_link=True,
    )
    report = evaluate([question], TimedService())
    assert report.stage_avg_ms["analyze"] == 100
    assert report.stage_avg_ms["plan"] == 200
    assert report.stage_avg_ms["tools"] == 50
    assert report.stage_avg_ms["link_check"] == 30
    assert report.stage_avg_ms["synthesize"] == 400
    assert "Stage breakdown" in report.to_markdown()