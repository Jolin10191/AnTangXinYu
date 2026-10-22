# 安糖心语预览断连恢复提示词

如果预览无法登录、注册或加载数据，把下方“可直接发送”整段交给 Codex 执行。不要手动重装数据库，也不要回到校园网局域网直连方案。

## 可直接发送

请恢复安糖心语的本机预览连接，并持续完成到手机可用、安装包和二维码可交付。沿用已经验证成功的 Cloudflare HTTPS 临时隧道方法。用户已授权本地联调、使用 Cloudflare 转发本机后端和实时开发流量，以及上传构建所需源码到现有 Expo 项目生成预览 APK；不要重新询问这些权限。

### 目标和边界

- 后端继续运行在本机；不要连接旧线上后端，也不要部署或修改正式服务器。
- 只使用现有 Cloudflare 隧道方案。校园网设备直连已失败，不再尝试同一 Wi-Fi、局域网 IP、Windows 端口转发、WSL 网络模式改造等方案，也不要轮流试其他隧道供应商。
- 保留现有数据库、账号、健康资料和授权，不清库、不重建卷、不重置密码、不覆盖环境文件、不重置 Git 工作区。
- 当前是基础联调模式，允许注册、登录、档案、医护申请审批、人员管理、患者授权与医护只读查看；模型和搜索未配置，聊天明确提示未配置。短信服务也未配置，不查找密钥、不使用假凭据或假验证码。
- 本次只恢复连接和必要出包。注册冲突报错后修改信息仍无法再次提交的问题已记录，尚未修复；不要把修复业务代码混入恢复任务。

### 项目与已有文件

- Windows 工作区：`D:\Desktop\AnTang-master`；Windows 交付副本：`D:\Desktop\AnTang-master\AnTang-master`。
- 唯一规范源码与运行目录：WSL `Ubuntu-22.04` 的 `/home/zzz_wolf/projects/AnTang`。先阅读其 `AGENTS.md` 和 `docs/local-development.md`。
- 所有项目 Git、Python、Node、Docker、Expo 命令通过 `wsl.exe -d Ubuntu-22.04 -- bash -lc` 在该目录运行。不要在 Windows 副本直接启动项目。
- 演示账号凭据文件：`D:\Desktop\AnTang-master\downloads\local-review-accounts.json`。需要时本地读取，不把其他密钥写入报告或日志。
- 本地 PostgreSQL 使用 Docker Compose 项目 `antang-local`，端口 `55432`，持久卷 `antang-local_local_postgres_data`。使用已有启动脚本即可，不手工重建。
- 已交付功能提交：`cfe9ed7`；文档交付提交：`a1d00ee`；数据库迁移当时为 `k48e9f1a6b52`。这些是定位线索，实际恢复以当前源码、Git 状态和迁移状态为准，不回退版本。

### 先核验，健康的连接不要重启

1. 检查当前 WSL `artifacts/local-tunnel.json`、对应日志、服务进程与端口，先确认没有同项目重复服务。
2. 检查本机 `http://127.0.0.1:8000/health`，预期 JSON 为 `{"status":"ok","mode":"local-basic"}`。
3. 再检查状态文件中 `apiUrl` 的公网 `/health`。进程存活不等于公网可用，必须实际访问 HTTPS。
4. 如果本地和公网均健康、地址与现有 APK 一致，保留服务和现有 APK、二维码；不为了“重新连接”而更换地址。仅在恢复实时开发确有需要时检查 Metro。

2026年10月16日恢复交付时的地址（仅供核对，可能已失效）：

- API：`https://serum-attacked-virginia-army.trycloudflare.com`
- Metro：`https://mathematical-dicke-proprietary-jar.trycloudflare.com`
- 开发包深链：`exp+antang://expo-development-client/?url=https%3A%2F%2Fmathematical-dicke-proprietary-jar.trycloudflare.com`

### 服务或隧道失效时

1. 本地 API 未运行时，在 WSL 项目目录执行 `bash scripts/dev-api --base-only`，保持进程运行。它会使用现有本地数据库并启动自动重载后端；先检查本机 `/health` 成功。
2. API 公网地址失效时，检查当前隧道主管进程及日志。只停止本项目旧的 `scripts/local_tunnel.py` 主管进程，优先 SIGINT 让它清理两个 cloudflared 和 Metro 子进程；核验 8081 已释放。不要照抄历史 PID 或误停其他项目。必要时仅处理经确认属于本项目的残留进程。
3. 在 WSL 项目目录加载现有 Node 环境 `source /home/zzz_wolf/.nvm/nvm.sh`，执行 `bash scripts/dev-tunnel`，保持运行。不要重复启动独立 `dev-mobile` 占用 8081。
4. 该脚本启动 API 与 Metro 两条 Cloudflare 隧道和 Metro，写入 `artifacts/local-tunnel.json`。使用已安装的官方 `~/.local/bin/cloudflared`，沿用已验证的 `http2` 配置。不要重新安装无关工具。
5. 核验新公网 API `/health` 和开发服务；实时调试还需确认开发包能加载 Metro 与热更新连接。读取新状态文件，不能沿用旧地址。

