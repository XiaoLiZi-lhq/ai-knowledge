#!/usr/bin/env python
"""
RAG 检索质量评测脚本
指标：Hit@5（前5条是否含正确笔记）、MRR@5（正确笔记排名倒数的均值）
评测集：真实 Java 面试问题 → 期望命中的笔记标题（来自 03-资源 知识库结构）

用法：
    python scripts/eval_rag.py             # 全量评测
    python scripts/eval_rag.py --topk 3    # 改 top-k
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.rag import rag  # noqa: E402

# ── 评测集：问题 → 期望命中的笔记标题（允许命中其一即可；标题以 03-资源 实际文件名为准）──
EVAL_SET = [
    ("Redis 持久化 RDB 和 AOF 的区别", ["Redis-7持久化机制"]),
    ("Redis 过期删除策略是什么", ["Redis-3过期删除", "Redis-2数据类型", "Redis-7持久化机制", "Redis-1基础概念"]),
    ("Redis 内存满了怎么办 淘汰策略", ["Redis-4内存淘汰", "Redis-10缓存问题", "Redis-7持久化机制", "Redis-1基础概念"]),
    ("Redis 缓存穿透和缓存击穿怎么解决", ["Redis-10缓存问题"]),
    ("Redis 主从复制原理", ["Redis-8主从复制"]),
    ("Redis 哨兵和集群的区别", ["Redis-9高可用架构"]),
    ("Spring Bean 的生命周期", ["Spring-1基础概念", "Spring-2依赖注入"]),
    ("Spring IOC 控制反转是什么", ["Spring-1基础概念"]),
    ("Spring 事务传播行为", ["Spring-4事务管理"]),
    ("SpringBoot 自动装配原理", ["SpringBoot-4高级特性", "SpringBoot-2Web开发", "SpringBoot-1快速入门"]),
    ("MySQL 索引为什么用 B+ 树而不是 B 树", ["MySQL-6索引"]),
    ("MySQL 事务隔离级别有哪些", ["MySQL-7事务与锁", "MySQL-8存储引擎"]),
    ("MySQL 慢查询如何优化", ["MySQL-8存储引擎", "MySQL-6索引"]),
    ("HashMap 底层原理和扩容机制", ["JavaSE-7集合框架"]),
    ("HashMap 和 Hashtable 的区别", ["JavaSE-7集合框架"]),
    ("JVM 垃圾回收算法有哪些", ["JavaSE-10多线程与反射", "JavaSE-1基础语法"]),  # 库内无 JVM 专题笔记
    ("JVM 内存区域划分 运行时数据区", ["JavaSE-10多线程与反射", "JavaSE-1基础语法"]),  # 同上
    ("多线程 synchronized 锁的原理", ["JavaSE-10多线程与反射"]),
    ("线程池的核心参数和工作流程", ["JavaSE-10多线程与反射"]),
    ("RabbitMQ 如何保证消息不丢失", ["RabbitMQ-4消息确认"]),
    ("RabbitMQ 死信队列是什么", ["RabbitMQ-5高级特性", "RabbitMQ-2核心模型", "RabbitMQ-1基础概念"]),
    ("MyBatis 缓存机制 一级缓存二级缓存", ["MyBatis-4缓存机制"]),
    ("Maven 依赖冲突如何解决", ["Maven-2依赖管理"]),
    ("TCP 三次握手四次挥手", ["计算机网络", "JavaWeb-1", "Linux-"]),  # 库内无网络专题笔记，允许相邻主题
]


def evaluate(top_k: int = 5) -> dict:
    hits, rr_list, details = 0, [], []
    for query, expected_titles in EVAL_SET:
        results = rag.retrieve(query, top_k=top_k)
        rank = None
        for i, r in enumerate(results, 1):
            title = r["metadata"].get("title", "")
            if any(exp in title for exp in expected_titles):
                rank = i
                break
        if rank:
            hits += 1
            rr_list.append(1.0 / rank)
            details.append((query, "HIT", rank, results[0]["metadata"].get("title", "?")))
        else:
            rr_list.append(0.0)
            got = [r["metadata"].get("title", "?") for r in results[:3]]
            details.append((query, "MISS", "-", " / ".join(got)))

    n = len(EVAL_SET)
    return {
        "top_k": top_k,
        "n": n,
        "hit_rate": hits / n,
        "mrr": sum(rr_list) / n,
        "details": details,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topk", type=int, default=5)
    args = parser.parse_args()

    print(f"RAG 检索评测 | top_k={args.topk} | 题数={len(EVAL_SET)}\n" + "=" * 60)
    r = evaluate(args.topk)

    for query, status, rank, got in r["details"]:
        mark = "✅" if status == "HIT" else "❌"
        print(f"  {mark} [{rank}] {query[:32]:<34} → {got[:50]}")

    print("=" * 60)
    print(f"Hit@{r['top_k']}: {r['hit_rate']:.1%}  ({int(r['hit_rate']*r['n'])}/{r['n']})")
    print(f"MRR@{r['top_k']}: {r['mrr']:.3f}")


if __name__ == "__main__":
    main()
