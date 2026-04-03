# RAG 调试报告

**日期**: {{DATE}}
**会话 ID**: {{SESSION_ID}}

---

## 1. 测试配置

| 项目 | 值 |
|------|-----|
| **LLM 模型** | {{MODEL_NAME}} |
| **Embedding 模型** | {{EMBEDDING_MODEL}} |
| **Notebook ID** | {{NOTEBOOK_ID}} |
| **测试问题** | {{QUESTION}} |
| **Sources 数量** | {{SOURCE_COUNT}} |

---

## 2. 性能指标

| 阶段 | 耗时 | 占比 | 备注 |
|------|------|------|------|
| **总耗时** | {{TOTAL_TIME}} | 100% | |
| ├─ Embedding 生成 | {{EMBEDDING_TIME}} | {{EMBEDDING_PCT}}% | |
| ├─ 向量搜索 | {{VECTOR_SEARCH_TIME}} | {{VECTOR_SEARCH_PCT}}% | 检索到 {{CHUNK_COUNT}} 个 chunks |
| ├─ Prompt 构建 | {{PROMPT_BUILD_TIME}} | {{PROMPT_BUILD_PCT}}% | |
| └─ LLM 调用 | {{LLM_TIME}} | {{LLM_PCT}}% | {{LLM_TOKEN_COUNT}} tokens |

---

## 3. 检索质量评估

| 指标 | 评分 | 说明 |
|------|------|------|
| **Chunks 相关性** | {{CHUNK_RELEVANCE}}/5 | {{CHUNK_RELEVANCE_NOTE}} |
| **检索数量充足性** | {{CHUNK_COUNT_ADEQUACY}}/5 | {{CHUNK_COUNT_ADEQUACY_NOTE}} |
| **检索覆盖率** | {{COVERAGE}}/5 | {{COVERAGE_NOTE}} |

**检索到的 Chunks**:
```
{{CHUNKS_LIST}}
```

---

## 4. 答案质量评估

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| **相关性** | {{ANSWER_RELEVANCE}} | {{ANSWER_RELEVANCE_NOTE}} |
| **准确性** | {{ANSWER_ACCURACY}} | {{ANSWER_ACCURACY_NOTE}} |
| **完整性** | {{ANSWER_COMPLETENESS}} | {{ANSWER_COMPLETENESS_NOTE}} |
| **简洁性** | {{ANSWER_CONCISENESS}} | {{ANSWER_CONCISENESS_NOTE}} |
| **综合评分** | {{ANSWER_OVERALL}}/5 | |

**生成的答案**:
```
{{ANSWER_TEXT}}
```

---

## 5. 引用准确性评估

| 指标 | 值 | 说明 |
|------|-----|------|
| **引用数量** | {{CITATION_COUNT}} | |
| **引用正确率** | {{CITATION_ACCURACY}}% | {{CITATION_ACCURACY_NOTE}} |
| **虚引/误引** | {{FALSE_CITATIONS}} | {{FALSE_CITATIONS_NOTE}} |

**引用详情**:
```
{{CITATION_DETAILS}}
```

---

## 6. 对比分析

| 对比项 | 当前配置 | 对比配置 | 差异 |
|--------|----------|----------|------|
| **模型** | {{MODEL_NAME}} | {{COMPARE_MODEL}} | - |
| **总耗时** | {{TOTAL_TIME}} | {{COMPARE_TOTAL_TIME}} | {{TIME_DIFF}} |
| **LLM 耗时** | {{LLM_TIME}} | {{COMPARE_LLM_TIME}} | {{LLM_TIME_DIFF}} |
| **答案质量** | {{ANSWER_OVERALL}}/5 | {{COMPARE_ANSWER_QUALITY}}/5 | {{QUALITY_DIFF}} |

---

## 7. 问题和观察

- **发现的问题**:
  - {{ISSUE_1}}
  - {{ISSUE_2}}
  - {{ISSUE_3}}

- **性能瓶颈**:
  - {{BOTTLENECK_1}}
  - {{BOTTLENECK_2}}

- **优化建议**:
  - {{SUGGESTION_1}}
  - {{SUGGESTION_2}}

---

## 8. 原始日志

```
{{RAW_LOGS}}
```

---

## 9. 下一步行动

- [ ] {{ACTION_1}}
- [ ] {{ACTION_2}}
- [ ] {{ACTION_3}}
