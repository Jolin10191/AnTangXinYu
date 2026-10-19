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

## 六、还没做的

- CI 从 master 自动出包：GitHub Actions 需要 Android SDK 与签名密钥（作为 secrets），
  配好之后"跑流水线即发布"，人不用碰命令行。目前是手动跑上面两步。
- 应用内"检查更新"入口：版本清单已经就绪，App 侧只需读取、比较、弹窗，
  这部分会和下一次重打包一起提交。
