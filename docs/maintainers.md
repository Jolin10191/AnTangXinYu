# 协作环境维护说明

## 代码、检查与安装包

| 项目 | 入口 |
| --- | --- |
| 代码与 PR | [GitHub AnTangXinYu](https://github.com/Qzwolf/AnTang)，默认分支 `master` |
| 自动检查 | `.github/workflows/check.yml`：手机端检查和后端检查 |
| App 云构建 | [Expo 构建页](https://expo.dev/accounts/wocky528/projects/antang/builds) |
| 正式服务器 API | `https://82.157.48.200:8000` |
| 服务器项目 | `/home/ubuntu/antang-prod`，Compose 项目名 `antang-prod` |

GitHub 检查在 PR 和 `master` 推送时运行。手机任务安装锁定的 npm 依赖，执行类型检查、Lint、测试和 Android JS 打包。后端任务使用独立 PostgreSQL 服务，执行 Ruff、Pyright、迁移和测试。测试入口创建并删除临时数据库，不连接业务库；CI 不配置模型、Expo 和部署密钥。

合并前核对当前提交的检查结果、代码评审和需要的真机结果。检查运行成功只证明自动检查覆盖的行为；Health Connect 权限、同步、原生模块及通知仍须在安装包上验收。

## 构建 Android 安装包

Expo 项目是 `@wocky528/antang`。开发包通过 Metro 读取本机代码和后端地址；审核预览包固定本次选择的本机局域网或 HTTPS 隧道地址；正式发布才使用线上环境。具体启动步骤见 [本地开发与审核](local-development.md)。

提交手机端代码后，在项目根目录运行以下其中一条：

```bash
bash scripts/build-android development
bash scripts/build-android preview
# 校园网：先启动 bash scripts/dev-tunnel，再运行
bash scripts/build-android preview tunnel
```

出包脚本提交云构建并附上 Git 提交编号。只有 Expo 页面显示 `FINISHED`、核对地址与 Android 签名后，才分发安装链接。开发包连接 Metro；预览 APK 独立运行。团队成员使用自己的 Expo 项目权限，不共享登录凭据。`EXPO_PUBLIC_API_URL` 不是密钥。

## 模型配置

对话与主动关怀是两条独立的链，可以各配一个模型（方案 B：对话求快，主动关怀求稳）。

| 环境变量 | 用途 | 当前取值（2026-10-21 决定） |
| --- | --- | --- |
| `HACHIMI_MODEL_NAME` | Core Agent 对话，用户看得见的流式回复 | `gemini-3.8-flash-low`（红队 12/12，端到端 p50 11.0 s，会发 `tool_calls`） |
| `HACHIMI_PROACTIVE_MODEL_NAME` | 主动关怀 worker 的起草与 Auditor 审核 | `gemini-3.8-flash`（红队 33/36，TTFT 8.6 s，只影响 worker） |
| `HACHIMI_AUDIO_MODEL_NAME` | 语音输入的听感（快慢/轻重/呼吸），一次请求同时拿转写 | 留空（只转写）；配 `gemini-3.8-flash` 才有听感 |
| `HACHIMI_TRANSCRIBE_MODEL_NAME` | 语音输入转写（`POST /api/v1/voice/transcribe`） | `whisper-1`（默认；换模型不影响对话） |

`HACHIMI_AUDIO_MODEL_NAME` 留空时不产生声音状态；生产环境的中转站没有 whisper 模型，不配它时 `/api/v1/voice/transcribe` 会稳定 502（`/audio/transcriptions` 返回 `503 model_not_found`，实测记录见 `docs/voice-input.md`）。

`HACHIMI_PROACTIVE_MODEL_NAME` 留空或填空白时回退到 `HACHIMI_MODEL_NAME`，所以不配也能跑。改完要重建 `api` 与 `proactive-care-worker` 两个容器（`hindsight` 走自己的 key，不用动）。

**为什么对话不用 `deepseek-chat`**：这台中转站上的 `deepseek-chat` 收到 `tools` 也返回 `tool_calls: null`（直连网关实测，同一次探测里 `gemini-3.8-flash`、`-low`、`-high`、`gemini-2.5-flash`、`deepseek-v4-flash` 都会正常发），知识库检索工具从不被调用，回答里的页码只能靠模型编。`-low` 与 `-high` 是同一族的中转站别名（实测 2.5 s / 3.0 s 都会发 `tool_calls`，正牌 `gemini-3.8-flash` 18.9 s），差别体现在推理预算而不是能否用工具；质量差异只能靠红队测，当前 `-low` 是 12/12。

两条注意事项：

- **换对话模型之后旧红队分数作废**，必须重跑 `api/evals/simulated_patient/` 的 36 轮再引用通过率。
- 主动关怀延迟要单独看 worker 日志：`processor.py` 有重试上限，模型太慢会触发重试。

### Hindsight 召回的重排（最容易被误当成「模型慢」）

`compose.yaml` 里 `HINDSIGHT_API_RERANKER_LOCAL_MODEL` 是 `BAAI/bge-reranker-v2-m3`（5.68 亿参数的 cross-encoder）。在 4 核机器上给 60 个候选逐对打分要 **67 秒**，而这段时间发生在模型开始生成之前——患者看到的就是「回复好慢」。所以 `HINDSIGHT_API_RERANKER_MAX_CANDIDATES` 设成 `10`（默认 300），召回实测 37.6 s / 39.0 s → 8.7 s / 6.4 s。

改动落在 `compose.yaml`，生效要重建 hindsight（模型要重新加载，约 40 秒）：

```bash
docker compose -p antang-prod -f compose.yaml -f compose.server.yaml \
  up -d --no-deps --force-recreate hindsight
```

代码侧还有一层兜底：`hindsight_recall_timeout_seconds`（默认 8 s）与 `hindsight_retain_timeout_seconds`（默认 25 s）。超时只记 `companion_memory_recall_timeout` / `companion_memory_retain_timeout` 警告，召回超时当本轮没有记忆，写入超时不动游标（下一段重补）。


## 更新服务器

角色及患者授权的账号维护和演示步骤见 [患者授权说明](patient-access.md)。当前统一迁移为 `r75cae7f1d94`；开发和审核先升级本机，审核通过后再更新线上。普通注册固定患者，医护申请由研发管理审批，研发身份仍通过维护命令赋予。

服务器生产目录跟踪 GitHub `master`。Nginx 在公网 `8000` 端口提供 HTTPS，API 容器映射到服务器本机 `8001`。发布前确认目标提交通过检查，备份主数据库和 Hindsight 数据库，并检查是否有数据库迁移。

```bash
ssh ubuntu@82.157.48.200
cd /home/ubuntu/antang-prod
git remote -v
git status --short
git pull --ff-only origin master
docker compose -p antang-prod -f compose.yaml -f compose.server.yaml build api
docker compose -p antang-prod -f compose.yaml -f compose.server.yaml up -d --no-build --wait api proactive-care-worker
curl --fail https://82.157.48.200:8000/health
```

发布后核对容器状态、数据库迁移和主要 API 请求。服务端代码从 GitHub 拉取并在服务器构建；App APK 由 Expo 构建，手机安装新包后才能使用新的 Health Connect 历史权限和本地导入功能。旧包内的 API 地址也不会自动改变。

服务器上的旧试验目录如确认没有运行的服务、进程和需要保留的未迁移文件，可以单独清理。不要因为目录已经停用就删除其数据库卷；保留备份，清理范围只限已确认的旧目录。

证书由 `antang-certbot.timer` 定期续期。查看状态：

```bash
systemctl list-timers antang-certbot.timer
```

## 官方参考

- [GitHub Actions 工作流](https://docs.github.com/en/actions/writing-workflows)
- [Expo 构建](https://docs.expo.dev/build/introduction/)
- [Expo 内部分发](https://docs.expo.dev/build/internal-distribution/)

## 本地与线上统一

2026年10月22日已将实际运行镜像中的健康功能与本地角色授权合并。两条旧迁移链都保留，升级统一使用 `alembic upgrade head`；不要手动 stamp 或改写已经执行的版本号。发布及回退约定见 [统一版本说明](deployments/2026-10-22-unified-source.md)。
