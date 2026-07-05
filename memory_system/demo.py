#!/usr/bin/env python3
"""
Memory System 独立演示

模拟完整的 LLM 跨会话记忆流程:
  1. 第一轮 LLM 交互 -> remember() 提取记忆
  2. 第二轮 LLM 交互前 -> recall() 检索 + inject_memories() 注入
  3. 展示完整的"记忆 -> 检索 -> 注入"闭环

运行:
    cd memory_system
    python demo.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# 确保可以从 memory_system 目录导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory_system import MemoryManager, MemoryType


# ---------------------------------------------------------------------------
# 模拟 LLM 提取函数 (实际集成时替换为真正的 LLM 调用)
# ---------------------------------------------------------------------------

async def mock_extract_fn(prompt: str) -> str:
    """模拟: 从 LLM 交互中提取结构化记忆 (实际使用时替换为 chat() 调用)."""
    # 简单规则模拟 —— 实际中这里调用 LLM API
    if "优化类图" in prompt and "提高可扩展性" in prompt:
        return json.dumps([
            {
                "memory_type": "preference",
                "content": "用户偏好使用组合模式而非继承来扩展系统功能",
                "tags": ["设计模式", "组合优于继承", "类图"],
                "importance": 0.8,
            },
            {
                "memory_type": "decision",
                "content": "BlogService 采用策略模式处理不同的支付方式",
                "tags": ["策略模式", "支付", "架构"],
                "importance": 0.9,
            },
            {
                "memory_type": "insight",
                "content": "该项目的领域模型倾向于贫血模型(Anemic Model), Service 层放业务逻辑",
                "tags": ["贫血模型", "领域驱动", "架构风格"],
                "importance": 0.6,
            },
        ])
    elif "时序图" in prompt and "添加认证流程" in prompt:
        return json.dumps([
            {
                "memory_type": "decision",
                "content": "认证流程使用 JWT Token + Refresh Token 双令牌机制",
                "tags": ["JWT", "认证", "时序图", "安全"],
                "importance": 0.9,
            },
            {
                "memory_type": "rejection",
                "content": "不要使用 Session 认证, 用户在第 2 轮优化时拒绝了该方案",
                "tags": ["Session", "认证", "已拒绝"],
                "importance": 0.85,
            },
        ])
    elif "全局优化" in prompt and "一致性" in prompt:
        return json.dumps([
            {
                "memory_type": "convention",
                "content": "项目统一使用 MVC 三层架构, Controller 不直接访问 DAO",
                "tags": ["MVC", "架构规范", "分层"],
                "importance": 0.75,
            },
            {
                "memory_type": "preference",
                "content": "命名规范遵循 Python PEP 8, 类名大驼峰, 方法名蛇形",
                "tags": ["命名规范", "PEP8", "Python"],
                "importance": 0.5,
            },
        ])
    else:
        return json.dumps([
            {
                "memory_type": "insight",
                "content": f"LLM 优化了 UML 设计, 改动集中在类关系调整",
                "tags": ["优化", "类关系"],
                "importance": 0.4,
            }
        ])


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("  Memory System Demo — 基于 BM25 的跨会话记忆")
    print("=" * 70)
    print()

    # 初始化
    storage_dir = os.path.join(os.path.dirname(__file__), "demo_output", "memories")
    manager = MemoryManager(storage_dir=storage_dir, max_entries=20)
    project = "blog_system"

    print(f"[Storage] {storage_dir}")
    print(f"[Project] {project}")
    print()

    # ==================================================================
    # 会话 1: 优化类图
    # ==================================================================
    print("─" * 70)
    print("  Session 1: 用户请求优化类图设计")
    print("─" * 70)

    # 1a. 用户发起优化
    user_query_1 = "请优化 Blog 系统的类图设计，提高可扩展性"
    print(f"\n[User] {user_query_1}")

    # 1b. 模拟 LLM 优化 (这里省略实际 LLM 调用)
    llm_response_1 = """
    已优化类图:
    - 将 BlogService 拆分为 BlogWriteService 和 BlogReadService (CQRS)
    - 引入 PostRepository 接口 (依赖倒置)
    - 使用组合模式替代继承链
    """

    print(f"[LLM] 优化完成, 变更了 3 个类")

    # 1c. 用户反馈
    user_feedback_1 = "accepted"

    # 1d. 提取并存储记忆
    print("\n[Extract] 提取记忆...")
    entries_1 = await manager.remember(
        project_id=project,
        context="用户请求优化 Blog 系统类图, 提高可扩展性",
        llm_call_type="optimize",
        user_input=user_query_1,
        llm_output=llm_response_1,
        user_feedback=user_feedback_1,
        extract_fn=mock_extract_fn,
    )

    for e in entries_1:
        print(f"   [+] [{e.memory_type.value}] {e.content[:60]}...")
    print(f"   -> 共提取 {len(entries_1)} 条记忆")
    print()

    # ==================================================================
    # 会话 2: 优化时序图
    # ==================================================================
    print("─" * 70)
    print("  Session 2: 用户请求优化时序图 (认证流程)")
    print("─" * 70)

    user_query_2 = "请优化用户登录的时序图，添加 JWT 认证流程"
    print(f"\n User: {user_query_2}")

    # 2a. 检索相关记忆
    print("\n[Search] 检索相关记忆...")
    results = await manager.recall(
        project_id=project,
        query=user_query_2,
        top_k=5,
        max_tokens=800,
    )

    for i, rr in enumerate(results, 1):
        print(
            f"   {i}. [{rr.entry.memory_type.value}] {rr.entry.content[:60]}... "
            f"(score: {rr.score:.4f})"
        )

    # 2b. 注入 system prompt
    system_prompt = (
        "你是一个 UML 设计专家, 擅长时序图分析和优化。"
        "请根据用户需求生成优化的时序图 JSON。"
    )
    enriched_prompt = manager.inject_memories(system_prompt, results)

    print(f"\n[Note] 注入记忆后的 System Prompt:")
    print(f"   {enriched_prompt[:200]}...")
    print(f"   -> 原始长度: {len(system_prompt)} chars, 注入后: {len(enriched_prompt)} chars")

    # 2c. 模拟 LLM 调用 (省略)
    llm_response_2 = """
    已优化时序图:
    - 添加了 Access Token + Refresh Token 流程
    - 增加了 Token 刷新生命线
    """
    print(f"\n[LLM] LLM: 时序图优化完成 (基于注入的记忆, 避开了 Session 方案)")

    # 2d. 提取新记忆
    print("\n[Extract] 提取记忆...")
    entries_2 = await manager.remember(
        project_id=project,
        context="用户请求优化登录时序图, 添加 JWT 认证流程",
        llm_call_type="optimize",
        user_input=user_query_2,
        llm_output=llm_response_2,
        user_feedback="accepted",
        extract_fn=mock_extract_fn,
    )

    for e in entries_2:
        print(f"   [+] [{e.memory_type.value}] {e.content[:60]}...")
    print(f"   -> 共提取 {len(entries_2)} 条记忆")
    print()

    # ==================================================================
    # 会话 3: 跨图全局优化
    # ==================================================================
    print("─" * 70)
    print("  Session 3: 用户请求全局优化 (跨图一致性校验)")
    print("─" * 70)

    user_query_3 = "请对类图+时序图+组件图进行全局优化，确保三者一致"
    print(f"\n User: {user_query_3}")

    # 3a. 检索
    print("\n[Search] 检索相关记忆...")
    results_3 = await manager.recall(
        project_id=project,
        query=user_query_3,
        top_k=5,
    )

    for i, rr in enumerate(results_3, 1):
        print(
            f"   {i}. [{rr.entry.memory_type.value}] {rr.entry.content[:60]}... "
            f"(score: {rr.score:.4f})"
        )
    print(f"   -> 共检索到 {len(results_3)} 条相关记忆")

    # 3b. 注入
    enriched_3 = manager.inject_memories(
        "你是 UML 全局优化专家，请对多张图进行交叉验证和协同优化。",
        results_3,
    )
    print(f"\n[Note] 完整的 System Prompt 末尾:")
    # 只显示记忆部分
    memory_section = enriched_3[len("你是 UML 全局优化专家，请对多张图进行交叉验证和协同优化。"):]
    print(memory_section)
    print()

    # ==================================================================
    # 查看记忆库状态
    # ==================================================================
    print("─" * 70)
    print("  Memory Store 状态")
    print("─" * 70)

    stats = await manager.stats(project)
    print(f"\n[Stats] 项目 '{project}' 记忆统计:")
    print(f"   总记忆数: {stats['total_memories']}")
    print(f"   按类型分布: {json.dumps(stats['by_type'], ensure_ascii=False)}")
    print(f"   已索引文档: {stats['indexed_docs']}")
    print(f"   词汇表大小: {stats['index_vocab']}")

    # 列出所有记忆
    all_memories = await manager.list_memories(project)
    print(f"\n[Note] 所有记忆 (按时间降序):")
    for i, e in enumerate(all_memories, 1):
        print(f"   {i}. [{e.memory_type.value}] {e.content}")
        print(f"      tags: {e.tags} | importance: {e.importance:.2f} | age: {e.age_days:.1f}d")
        print(f"      id: {e.id}")

    # ==================================================================
    # 测试 forget
    # ==================================================================
    print()
    print("─" * 70)
    print("  测试 forget: 删除一条记忆")
    print("─" * 70)

    if all_memories:
        target = all_memories[0]
        print(f"\n[Delete]  删除: [{target.memory_type.value}] {target.content[:40]}...")
        ok = await manager.forget(project, target.id)
        print(f"   {'[OK] 删除成功' if ok else '[FAIL] 删除失败'}")

        stats_after = await manager.stats(project)
        print(f"   删除后总记忆数: {stats_after['total_memories']}")

    # ==================================================================
    # Done
    # ==================================================================
    print()
    print("=" * 70)
    print("  [OK] Demo 完成!")
    print(f"  [Folder] 记忆文件保存在: {os.path.abspath(storage_dir)}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
