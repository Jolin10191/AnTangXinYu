import { tokenKeyForApiUrl } from "./token-store";
jest.mock("../config", () => ({ API_URL: "http://192.168.1.10:8000" }));

test("local and production sessions use separate storage keys", () => {
  const local = tokenKeyForApiUrl("http://192.168.1.10:8000");
  const production = tokenKeyForApiUrl("https://82.157.48.200:8000");
  expect(local).not.toBe(production);
  expect(local).not.toBe("antang.auth.tokens");
  expect(local).toMatch(/^[a-zA-Z0-9._-]+$/);
  expect(tokenKeyForApiUrl("http://192.168.1.10:8000/")).toBe(local);
});
