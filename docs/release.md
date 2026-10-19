# 发布一个 App 版本

现在只有一个下载入口：`https://82.157.48.200:8000/download/`。
谁出的包不重要，重要的是**包里的 versionCode 在变大、签名是同一把密钥**。

## 一、versionCode 只增不减

格式 `YYMMDD + 两位当日序号`，例如 `26101901` 表示 2026-10-19 第 01 次发布。
存量用户装的旧包一定小于新包，App 的"检查更新"才能判断出有新版本。

```bash
./scripts/android-version --next            # 打印下一个可用值
./scripts/android-version --apply           # 直接写进 apps/mobile/app.json
./scripts/android-version --check 26101902  # 校验某个值是否合法且更大
```

`apps/mobile/app.json` 里的 `expo.android.versionCode` 必须和要发布的版本一致，
`scripts/publish-apk` 会拒绝不一致的包——包内版本号没改，用户永远收不到更新。

## 二、签名密钥只有一把

换一台机器或换一个人出包，如果签名不同，Android 会拒绝覆盖安装，
提示"应用未安装"，更新链就断在这里。

- 发布密钥存在**仓库之外**：`antang-release.keystore` 与配套的 `antang-release.properties`；
- 至少备份两处（离线盘 + 团队共享的密钥库），丢了这个文件就再也无法给已装的用户发更新；
- 团队里任何出包的人用的都是这一把，密码通过环境变量传入，不写进仓库；
- 当前已装的测试包是 **debug keystore** 签的。第一次切到发布密钥时，用户需要**卸载重装一次**
  （只有这一次）。卸载会清掉手机本地的看板缓存，服务端数据不受影响，登录后重新同步即可。

## 三、出包

```bash
export ANTANG_KEYSTORE=/path/to/antang-release.keystore
export ANTANG_KEYSTORE_PASSWORD_FILE=/path/to/antang-release.properties
export EXPO_PUBLIC_API_URL=https://82.157.48.200:8000
./scripts/build-android-local
```

签名通过 gradle 的 injected signing 参数传入，不修改 `android/` 下任何文件，
所以 `expo prebuild --clean` 之后依然有效。

## 四、发布

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\publish-apk.ps1 `
    -Apk .\安糖心语-xxx.apk -VersionName 1.0.1 -VersionCode 26101902 -Notes "新增量表入口"
```

脚本做四件事：算 SHA-256、写 `latest.json`、上传 APK 与清单、在服务器上重算哈希核对。
发布前它会读线上的 `latest.json`，**如果新包的 versionCode 不比线上大就直接拒绝**。

清单地址：`https://82.157.48.200:8000/download/latest.json`（`application/json`）。

## 五、刻意不做的事

- **不在 GitHub 挂 APK 或下载链接**：仓库现在是源码，`releases` 为空。功能没做完之前不对外分发，
  海报上的 GitHub 二维码只通向源码。
- **不做静默安装**：Android 不允许普通应用在后台安装自己，最多做到"应用内下载 + 系统安装确认"。
  想彻底免安装只能走 `expo-updates` 的 JS 热更新，但它覆盖不了原生模块的改动（例如实时心率）。
- **不公布服务器 IP 之外的入口**：现在下载页是裸 IP + 自签/Let's Encrypt 证书，
  给患者用之前必须换成备案域名。

## 六、应用内检查更新

侧边栏底部有「检查更新」一行，显示当前版本。点一下读 `latest.json`、比 `versionCode`：

- 有新版 → 弹「有新版本」+ 包大小 + 说明，点「去下载」交给系统浏览器下载；
- 已最新 → 弹「已是最新版本」；
- 读不到清单 / 字段不全 → 直接报错，不假装"已是最新"。

下载完仍由系统的安装器确认安装一次——Android 不允许普通应用静默装自己。
清单字段缺一个就报错（`src/update/release.ts`），不用默认值糊过去。

## 七、CI 出包

`.github/workflows/android-release.yml`：手工触发，或推一个 `v*` 标签。Runner 上装
JDK 17 / NDK 27.1.12297006 / CMake 3.22.1 → `expo prebuild` → `gradlew assembleRelease`
（签名走同一把发布密钥）→ 上传 APK + `sha256.txt` + `version.txt`。

需要先在仓库 Settings → Secrets and variables → Actions 里配 4 个值。
运行 `gh-secrets-helper.ps1` 会把它们打印出来（粘完就关窗口，别留在聊天记录里）：

| secret | 内容 |
|---|---|
| `ANTANG_KEYSTORE_BASE64` | 发布密钥文件的 base64 |
| `ANTANG_KEYSTORE_PASSWORD` | 密钥库密码 |
| `ANTANG_KEY_PASSWORD` | 密钥密码 |
| `ANTANG_API_URL` | `https://82.157.48.200:8000` |

**构建不等于发布**：流水线只产出 artifact，对外发布仍要人工跑 `publish-apk.ps1`。
这样出包不会自动影响正在使用的用户。

首次跑可能要调 NDK / CMake 版本，跑通一次之后就稳定了。

