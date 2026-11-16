# NBA 语料目录

把首批语料放在这里，然后运行：

```bash
python scripts/ingest_corpus.py
```

## Markdown

每个 `.md` 文件是一篇文档，第一行作为标题。适合规则、术语、比赛回顾等长文本。

## JSON

一个 `.json` 文件可以是一个对象或对象数组：

```json
{
  "doc_id": "curry-career",
  "title": "斯蒂芬·库里生涯概览",
  "url": "https://example.com/curry",
  "text": "正文……",
  "source_type": "doc",
  "entity_type": "player",
  "entity_name": "库里",
  "date": "2026-01-01"
}
```

首批建议：30 篇（10 位球员 + 10 支球队 + 10 篇经典比赛/规则）。
只保存标题、短摘要和原链接，不转载全文。