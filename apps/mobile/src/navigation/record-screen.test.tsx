import { act, create, type ReactTestRenderer } from "react-test-renderer";

import type { GlucoseReading, GlucoseSummary } from "../api/types";
import { RecordScreen, formatGlucose, formatMeasuredAt } from "./record-screen";

const READING: GlucoseReading = {
  id: "00000000-0000-0000-0000-000000000001",
  valueMgDl: 99,
  measuredAt: "2026-10-24T12:35:00+08:00",
  context: "fasting",
  source: "manual",
  note: "早上好",
  revokedAt: null,
  createdAt: "2026-10-24T12:36:00+08:00",
};

const SUMMARY: GlucoseSummary = {
  days: 7,
  count: 1,
  averageMgDl: 99,
  minimumMgDl: 99,
  maximumMgDl: 99,
  below70Count: 0,
};

async function mount(
  readings: GlucoseReading[],
  summary: GlucoseSummary,
  handlers: { onImport?: () => void; onRecordGlucose?: () => void } = {},
): Promise<ReactTestRenderer> {
  const api = {
    getGlucoseReadings: jest.fn(async () => readings),
    getGlucoseSummary: jest.fn(async () => summary),
  };
  let renderer: ReactTestRenderer | null = null;
  await act(async () => {
    renderer = create(
      <RecordScreen
        api={api}
        onImport={handlers.onImport ?? (() => undefined)}
        onRecordGlucose={handlers.onRecordGlucose ?? (() => undefined)}
      />,
    );
  });
  return renderer as unknown as ReactTestRenderer;
}

describe("RecordScreen", () => {
  it("shows a manual reading with its context and note", async () => {
    const tree = await mount([READING], SUMMARY);
    const text = JSON.stringify(tree.toJSON());
    expect(text).toContain("5.5 mmol/L");
    expect(text).toContain("空腹");
    expect(text).toContain("早上好");
    expect(text).toContain("低于 3.9 共");
  });

  it("switches to the sensor tab and offers an import action", async () => {
    let imported = 0;
    const tree = await mount([READING], SUMMARY, { onImport: () => (imported += 1) });

    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "传感器来源" }).props.onPress();
    });

    const button = tree.root.findByProps({ accessibilityLabel: "导入传感器数据" });
    await act(async () => {
      button.props.onPress();
    });
    expect(imported).toBe(1);
  });

  it("keeps meals as a next-week placeholder instead of an empty screen", async () => {
    const tree = await mount([READING], SUMMARY);
    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "饮食分类" }).props.onPress();
    });
    expect(JSON.stringify(tree.toJSON())).toContain("下周");
  });
});

describe("record formatting", () => {
  it("shows every reading in mmol/L, the unit patients here actually use", () => {
    expect(formatGlucose(READING)).toBe("5.5 mmol/L");
    expect(formatGlucose({ ...READING, valueMgDl: 86 })).toBe("4.8 mmol/L");
  });

  it("formats the measurement time as month-day hour:minute", () => {
    const text = formatMeasuredAt("2026-10-24T12:35:00+08:00");
    expect(text).toMatch(/^10-2[34] \d{2}:\d{2}$/);
  });
});
