# 项目状态（每次改动后更新）

这份文件是给「下一轮对话」用的：新会话不需要重新问一遍哪些做了、哪些没做。
规则：只写**可核对的事实**（谁在什么时候合入/部署），不写计划性形容词；未完成项带一句「卡在哪」。

## 一、已在生产运行

| 能力 | 状态 | 核对方式 |
| --- | --- | --- |
| 手环数据接入（Gadgetbridge 导出文件 → 后端） | 上线 | App 内「华为手环导入」导入后看板有数 |
| 健康看板读服务器近 30 天观测 | 上线 | `GET /api/v1/health-profile/wearable-dashboard` |
| 实时心率（BLE 心率广播，华为手环） | 上线 | 看板「实时心率」卡片，或对话里问「我现在的心率」 |
| 知识库检索（指南/共识，带页码） | 上线 | 回答里出现「（《书名》第 N 页）」 |
| 本地向量化侧车（bge-m3，与线上向量同空间） | 上线 | `antang-prod-local-embeddings-1` |
| 主动关怀（每日问候、跟进、Auditor 审核） | 上线 | 设置里「日常问候」开 |
| 注销账号 / 注册强制知情同意 | 上线 | — |
| 加密备份（gpg AES256）+ fail2ban | 上线 | 服务器 `systemctl status antang-backup.timer` |
| 低血糖恐惧四象限 → 主动联系频率（3/4/2/5/3 次每周） | 上线 | `psychosocial_assessments` 表 |
| 行为通道与信念图谱（`fear_behavior_logs`、`hypoglycemia_belief_events`、`log_fear_behavior` / `record_hypoglycemia_belief` 工具、`GET /health-profile/fear-summary`） | 上线 | 迁移 `n61e6a4f9d82`；对话时自动喂进提示词 |
| 发布链路（versionCode 单调、固定签名、latest.json、CI 出包） | 上线 | `curl https://<host>/download/latest.json` |

## 二、代码已合入分支，尚未部署到生产

（暂无。分支 `feat/live-heart-rate`，PR #9 仍未合并。）

## 三、未做（按优先级，含卡点）

1. **移动端「行为与信念」展示**：后端接口已有，App 里还没有入口。改动只在 `apps/mobile`，需重打 APK。
2. **认知重构话术**：卡在临床同事给可接受边界；现在图谱只「记」不「改」。
3. **分级暴露方案**：卡在需要医生定强度/时长/血糖下限。
4. **语音输入（方案 A：ASR 侧车 + `/transcribe`，不存音频）**：后端与移动端都没开始。需新增 `RECORD_AUDIO` 权限与新原生依赖 → 必须重打 APK。
5. **行为/信念未进入主动关怀**：对话里已注入（`render_behavior_context`），但主动关怀的 `context_payload` 还没有，主动消息目前不知道「这个人最近每晚查三次血糖」。
6. **红队回归**：上一轮 33/36（2026-10 中旬）。此后改过提示词（cite 字段、否定/转折判定、夜间安抚规则、主动关怀承诺规则、行为/信念上下文），**尚未重跑**，当前分数未知。
7. **App 内「检查更新」入口**：技术方案已定（读 `latest.json` 比 versionCode），未实现。
8. **SSH 换强密码并告知组里**：口令登录仍开放。
## 四、外部依赖（不在我们手里）

- HFS-II / CHFS / PHFS-II / HFS-98 量表授权（HFS-Global，个案审批）→ 到位后才换 `instrument`、才做年龄匹配分流。
- OhioT1DM DUA（机构邮箱申请，约一周）→ 到位后才做跨数据集验证的正式版本。
- 血糖预测：日期集已就位（DiaData/HUPA-UCM/T1D-UOM），方法结论已出（加模态无增益、AUROC 0.96 但每天 1 次误报只覆盖 15–29% 事件）。

## 五、工程约定（踩过坑后定下的）

- 新增任何工具必须同时在 `api/src/antang_api/chat.py` 登记活动阶段，否则整轮对话失败。
- 引用只走工具返回的成品字符串，不让模型自己拼 `[S1]`（会被 `validate_citations` 拒）。
- 结论必须标明证据强度：模拟患者红队是开发期回归，不是临床验证。
- APK 里的 JS 是打包进包体的（未启用 OTA），任何前端改动都要重打；后端改动部署即生效。
- 发布签名只有一把（`keys/antang-release.keystore`），丢了就无法给已安装用户更新。
