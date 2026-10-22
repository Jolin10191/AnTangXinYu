# 安糖心语

面向 1 型糖尿病用户的长期陪伴 App，关注低血糖恐惧。Android 使用 Expo / React Native，后端使用 FastAPI、PostgreSQL 和 LangGraph。

## 第一次参与开发

先准备 **Git 和 Node.js 24**。Windows 开发使用 WSL Ubuntu，项目和命令都放在 Ubuntu 内；不要混用 Windows 的 Node 或 Python。

```bash
git clone https://github.com/Qzwolf/AnTang.git AnTang
cd AnTang/apps/mobile
npm ci
cp .env.example .env
```

开发和审核预览默认连接本机后端。`EXPO_PUBLIC_API_URL` 是**安糖后端**的地址，和模型服务地址不是一回事。先在项目根目录启动本地后端；尚无模型凭据时可明确选择基础联调：

```bash
bash scripts/dev-api --base-only
```

安装维护者提供的开发 APK，然后运行：

```bash
npm run dev
```

普通局域网使用同一 Wi-Fi；校园网等隔离设备的网络，改在项目根目录运行 `bash scripts/dev-tunnel`，通过已授权的 Cloudflare HTTPS 隧道连接本机后端和 Metro。两种方式均支持页面保存后热更新、后端保存后自动重载。先在本机审核，通过后再发布服务器。完整步骤见 [本地联调说明](docs/local-development.md)。

## 提交前检查

在仓库根目录执行对应的一条命令：

| 改了哪里 | 命令 | 需要准备 |
| --- | --- | --- |
| 手机端 | `bash scripts/check mobile` | Node.js 24 |
| 后端 | `bash scripts/check api` | uv、Python 3.12、独立测试 PostgreSQL（本地 Docker 或 `ANTANG_CHECK_DATABASE_URL`） |
| 两边都有 | `bash scripts/check all` | 上面两套环境 |

脚本安装锁定依赖，再执行检查和测试。后端自动检查使用临时数据库，不需要模型密钥，不会连接团队的业务数据库。

## 协作怎么走

在自己的分支修改 → 运行检查 → 提交 PR → 需要体验时生成测试 APK → 评审与真机验收 → 合并。

PR 写清楚“解决什么问题、怎么验证、有没有迁移或配置变化”。涉及手环权限、数据同步、通知等手机行为时，要写实际设备上的结果。编译通过不能代替真机验证。

## 安装包与维护

医护申请审批、研发账号管理、人数统计、患者授权和医护只读流程见 [角色与患者授权](docs/patient-access.md)。用户确认的手机号验证码登录需求与本批范围见 [账号与审批需求](docs/product/account-registration-and-clinician-review.md)；真实短信配置可用前保留账号密码登录。

- **开发包**连接开发电脑上的 Metro；**预览包**独立运行并连接构建时配置的后端。
- 安装包在 [Expo 项目构建页](https://expo.dev/accounts/wocky528/projects/antang/builds) 获取。分发前核对构建状态为 `FINISHED`、提交编号、API 地址及 Android 签名。

[维护说明](docs/maintainers.md) 包含 GitHub 检查、云构建和服务器发布步骤。

## 目录

| 路径 | 内容 |
| --- | --- |
| `apps/mobile/` | Android App 与移动端测试 |
| `api/` | 后端、数据库迁移与后端测试 |
| `scripts/` | 团队共用的检查和出包入口 |
| `.github/workflows/` | GitHub 自动检查配置 |
| `docs/` | 开发与维护说明 |
| `AGENTS.md` | 已确认的产品范围和项目约定 |

## 当前统一功能

代码已汇合患者／医护／研发管理、医护审批、人员统计和患者授权，以及线上知识库、心理与行为记录、血糖记录和语音处理。注册同时保留知情同意与医护申请校验；本机无模型配置时仍可显式使用基础联调。功能与迁移边界见 [统一版本说明](docs/deployments/2026-10-22-unified-source.md)。
