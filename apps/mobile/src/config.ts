import Constants from "expo-constants";

const environment = Constants.expoConfig?.extra?.appEnvironment;
const configuredApiUrl = (
  environment === "preview"
    ? Constants.expoConfig?.extra?.apiUrl
    : process.env.EXPO_PUBLIC_API_URL
)?.trim();

if (!configuredApiUrl) {
  throw new Error(
    "缺少 EXPO_PUBLIC_API_URL，请在 apps/mobile/.env 中配置后端地址。",
  );
}

if (!/^https?:\/\//i.test(configuredApiUrl)) {
  throw new Error(
    "EXPO_PUBLIC_API_URL 必须是完整的 http:// 或 https:// 地址。",
  );
}

export const API_URL = configuredApiUrl.replace(/\/+$/, "");

if (
  environment !== "production" &&
  /^https?:\/\/82\.157\.48\.200(?::|\/|$)/i.test(API_URL)
) {
  throw new Error(
    "开发和预览需要连接本机后端，请使用 bash scripts/dev-mobile 启动本地联调。",
  );
}
