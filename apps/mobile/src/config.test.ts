function loadConfig(mode: string, envUrl: string, previewUrl?: string): string {
  jest.resetModules();
  process.env.EXPO_PUBLIC_API_URL = envUrl;
  jest.doMock("expo-constants", () => ({
    __esModule: true,
    default: {
      expoConfig: { extra: { appEnvironment: mode, apiUrl: previewUrl } },
    },
  }));
  return jest.requireActual<{ API_URL: string }>("./config").API_URL;
}

const original = process.env.EXPO_PUBLIC_API_URL;
afterEach(() => {
  if (original === undefined) delete process.env.EXPO_PUBLIC_API_URL;
  else process.env.EXPO_PUBLIC_API_URL = original;
  jest.resetModules();
});

test("review preview uses its local target even when a cloud environment contains the production URL", () => {
  expect(
    loadConfig(
      "preview",
      "https://82.157.48.200:8000",
      "http://192.168.1.10:8000",
    ),
  ).toBe("http://192.168.1.10:8000");
});

test("development rejects the production backend", () => {
  expect(() => loadConfig("development", "https://82.157.48.200:8000")).toThrow(
    "开发和预览需要连接本机后端",
  );
});

test("only an explicit production build can use the production backend", () => {
  expect(loadConfig("production", "https://82.157.48.200:8000")).toBe(
    "https://82.157.48.200:8000",
  );
});
