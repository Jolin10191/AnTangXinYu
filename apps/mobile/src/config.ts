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

/**
 * 语音输入默认关着。
 *
 * 后端那套（转写 + 声音的粗状态）已经在线，但要把麦克风按钮放进包里，得先解决
 * 两件没证据的事：m4a 的静音判定还在等 ffmpeg 方案，以及没人验证过语音真的让回应
 * 更好（系统键盘自带的语音输入也能把话变成文字）。所以打测试包时显式写
 * EXPO_PUBLIC_VOICE_INPUT=1 才开，默认的正式包不显示这颗按钮。
 */
export const VOICE_INPUT_ENABLED = process.env.EXPO_PUBLIC_VOICE_INPUT === "1";
