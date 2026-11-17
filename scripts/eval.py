import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import ChatRequest


@dataclass
class EvalQuestion:
    id: str
    question: str
    expected_facts: list[str] = field(default_factory=list)
    expected_source_types: list[str] = field(default_factory=list)
    needs_link: bool = False


@dataclass
class EvalReport:
    total: int = 0
    retrieval_hit_rate: float = 0.0
    citation_coverage: float = 0.0
    fact_hit_rate: float = 0.0
    link_validity: float = 0.0
    p95_latency_ms: float = 0.0
    avg_cost_cny: float = 0.0
    rows: list[dict] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            "# Evaluation Report",
            "",
            f"- total: {self.total}",
            f"- retrieval_hit_rate: {self.retrieval_hit_rate:.3f}",
            f"- citation_coverage: {self.citation_coverage:.3f}",
            f"- fact_hit_rate: {self.fact_hit_rate:.3f}",
            f"- link_validity: {self.link_validity:.3f}",
            f"- p95_latency_ms: {self.p95_latency_ms:.1f}",
            f"- avg_cost_cny: {self.avg_cost_cny:.4f}",
            "",
            "| id | question | sources | types | hit | fact | cited | latency_ms |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in self.rows:
            lines.append(
                f"| {row['id']} | {row['question']} | {row['sources']} | "
                f"{row['types']} | {row['hit']} | {row['fact']} | "
                f"{row['cited']} | {row['latency_ms']:.1f} |"
            )
        return "\n".join(lines)


def _hit(question: EvalQuestion, response) -> bool:
    if not question.expected_source_types:
        return True
    return any(source.type in question.expected_source_types for source in response.sources)


def evaluate(questions: list[EvalQuestion], chat_service) -> EvalReport:
    if not questions:
        return EvalReport()

    hits = 0
    citations = 0
    facts_hit = 0
    valid_links = 0
    total_links = 0
    latencies: list[float] = []
    costs: list[float] = []
    rows: list[dict] = []

    for question in questions:
        start = time.perf_counter()
        response = chat_service.answer(ChatRequest(question=question.question))
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)
        hit = _hit(question, response)
        hits += 1 if hit else 0
        cited = bool(re.search(r"\[\d+\]", response.answer)) and bool(response.sources)
        citations += 1 if cited else 0
        text = response.answer + " " + " ".join(
            source.snippet or "" for source in response.sources
        )
        fact = not question.expected_facts or all(
            expected in text for expected in question.expected_facts
        )
        if fact:
            facts_hit += 1
        if question.needs_link and not response.sources:
            total_links += 1
        for source in response.sources:
            total_links += 1
            if source.link_status != "dead":
                valid_links += 1
        costs.extend(step.cost_cny for step in response.trace)
        rows.append(
            {
                "id": question.id,
                "question": question.question,
                "sources": len(response.sources),
                "types": ",".join(
                    sorted({source.type for source in response.sources})
                )
                or "-",
                "hit": "yes" if hit else "no",
                "fact": "yes" if fact else "no",
                "cited": "yes" if cited else "no",
                "latency_ms": latency_ms,
            }
        )

    sorted_latencies = sorted(latencies)
    p95_index = max(0, int(len(sorted_latencies) * 0.95) - 1)
    return EvalReport(
        total=len(questions),
        retrieval_hit_rate=hits / len(questions),
        citation_coverage=citations / len(questions),
        fact_hit_rate=facts_hit / len(questions),
        link_validity=(valid_links / total_links) if total_links else 1.0,
        p95_latency_ms=sorted_latencies[p95_index],
        avg_cost_cny=(sum(costs) / len(questions)) if costs else 0.0,
        rows=rows,
    )


def load_questions(path: Path) -> list[EvalQuestion]:
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            questions.append(EvalQuestion(**json.loads(line)))
    return questions


class _FakeService:
    def answer(self, request: ChatRequest):
        from app.models import ChatResponse, Source

        return ChatResponse(
            answer=f"示例答案（{request.question}）[1]",
            sources=[
                Source(
                    id=1,
                    title="示例来源",
                    url="https://example.com",
                    site="example",
                    type="news",
                )
            ],
            trace=[],
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--fake", action="store_true")
    args = parser.parse_args()

    questions = load_questions(Path("eval/questions.jsonl"))
    if args.limit:
        questions = questions[: args.limit]

    if args.fake:
        service = _FakeService()
    else:
        from app.main import build_default_service

        service = build_default_service(use_cache=False)

    report = evaluate(questions, service)
    Path("eval").mkdir(exist_ok=True)
    Path("eval/report.md").write_text(report.to_markdown(), encoding="utf-8")
    print(report.to_markdown())


if __name__ == "__main__":
    main()