如果电脑重启后需要手动打开终端，两个 WSL 终端分别运行：

```bash
# 终端一：仅当本地 API 未运行时
cd /home/zzz_wolf/projects/AnTang
bash scripts/dev-api --base-only
```

```bash
# 终端二：仅当旧隧道已清理、8081 空闲时
source /home/zzz_wolf/.nvm/nvm.sh
cd /home/zzz_wolf/projects/AnTang
bash scripts/dev-tunnel
```

### API 地址变更时，必须交付新预览 APK

当前固定预览 APK 把 API 地址写在包内。仅启动新隧道或更新网页二维码，无法修复已经安装的旧包。

1. 公网 API 验证成功后，检查 Git 状态，不覆盖或丢弃已有修改。按项目规则确认移动端构建版本可追溯，不绕过 `scripts/build-android` 的检查。
2. 在 WSL 加载 Node 环境后，从项目根执行 `bash scripts/build-android preview tunnel`，继续使用现有 Expo 项目和签名，不新建 Expo 项目。构建上传仍排除密钥、环境文件、本地数据库与患者数据。
3. 等待 EAS 返回 `FINISHED`，不能只提交构建任务就结束。获取真实 APK 地址并下载到 Windows `downloads`。
4. 核验 APK 完整性、既有签名证书、当前 API 隧道地址及已交付的管理功能。已有证书 SHA256：`8abd9b1effa2b0e4915bb60f674b316f6bc8d46e7a44381a0b6f0512c0887fa8`。
5. 重新生成可扫码下载新 APK 的二维码卡片，更新报告的下载链接与配图；同时刷新实时开发连接二维码。二维码生成器见 `downloads/verification/make_local_qr.py`，已有校验工具见同目录。不要使用 AI 绘制二维码。
6. 更新 `downloads/2026-10-16-组会报告.md` 及同名 HTML 中的下载地址和二维码。HTML 内嵌了图片，也要重新生成，不能只替换旁边的 PNG。
7. 告诉大家安装更新后的预览包。开发 APK 无原生变更时可以复用，只需重新扫描当前开发连接码；固定预览包和开发包使用同一包名，会相互替换。

### 交付依据与输出

2026年10月16日恢复交付的固定预览包信息，仅作核对，不代表一直可用：

- EAS 构建：`5c69cc78-7713-4915-9e8a-1569c07c24cb`。
- 下载：`https://expo.dev/artifacts/eas/wop9Feb6mpgyZVkcZDT-ury96kDkIlmJhKMdzjMz7NY.apk`。
- 文件：`downloads/antang-management-preview-20261016-recovery.apk`。
- SHA256：`dc16a1c8b2b1c64369c08679f1662b80d0f1189790eed83402a345c69c484164`。
- 预览下载卡片：`downloads/antang-management-preview-download.png`。
- 实时连接卡片：`downloads/antang-management-live-connect.png`。
- 开发 APK：`https://expo.dev/artifacts/eas/x4YaToHCfywJDUjQLGb3XcaSKBEze-KUMrZsKwk4tLQ.apk`，本地文件 `downloads/antang-development-06621f0.apk`。

最终交付当前健康检查结果、可用 APK 下载链接、可直接分享的下载二维码、实时连接二维码及需要保持运行的进程说明。恢复后保留 API、隧道与 Metro 运行，不在任务结束时关闭它们。不要声称临时隧道保证长期可用；要说明地址变更后固定预览包需要更新。无需重新跑完整业务测试或创建测试患者，除非有证据表明恢复操作影响了业务功能。

## 持续使用说明

电脑开机、联网、不休眠且服务保持运行时，现有连接可以继续使用，不需要每天主动重新配置。但临时隧道没有次日可用保证；仅关闭终端、电脑休眠、网络断开或平台回收入口，都可能造成断连。尚未配置自动开机恢复或稳定域名服务。服务器正式部署后，再使用不依赖个人电脑的固定入口。
