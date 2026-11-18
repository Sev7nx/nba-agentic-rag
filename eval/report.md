# Evaluation Report

- total: 24
- retrieval_hit_rate: 1.000
- citation_coverage: 1.000
- fact_hit_rate: 1.000
- link_validity: 1.000
- p95_latency_ms: 18718.0
- avg_cost_cny: 0.0119

| id | question | sources | types | hit | fact | cited | latency_ms |
|---|---|---|---|---|---|---|---|
| news-1 | 勇士最近有什么交易传闻？ | 5 | news | yes | yes | yes | 18718.0 |
| news-2 | 湖人最近签下了谁？ | 6 | news | yes | yes | yes | 22393.2 |
| news-3 | 凯尔特人本赛季的战绩怎么样？ | 1 | stats | yes | yes | yes | 3920.6 |
| news-4 | 约基奇最近有伤病吗？ | 4 | news | yes | yes | yes | 8717.1 |
| news-5 | 独行侠最近的交易流言有哪些？ | 2 | news | yes | yes | yes | 10109.3 |
| history-1 | 库里哪场比赛最经典？ | 8 | doc,video | yes | yes | yes | 23419.6 |
| history-2 | 2016 年总决赛第七场发生了什么？ | 7 | doc,video | yes | yes | yes | 16876.9 |
| history-3 | 乔丹的最后一投是哪场比赛？ | 8 | doc,video | yes | yes | yes | 15684.8 |
| history-4 | 科比退役战得了多少分？ | 5 | doc | yes | yes | yes | 9446.5 |
| history-5 | 马刺上一次夺冠是哪一年？ | 5 | doc | yes | yes | yes | 10711.8 |
| compare-1 | 库里和魔术师约翰逊谁的历史地位更高？ | 6 | doc,stats | yes | yes | yes | 9320.6 |
| compare-2 | 约基奇和恩比德谁更强？ | 8 | doc,news,stats | yes | yes | yes | 15186.3 |
| compare-3 | 詹姆斯和乔丹的生涯荣誉对比。 | 4 | doc,stats | yes | yes | yes | 14074.6 |
| compare-4 | 东契奇和特雷杨谁更适合建队？ | 3 | doc,stats | yes | yes | yes | 9485.7 |
| video-1 | 找几个库里的三分集锦。 | 5 | video | yes | yes | yes | 11689.5 |
| video-2 | 约基奇本赛季的助攻集锦。 | 2 | stats,video | yes | yes | yes | 12453.3 |
| video-3 | 2016 年总决赛抢七的集锦。 | 8 | doc,video | yes | yes | yes | 17460.0 |
| rules-1 | NBA 三分线有多远？ | 5 | doc | yes | yes | yes | 12388.7 |
| rules-2 | 什么是罗斯条款？ | 5 | doc | yes | yes | yes | 9410.0 |
| rules-3 | 附加赛的规则是什么？ | 5 | doc | yes | yes | yes | 8973.6 |
| stats-1 | 库里 2026-27 赛季场均多少分？ | 1 | stats | yes | yes | yes | 5848.3 |
| stats-2 | 2026-27 赛季得分王是谁？ | 6 | news,stats | yes | yes | yes | 14347.7 |
| stats-3 | 勇士 2026-27 赛季战绩怎么样？ | 5 | news,stats | yes | yes | yes | 12069.4 |
| live-1 | 今天有什么比赛？ | 5 | live | yes | yes | yes | 7216.2 |

## Stage breakdown (ms)

| stage | avg | max |
|---|---:|---:|
| total | 12497 | 23420 |
| synthesize | 5241 | 10724 |
| analyze_plan | 3816 | 7488 |
| tools | 2454 | 15682 |
| link_check | 1074 | 3579 |
| analyze | 0 | 0 |
| plan | 0 | 0 |
| verify | 0 | 0 |
| refine | 0 | 0 |

| id | analyze_plan | analyze | plan | tools | link_check | synthesize | total |
|---|---:|---:|---:|---:|---:|---:|---:|
| news-1 | 2510 | 0 | 0 | 6101 | 1952 | 8143 | 18718 |
| news-2 | 1528 | 0 | 0 | 13025 | 2305 | 5527 | 22393 |
| news-3 | 2019 | 0 | 0 | 42 | 0 | 1855 | 3921 |
| news-4 | 1923 | 0 | 0 | 879 | 1660 | 4251 | 8717 |
| news-5 | 2666 | 0 | 0 | 4325 | 995 | 2119 | 10109 |
| history-1 | 2545 | 0 | 0 | 15682 | 1551 | 5318 | 23420 |
| history-2 | 5341 | 0 | 0 | 536 | 1037 | 10047 | 16877 |
| history-3 | 7488 | 0 | 0 | 1948 | 1566 | 4705 | 15685 |
| history-4 | 5967 | 0 | 0 | 47 | 1000 | 2441 | 9446 |
| history-5 | 3541 | 0 | 0 | 26 | 1448 | 5692 | 10712 |
| compare-1 | 4065 | 0 | 0 | 124 | 740 | 4447 | 9321 |
| compare-2 | 6018 | 0 | 0 | 648 | 1381 | 7264 | 15186 |
| compare-3 | 5026 | 0 | 0 | 48 | 621 | 8391 | 14075 |
| compare-4 | 3662 | 0 | 0 | 189 | 496 | 5231 | 9486 |
| video-1 | 3968 | 0 | 0 | 1071 | 890 | 5755 | 11690 |
| video-2 | 5161 | 0 | 0 | 855 | 607 | 5840 | 12453 |
| video-3 | 2091 | 0 | 0 | 3251 | 1417 | 10724 | 17460 |
| rules-1 | 5974 | 0 | 0 | 23 | 678 | 5709 | 12389 |
| rules-2 | 3358 | 0 | 0 | 27 | 536 | 5484 | 9410 |
| rules-3 | 3286 | 0 | 0 | 22 | 629 | 5031 | 8974 |
| stats-1 | 4041 | 0 | 0 | 4 | 0 | 1799 | 5848 |
| stats-2 | 3404 | 0 | 0 | 6049 | 677 | 4253 | 14348 |
| stats-3 | 2958 | 0 | 0 | 3116 | 3579 | 2443 | 12069 |
| live-1 | 3033 | 0 | 0 | 866 | 0 | 3312 | 7216 |