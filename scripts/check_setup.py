import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]


def mark(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def main() -> int:
    problems: list[str] = []

    print(f"Python: {sys.version.split()[0]}")
    if sys.version_info < (3, 11):
        problems.append("Python 版本低于 3.11")

    env_path = ROOT / ".env"
    env_ok = env_path.exists()
    print(f"[{mark(env_ok)}] .env")
    if not env_ok:
        problems.append("缺少 .env，先执行 cp .env.example .env 并填入 key")

    llm_ok = bool(settings.llm_api_key) and settings.llm_api_key != "your-llm-api-key"
    tavily_ok = (
        bool(settings.tavily_api_key)
        and settings.tavily_api_key != "your-tavily-api-key"
    )
    print(f"[{mark(llm_ok)}] LLM_API_KEY")
    print(f"[{mark(tavily_ok)}] TAVILY_API_KEY")
    if not llm_ok:
        problems.append("LLM_API_KEY 为空")
    if not tavily_ok:
        problems.append("TAVILY_API_KEY 为空（新闻/视频搜索会返回空）")

    stats_path = ROOT / settings.stats_db_path
    stats_ok = stats_path.exists()
    print(f"[{mark(stats_ok)}] {settings.stats_db_path}")
    if stats_ok:
        try:
            with sqlite3.connect(stats_path) as conn:
                as_of = conn.execute(
                    "SELECT value FROM meta WHERE key = 'as_of'"
                ).fetchone()
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            print(f"       as_of: {as_of[0] if as_of else settings.stats_as_of}")
            print(f"       tables: {len(tables)}")
        except sqlite3.Error as exc:
            problems.append(f"stats.sqlite 打不开：{exc}")
    else:
        problems.append(
            "缺少 data/stats.sqlite；先下载 Kaggle 数据并运行 "
            "python scripts/build_stats_db.py"
        )

    docs_path = ROOT / settings.docs_path
    docs_ok = docs_path.exists()
    print(f"[{mark(docs_ok)}] {settings.docs_path}")
    if docs_ok:
        lines = sum(1 for line in docs_path.open(encoding="utf-8") if line.strip())
        print(f"       documents: {lines}")
    else:
        problems.append(
            "缺少 data/docs/documents.jsonl；先运行 python scripts/fetch_docs.py"
        )

    chroma_path = ROOT / settings.chroma_dir
    chroma_ok = chroma_path.exists() and (chroma_path / "chroma.sqlite3").exists()
    print(f"[{mark(chroma_ok)}] {settings.chroma_dir}")
    if not chroma_ok:
        problems.append(
            "缺少文档索引；先运行 python scripts/build_doc_index.py"
        )

    extra_path = ROOT / "data/extra/Player Per Game.csv"
    print(f"[{mark(extra_path.exists())}] data/extra（仅重建 stats 时需要）")
    print(f"[i] embedding model: {settings.embedding_model}")

    if problems:
        print("\n还需要处理：")
        for problem in problems:
            print(f"- {problem}")
        print("\n完整步骤见 README 的「快速开始」。")
        return 1

    print("\n环境检查通过，可以启动：")
    print("  uvicorn app.main:app --reload")
    print("  streamlit run app/ui/streamlit_app.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())