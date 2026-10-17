# 医学知识库

App 回答医学问题时，先用知识库检索指南原文，再依据检索到的片段作答，并把出处写成
「（《中国1型糖尿病诊治指南（2021版）》第 42 页）」。知识库是固定的文档集合，不含任何
用户数据，也不提供实时信息；实时信息仍然来自手环与用户对话。

## 数据流

```
PDF 指南/共识
  -> build_knowledge_chunks.py     离线，一次
  -> knowledge_chunks.jsonl        每行一个片段 + bge-m3 向量
  -> load_knowledge.py             在 api 容器里执行
  -> knowledge_documents / knowledge_chunks 两张表
  -> search_diabetes_knowledge     对话中按需检索
```

构建与灌库都不在请求路径上：构建脚本只在本地跑，灌库脚本只在更新语料时跑一次。

## 一、切分与向量化

`api/scripts/build_knowledge_chunks.py`：

- 用 PyMuPDF 逐页取文本，去掉纯页码行，按中文标点断句累积到约 900 字符；
- **剔除跨页页眉页脚**：同一文档里在 40% 以上的页面上逐字重复的行视为版式噪声。
  期刊排版的中文指南每页页首都有「中华糖尿病杂志2022 年11 月第14 卷第11 期」这类行，
  不去掉它们会把同刊的片段互相拉近；
- **记录印刷页码**：期刊 PDF 的第 19 页往往印着第 1161 页，读者只能按印刷页翻。构建时
  从页脚读页码，取「印刷页 − PDF 页」的中位数作为整本文档的偏移（`printed_offset`），
  偏移要能覆盖 80% 以上的页才采用；采用不了就只留 PDF 页，并在检索结果里标 `page_kind`；
- **分块不跨页**，所以每个片段都能标出准确页码；短于 220 字符的页向后合并；
- 片段按 `sha256(text)` 去重（同一本指南里的重复条款只留一份）；
- 向量由 `bge-m3` 生成，1024 维，片段在入库前做 L2 归一化。

```bash
py -3 api/scripts/build_knowledge_chunks.py \
    --source <PDF 目录> --out <输出目录> \
    --key-file <只放密钥的文件> --base-url <OpenAI 兼容端点>
```

`--dry` 只解析不向量化，用来核对页数与片段数。

## 二、灌库

`api/scripts/load_knowledge.py` 在 api 容器内执行，因为它要连数据库：

```bash
docker cp knowledge_chunks.jsonl antang-prod-api-1:/tmp/
docker cp api/scripts/load_knowledge.py antang-prod-api-1:/tmp/
docker exec -e PYTHONIOENCODING=utf-8 antang-prod-api-1 \
    .venv/bin/python /tmp/load_knowledge.py --path /tmp/knowledge_chunks.jsonl
```

灌库是**全量替换**：先删 `knowledge_documents`（片段靠外键级联删除），再按
`(folder, title)` 分组写入。输出 `done: documents=N chunks=M`。

## 三、检索

`api/src/antang_api/knowledge/search.py`：

- 启动时（`main.py` 的 lifespan 调 `warm_knowledge_index`）把全部向量读进内存，
  用表里的 `count` 与 `max(created_at)` 做指纹，语料变了才重建；
- 查询向量与片段向量都做过归一化，所以余弦相似度就是点积；
- 用 `argpartition` 取 top-k 后排序，**低于 `MIN_KNOWLEDGE_SCORE = 0.32` 的片段直接丢弃**，
  宁可回答「没找到指南依据」也不拿不相关的段落充数；
- **同语种优先**：语料里中文指南只占约一成、英文 ADA 占九成，中文提问时英文片段容易把
  中文指南挤出去。查询是中文时，汉字占比过半的片段在排序上加 `LANGUAGE_BONUS = 0.04`；
  这个权重小到不会把无关片段拉进来（原始余弦仍要过 `MIN_KNOWLEDGE_SCORE`），
  大到能分开分数贴近的两种语料。

选精确 KNN 而不是 pgvector 的原因：片段量级在万级、维度 1024，内存里算一次约 10 ms，
召回率高于任何近似索引，而且不用给生产库换镜像。接口留在 `search_knowledge()` 一处，
以后片段量涨到十万级再换成 pgvector 只需要改这个文件。

## 四、工具与出处

`api/src/antang_api/tools/knowledge.py` 注册 `search_diabetes_knowledge`，参数是
`query`（2–120 字）与 `top_k`（1–8，默认 5），返回
`{query, results: [{title, page, page_kind, pdf_page, text, score}]}`，
单条文本截断到 700 字符，整体不超过 6000 字符。

`page` 永远是**读者能翻到的那一页**：有印刷页码时给印刷页（`page_kind: "printed"`），
没有时退回文件页码（`page_kind: "pdf"`）；`pdf_page` 只用于排查，不写进回答。

**出处一律是「《标题》第 N 页」这样的文字，不使用 `[S1]` 编号。** `citations.py` 会把
任何不在本次 `web_fetch` 结果里的 `[Sn]` 判为不存在的来源并让整轮对话失败，所以知识库和
网页检索必须用两套互不冒充的出处格式——这一点写在 `agents/core.py` 的 `SYSTEM_PROMPT` 里。

## 五、新增工具的硬性要求

新工具必须在 `api/src/antang_api/chat.py` 的 `TOOL_ACTIVITY_PHASES` 里登记活动阶段，
否则调用时 `chat.py` 会抛 `工具缺少活动阶段配置：<工具名>`，整个对话直接失败。
`api/tests/test_chat_service.py::test_new_tools_reuse_stable_activity_phases` 覆盖这条约束。

## 六、当前语料

27 份文档、6086 个片段（其中 499 个带印刷页码），来源包括《中国1型糖尿病诊治指南（2021版）》
《中国糖尿病防治指南（2024版）》《ADA Standards of Care in Diabetes—2026》《成人1型糖尿病的
管理（ADA/EASD）（2022）》《中国胰岛素泵治疗指南（2021）》《持续葡萄糖监测基层临床应用专家
共识（2025年）》《动态葡萄糖图谱报告临床应用专家共识（2023版）》《1型糖尿病运动管理：共识
声明》等。

中文片段只占约一成，英文 ADA 占九成，这是「同语种优先」排序规则存在的原因。

八份小于 30 KB 的空壳 PDF、一本 198 MB 的整本书，以及三本扫描版（无文字层，PyMuPDF 取不到
文本）的中文书没有入库，跳过原因记录在构建产物的 `manifest.json` 里。
