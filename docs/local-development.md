# 本地修改、实时联调与审核

流程固定为：**本地修改 → 手机实时联调 → 本机审核 → 审核通过后发布线上**。普通局域网直接连接；校园网、公共 Wi-Fi 等设备隔离网络使用下文的 HTTPS 隧道。

## 使用同一份源码

实际运行目录是 WSL Ubuntu-22.04 的 `/home/zzz_wolf/projects/AnTang`。Windows 编辑器可打开 `\\wsl.localhost\Ubuntu-22.04\home\zzz_wolf\projects\AnTang`。编辑器、后端和 Metro 都读取这一份源码；Windows 解压目录仅作同步交付副本，修改副本不会自动改变运行中的服务。

以下命令在这份 WSL 项目运行。首次安装依赖：`uv sync --project api --frozen`，并在 `apps/mobile` 执行 `npm ci`，使用 Node.js 24。

## 自己修改后立即在手机看

先启动本地后端。尚无模型和搜索凭据时，显式选择基础联调：

```bash
cd /home/zzz_wolf/projects/AnTang
bash scripts/dev-api --base-only
```

脚本启动独立本机数据库、执行迁移并自动重载后端。注册、登录、档案、设备数据和患者授权可用；发送智能聊天会明确提示未配置，主动关怀未启用。补齐 `api/.env` 后，去掉 `--base-only` 启动完整 API；Hindsight 和关怀 Worker 的完整联调另按相应模块配置启动。

另开一个 WSL 终端：

```bash
cd /home/zzz_wolf/projects/AnTang
bash scripts/dev-mobile
```

也可在 `apps/mobile` 运行 `npm run dev`。手机安装**开发 APK**，与电脑连接同一 Wi-Fi，扫描终端的开发二维码。脚本自动选择本机地址，并确认后端为当前角色授权版本；如需手动指定地址，用 `ANTANG_DEV_HOST=电脑IP bash scripts/dev-mobile`。

| 修改内容 | 如何看到反馈 |
| --- | --- |
| 页面和普通 TypeScript 代码 | 保存后手机热更新，通常无需重新安装 |
| `api/src` 下的 Python 逻辑 | 自动重载后，手机再次操作或查询 |
| 数据库结构 | 新增迁移并执行升级后验证 |
| 原生模块、权限、插件及原生配置 | 重新构建并安装开发 APK |

## 给同学审核

校园网请先按下一节启动隧道，再运行 `bash scripts/build-android preview tunnel`。同学无需与电脑连接同一 Wi-Fi。

保持本机后端运行，在移动端改动提交后生成绑定本机地址的审核包：

```bash
bash scripts/build-android preview
# 需要手动指定电脑地址时：
bash scripts/build-android preview http://192.168.1.100:8000
```

审核预览 APK 固定本次页面版本和后端地址，适合大家核对同一版效果；修改页面后需要重新出包。个人实时开发使用开发 APK，不需每次生成审核包。两种包目前使用同一 Android 包名，安装其中一个会替换另一个。

手机和电脑须处于同一局域网，电脑后端保持运行。电脑 IP 改变后审核包需要重新构建；开发包重新连接 Metro 即可。云端遗留的线上地址不会覆盖审核包明确选择的本机目标。本地账号、数据与线上独立，登录凭据也按后端分别保存；先在本机注册测试账号。

安装包下载二维码用于安装 App；开发终端中的二维码用于连接当前电脑代码，二者用途不同。

## 校园网或异地使用 HTTPS 隧道

