# 低血糖恐惧的行为证据与信念图谱

量表（HFS-II 及其儿童版、家长版、伴侣版）测的是**外显**恐惧，题目受版权保护，且一年只能问一次两次。
这份文档记录另一条通道：**从对话里取行为与信念**，和外显分数放在同一个人身上对照。

两件事分别对应两个设计问题：

- 恐惧的人具体**做了什么**（额外测一次、夜里反复确认、因怕低血糖而加餐、运动回避、擅自减胰岛素）。
  行为是可数的事实，不需要量表授权，也不需要用户填表。
- 恐惧的人**相信什么**（“低血糖就会晕过去”“只要心慌就说明低了”“低血糖会伤脑子”）。
  信念决定行为，而灾难化信念正是认知重构的靶子。

## 一、数据模型

迁移 `n61e6a4f9d82`，两张表，都随账号注销 `ON DELETE CASCADE` 删除。

`fear_behavior_logs`

| 列 | 说明 |
| --- | --- |
| `kind` | 五选一：`extra_check` / `night_check` / `carb_loading` / `exercise_avoidance` / `insulin_hold` |
| `occurred_at` | 事情发生的时间（可空，默认取写入时刻） |
| `context` | 用户当时的原话，便于回看是谁在什么情境下说的 |
| `source_message_id` | 从哪条消息抽出来的，外键到 `messages`，删消息时置空 |

`hypoglycemia_belief_events`

| 列 | 说明 |
| --- | --- |
| `belief` | 十七选一，见 `models/behavior.py` 的 `HYPOGLYCEMIA_BELIEFS`（灾难化、失控感、躯体误读、回避、羞耻等几类） |
| `occurrence` | `stated`（用户自述）/ `endorsed`（助手提出后用户认可）/ `rejected`（用户否认） |
| `evidence` | 用户原话 |

`belief` 用固定枚举而不是自由文本：认知重构需要知道“针对哪一条信念”，自由文本无法统计同一条信念被反复触发的次数。
枚举本身就是我们关于“1 型糖尿病患者对低血糖有哪些典型信念”的假设，改枚举要重新过一遍临床同事。

## 二、阈值与判定

都在 `behavioral/service.py` 顶部，改一处即可：

- `AVOIDANCE_WEEKLY_THRESHOLD = 2.0`：近 7 天“回避型”行为（运动回避 + 擅自减胰岛素）达到 2 次，标记为需要主动联系。
- `AVOIDANCE_KINDS` / `MONITORING_KINDS`：把行为分成“回避”和“过度监测”两类。
  这两个方向的临床含义相反，不能合并成一个“恐惧分数”。
- 外显与内隐的对照规则：量表 `fear_behavior_percent` 或 `fear_worry_percent` 有一项 ≥ `FEAR_HIGH_PERCENT`（50）算外显高；
  近 7 天回避行为 ≥ 2 次算内隐高。两者不一致的两种情形（量表低但行为高、量表高但行为低）才是我们要在对话里追问的。

`GET /api/v1/health-profile/fear-summary` 返回：两张表的近 30 天明细、按 `belief` 聚合的信念节点（含次数与最近一次时间）、
7 天与 30 天的行为计数、以及上面那个“外显高 / 内隐高”的布尔值。移动端不显示分数，只显示“最近有没有因为这些事反复确认”。

## 三、对话侧的取数方式

两个工具（`tools/behavior.py`），都只在用户真的说起这些事时调用，不做推断：

- `record_fear_behavior`：用户说到“又测了一次”“晚上不放心”“因为怕低血糖没去跑步”“自己把胰岛素减了”时记录。
- `record_hypoglycemia_belief`：用户表达对低血糖的信念时记录，必须带上用户原话片段作为 `evidence`。

两条硬规则写在工具描述里：

1. **不记录推测**。用户没说“我多测了一次”，就不能因为对话里出现心慌而记一条 `extra_check`。
2. **不自作主张下结论**。工具只写事实，不写“用户有低血糖恐惧症”这类判断；诊断不是这个系统的输出。

提示词里另有约定：助手不得在回复里展示这些计数或“你的恐惧指数”，避免把行为监测变成新的焦虑源。
这正是我们批评硅基动感悬浮球的地方——把“反复检查”做成产品入口会强化检查行为。

## 四、为什么现在只做到这一步

- **没做量表替换**：`instrument` 仍是 `antang-behavior-v1`，等 HFS 授权到位再换。行为通道与量表通道独立，换量表不影响这两张表。
- **没做认知重构的自动化**：信念图谱目前只“记”，不“改”。改写要等临床同事给出可接受的话术边界，交给模型自由发挥风险太高。
- **没做分级暴露**：运动回避的暴露方案需要医生参与制定（强度、时长、血糖下限），不是工程侧能定的。

## 五、验证

```bash
bash api/scripts/test          # 全量后端测试
```

`api/tests/test_fear_behavior.py` 覆盖：五类行为的记录与回读、信念枚举越界拒绝、`occurrence` 只接受三个值、
近 30 天过滤、按信念聚合的计数与最近时间、7 天回避阈值边界（1 次不算、2 次算）、外显与内隐四种组合、
`fear-summary` 接口的往返、以及没有记录时返回空而报错。

## 六、患者自己撤回

这两张表记的东西（夜里起来查了几次血糖、说过“低血糖就是会死”）比血糖读数更敏感，所以患者要能自己删掉，
而不是只能注销账号连带清空。

- `DELETE /api/v1/health-profile/fear-behavior/{log_id}` → `204`
- `DELETE /api/v1/health-profile/belief-events/{event_id}` → `204`

两个接口都在 `behavioral/service.py`（`delete_behavior_log` / `delete_belief_event`），按 `user_id` 限定，
记录不存在或不属于该用户都返回 `404`，不区分“没有”和“不是你的”。

**为什么是硬删除**：血糖读数用 `revoked_at` 软撤回，因为复盘、趋势图要能解释“这条当时不在”。
行为与信念没有这层时间线语义——一条被撤回的“额外检查 6 次”对任何下游都没有价值，留着只是风险。
AGENTS.md 也要求删干净。代价是删了不可恢复，所以移动端删之前必须再确认一次。

### 列表接口（2026-10-21 新增）

只有 `DELETE /{id}` 删不了：汇总卡片给的是次数，患者看不到“是哪一条”。所以配了两个列表接口，
带 `id`、中文说法和时间：

- `GET /api/v1/health-profile/fear-behavior?days=28` → `[{id, kind, label, count, note, occurred_at}]`
- `GET /api/v1/health-profile/belief-events?days=90` → `[{id, belief_code, label, quote, occurrence, detected_at}]`

两个列表都按时间倒序（患者翻它是为了找刚刚那一条）。`label` 由服务端给：行为用
`behavioral/service.py` 的 `BEHAVIOR_KIND_LABELS`，信念用 `_BELIEF_LABELS`——客户端不再各写一套词表，
否则同一条记录在两个界面会叫两个名字。

### App 侧（`apps/mobile/src/fear/FearBehaviorSection.tsx`）

卡片下半部分「可以删掉的记录」逐条列出行为与信念，每条一个「删除」；点完变成「删掉这条？」+
`删掉` / `取消` 两个按钮，确认后才发 `DELETE`，成功即从列表移除，并重新拉一次
`GET /fear-summary` 让上面的次数跟着变（否则刚删掉的那几条还挂在“6 次”里）。
删除失败时保留原记录并在卡片里说明原因，不做静默当成功。

```bash
bash api/scripts/test          # 含 tests/test_health_profile_routes.py 的撤回用例
```
