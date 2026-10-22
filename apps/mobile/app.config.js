const fs = require("node:fs");
const path = require("node:path");

// 开发包从 Metro 加载当前代码；审核预览包使用本次明确选择的本机地址。
// 线上环境只由 production 构建读取，不能成为开发/预览的默认值。
module.exports = ({ config }) => {
  const profile = process.env.EAS_BUILD_PROFILE || "development";
  const environment =
    profile === "production"
      ? "production"
      : profile === "preview"
        ? "preview"
        : "development";
  const extra = { ...config.extra, appEnvironment: environment };
  if (environment === "preview") {
    const targetPath = path.join(__dirname, "local-preview.json");
    if (!fs.existsSync(targetPath)) {
      throw new Error(
        "缺少本次预览的本地后端地址。请从项目根目录运行 bash scripts/build-android preview。",
      );
    }
    const target = JSON.parse(fs.readFileSync(targetPath, "utf8"));
    const url = new URL(target.apiUrl);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      ["82.157.48.200", "127.0.0.1", "localhost", "::1"].includes(url.hostname)
    ) {
      throw new Error(
        "预览版必须连接手机能访问的本机后端，不能使用线上地址或 localhost。",
      );
    }
    extra.apiUrl = target.apiUrl;
  }
  return {
    ...config,
    name:
      environment === "development"
        ? "安糖心语·开发"
        : environment === "preview"
          ? "安糖心语·预览"
          : config.name,
    extra,
  };
};