本机已安装并校验 Cloudflare 官方 `cloudflared`。新电脑请从 [官方发布](https://github.com/cloudflare/cloudflared/releases) 安装对应系统版本，并核对发布页的 SHA-256；将程序放入 PATH 或 `~/.local/bin/cloudflared`。

保持第一个终端的 `bash scripts/dev-api --base-only` 运行，关闭原先的 `dev-mobile`，再在第二个终端执行：

```bash
cd /home/zzz_wolf/projects/AnTang
bash scripts/dev-tunnel
```

脚本为本机 8000 后端和 8081 Metro 分别建立临时 HTTPS 隧道，确认连接后启动实时开发，并打印开发包连接地址与二维码。手机安装现有开发 APK 即可，不需要为切换隧道重新安装开发包。记录保存在不提交的 `artifacts/local-tunnel.json`，隧道诊断日志也在 `artifacts/` 中。脚本只记录连接元数据，不打印账号密码或业务请求。

先用手机浏览器打开输出的后端地址加 `/health`，确认返回 `local-basic`；再用开发包扫描终端二维码。启动器也可手动输入输出的 Metro HTTPS 地址。页面、JS 资源和热更新连接都通过 Metro 隧道，业务请求通过后端隧道。

固定版本审核包：

```bash
bash scripts/build-android preview tunnel
```

脚本检查当前后端仍在线，再把本次后端隧道地址写入审核包。审核包不需要 Metro，但需要本机后端与后端隧道持续运行。现有 `dev-tunnel` 会一起保持这两项服务和 Metro 运行，退出后关闭本次两个公网入口。

公网隧道转发的是本机服务，业务数据仍写入本机数据库；注册、登录、角色和患者授权检查保持有效。拥有网址的人可以访问注册登录入口，查看患者资料仍需有效登录和患者授权。仅将本次连接码与测试账号提供给审核参与者。

这是临时开发隧道，停止后地址失效，重启会生成新地址；开发包重新扫码，固定审核包重新生成。平台没有在线保证，本机已遇到进程仍在重试但平台返回 `Unauthorized: Tunnel not found`、原域名无法解析的情况；此时需重新启动临时隧道，不能只看进程是否存活。当前基础联调因缺少模型配置而不启用智能聊天。Cloudflare Quick Tunnel 不支持 SSE；本项目聊天使用 NDJSON，恢复聊天时需单独验证分块透传、首包延迟、取消和长连接，不能将 SSE 限制直接等同于 NDJSON 不可用。[Cloudflare 官方说明](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

## 每次是否需要重新配置

| 情况 | 需要做什么 |
| --- | --- |
| 保存页面或普通后端代码 | 开发包刷新、后端自动重载；不重新搭建数据库或隧道 |
| 网络短暂断开，隧道进程还在 | cloudflared 会尝试重连；恢复后继续使用当前地址 |
| 关闭本地后端 | 在原项目重新运行 `bash scripts/dev-api --base-only`，已有本地账号和数据保留 |
| 关闭隧道或重启电脑 | 启动后端和 `bash scripts/dev-tunnel`；开发包扫描新连接，固定审核包重新生成 |
| 电脑关机、睡眠或持续断网 | 本机后端不可访问，隧道不能替电脑提供服务 |

目前服务是在本次联调会话中启动，还没有设置 Windows 开机自动启动。数据库使用持久卷，重启服务不会清空本地账号、档案或授权记录。

如果需要长期固定入口，可配置有账号和固定域名的 Cloudflare Tunnel，再设置自动启动；这样减少重启后的配置工作，但电脑仍需在线。如果要求电脑关机后同学也能继续访问，应将审核版本部署到独立测试服务器。测试环境与正式线上环境分开，本机继续用于实时开发。

## 本机设置医护身份

先在本机 App 注册账号，再执行：

```bash
bash scripts/dev-role 医护用户名 clinician --actor 本机维护者
bash scripts/dev-role 研发用户名 researcher --actor 本机维护者
```

这些命令只修改本机数据库。随后以患者、医护两个账号验证授权、读取、撤销、再次读取被拒绝。

## 网络与发布

本机使用 WSL 镜像网络。手机需要访问电脑的 8000（后端）和 8081（Metro）端口。首次配置可在 Windows 管理员 PowerShell 运行 `scripts/enable-local-network.ps1`，只允许同一局域网访问这两个端口，保留其余防火墙限制。本机已完成此项配置。

手机浏览器打开 `http://电脑IP:8000/health` 应看到 `local-basic`。连接失败时检查是否同一 Wi-Fi、路由器是否启用客户端隔离、Windows/Hyper-V 防火墙及 WSL 网络。Windows 本机检查 WSL 服务使用 `http://127.0.0.1:8000/health`；镜像网络默认不允许宿主机绕自己的局域网 IP 回访 WSL，因此 Windows 访问自身局域网 IP 超时不能代替手机的访问结果。手机的 localhost 指向手机自身，不能代替电脑地址。

检查仍使用 `bash scripts/check mobile` 和 `bash scripts/check api`；后端自动检查使用独立临时数据库，不连接本机业务库或线上库。审核通过后再按 [维护说明](maintainers.md) 发布服务器。

依据：[Expo 开发构建](https://docs.expo.dev/develop/development-builds/introduction/)、[Expo CLI](https://docs.expo.dev/more/expo-cli/)、[WSL 网络](https://learn.microsoft.com/en-us/windows/wsl/networking)。
