import { act, create, type ReactTestRenderer } from "react-test-renderer";

import type { GlucoseReading, GlucoseSummary, MealLog, MedicationLog } from "../api/types";
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

const MEAL: MealLog = {
  id: "00000000-0000-0000-0000-000000000002",
  eatenAt: "2026-10-24T12:30:00+08:00",
  mealType: "lunch",
  description: "一碗米饭、青菜、鸡胸",
  carbsGrams: 65,
  createdAt: "2026-10-24T12:31:00+08:00",
};

const MEDICATION: MedicationLog = {
  id: "00000000-0000-0000-0000-000000000003",
  takenAt: "2026-10-24T07:50:00+08:00",
  name: "诺和锐",
  doseText: "6 单位",
  kind: "insulin",
  note: "早餐前",
  createdAt: "2026-10-24T07:51:00+08:00",
};

const DASHBOARD = {
  periodStart: "2026-10-17T00:00:00+08:00",
  periodEnd: "2026-10-24T00:00:00+08:00",
  sources: [
    {
      sourcePackage: "com.huawei.health",
      device: { manufacturer: "HUAWEI", model: "Watch" },
      latestObservedAt: "2026-10-24T12:00:00+08:00",
      daily: [],
      heartRateTrend: [],
      sleepSessions: [],
      totals: {
        heartRateSamples: 0,
        heartRateMinimum: null,
        heartRateMaximum: null,
        heartRateAverage: null,
        steps: 8200,
        distanceMeters: 5600,
        oxygenSaturationSamples: 0,
        oxygenSaturationMinimum: null,
        oxygenSaturationAverage: null,
        restingHeartRateSamples: 0,
        restingHeartRateMinimum: null,
        restingHeartRateMaximum: null,
        restingHeartRateAverage: null,
        sleepSessions: 3,
        sleepMinutes: 370,
      },
    },
  ],
};

function fakeApi(overrides: Record<string, unknown> = {}) {
  return {
    getGlucoseReadings: jest.fn(async () => [READING]),
    getGlucoseSummary: jest.fn(async () => SUMMARY),
    getMealLogs: jest.fn(async () => [MEAL]),
    createMealLog: jest.fn(async () => MEAL),
    deleteMealLog: jest.fn(async () => undefined),
    getMedicationLogs: jest.fn(async () => [MEDICATION]),
    createMedicationLog: jest.fn(async () => MEDICATION),
    deleteMedicationLog: jest.fn(async () => undefined),
    getWearableDashboard: jest.fn(async () => DASHBOARD),
    ...overrides,
  };
}

async function mount(
  api = fakeApi(),
  handlers: { onImport?: () => void; onRecordGlucose?: () => void } = {},
): Promise<ReactTestRenderer> {
  let renderer: ReactTestRenderer | null = null;
  await act(async () => {
    renderer = create(
      <RecordScreen
        api={api as never}
        onImport={handlers.onImport ?? (() => undefined)}
        onRecordGlucose={handlers.onRecordGlucose ?? (() => undefined)}
      />,
    );
  });
  return renderer as unknown as ReactTestRenderer;
}

describe("RecordScreen", () => {
  it("shows a manual reading with its context and note", async () => {
    const tree = await mount();
    const text = JSON.stringify(tree.toJSON());
    expect(text).toContain("5.5 mmol/L");
    expect(text).toContain("空腹");
    expect(text).toContain("早上好");
    expect(text).toContain("低于 3.9 共");
  });

  it("switches to the sensor tab and offers an import action", async () => {
    let imported = 0;
    const tree = await mount(fakeApi(), { onImport: () => (imported += 1) });

    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "传感器来源" }).props.onPress();
    });
    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "导入传感器数据" }).props.onPress();
    });
    expect(imported).toBe(1);
  });

  it("lists meals and saves a new one without leaving the tab", async () => {
    const api = fakeApi();
    const tree = await mount(api);

    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "饮食分类" }).props.onPress();
    });
    expect(JSON.stringify(tree.toJSON())).toContain("一碗米饭、青菜、鸡胸");

    await act(async () => {
      tree.root
        .findByProps({ accessibilityLabel: "这一餐吃了什么" })
        .props.onChangeText("两个包子");
    });
    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "份量一碗" }).props.onPress();
    });
    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "保存这餐" }).props.onPress();
    });

    expect(api.createMealLog).toHaveBeenCalledWith(
      expect.objectContaining({ mealType: "lunch", description: "两个包子", carbsGrams: 45 }),
    );
  });

  it("lists medication and saves one with the text the patient typed", async () => {
    const api = fakeApi();
    const tree = await mount(api);

    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "用药分类" }).props.onPress();
    });
    expect(JSON.stringify(tree.toJSON())).toContain("诺和锐");

    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "药名" }).props.onChangeText("二甲双胍");
    });
    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "剂量" }).props.onChangeText("一片");
    });
    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "选择口服药" }).props.onPress();
    });
    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "保存这次用药" }).props.onPress();
    });

    expect(api.createMedicationLog).toHaveBeenCalledWith(
      expect.objectContaining({ name: "二甲双胍", doseText: "一片", kind: "oral" }),
    );
  });

  it("fills exercise and sleep from the wearable import, not from typing", async () => {
    const tree = await mount();

    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "运动分类" }).props.onPress();
    });
    expect(JSON.stringify(tree.toJSON())).toContain("8,200");

    await act(async () => {
      tree.root.findByProps({ accessibilityLabel: "睡眠分类" }).props.onPress();
    });
    expect(JSON.stringify(tree.toJSON())).toContain("约 6 小时");
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
