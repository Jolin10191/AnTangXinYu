import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import type { ApiClient } from "../api/client";
import type { GlucoseReading, GlucoseSummary } from "../api/types";
import { colors, radii, spacing, typefaces } from "../ui/theme";

export type RecordTabKey = "glucose" | "meals" | "medication" | "activity" | "sleep";

export const RECORD_TABS: { key: RecordTabKey; label: string }[] = [
  { key: "glucose", label: "血糖" },
  { key: "meals", label: "饮食" },
  { key: "medication", label: "用药" },
  { key: "activity", label: "运动" },
  { key: "sleep", label: "睡眠" },
];

const GLUCOSE_CONTEXT_LABELS: Record<string, string> = {
  fasting: "空腹",
  pre_meal: "餐前",
  post_meal: "餐后",
  bedtime: "睡前",
  night: "夜间",
  other: "随时",
};

export function formatGlucose(reading: GlucoseReading): string {
  // 国内血糖习惯用 mmol/L，手输与传感器统一这一种口径，避免同一页两种单位。
  return `${(reading.valueMgDl / 18).toFixed(1)} mmol/L`;
}

export function formatMeasuredAt(iso: string): string {
  const date = new Date(iso);
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hour = `${date.getHours()}`.padStart(2, "0");
  const minute = `${date.getMinutes()}`.padStart(2, "0");
  return `${month}-${day} ${hour}:${minute}`;
}

type Props = {
  api: Pick<ApiClient, "getGlucoseReadings" | "getGlucoseSummary">;
  onImport: () => void;
  onRecordGlucose: () => void;
};

/**
 * 记录页：按论文列的几个维度分栏（血糖 / 饮食 / 用药 / 运动 / 睡眠），
 * 血糖内部再分「手动」与「传感器」两种来源，避免把同一种数据拆成两个入口。
 *
 * 这是导航重构的提案实现：还没有接进 App.tsx，见 README-nav-v2.md。
 */
export function RecordScreen({ api, onImport, onRecordGlucose }: Props) {
  const [tab, setTab] = useState<RecordTabKey>("glucose");
  const [source, setSource] = useState<"manual" | "sensor">("manual");
  const [readings, setReadings] = useState<GlucoseReading[]>([]);
  const [summary, setSummary] = useState<GlucoseSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.getGlucoseReadings(), api.getGlucoseSummary()])
      .then(([rows, nextSummary]) => {
        if (!active) {
          return;
        }
        setReadings(rows);
        setSummary(nextSummary);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(cause instanceof Error ? cause.message : "记录读取失败");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [api]);

  const manualReadings = readings.filter((reading) => reading.source !== "report");

  return (
    <View style={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.title}>记录</Text>
        <Text style={styles.headerHint}>最近 7 天</Text>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.tabRow}
        contentContainerStyle={styles.tabRowContent}
      >
        {RECORD_TABS.map((item) => {
          const selected = item.key === tab;
          return (
            <Pressable
              key={item.key}
              accessibilityRole="tab"
              accessibilityState={{ selected }}
              accessibilityLabel={`${item.label}分类`}
              onPress={() => setTab(item.key)}
              style={[styles.tab, selected ? styles.tabActive : null]}
            >
              <Text style={[styles.tabText, selected ? styles.tabTextActive : null]}>
                {item.label}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <ScrollView contentContainerStyle={styles.body}>
        {tab === "glucose" ? (
          <>
            <View style={styles.segment}>
              {(["manual", "sensor"] as const).map((key) => (
                <Pressable
                  key={key}
                  accessibilityRole="button"
                  accessibilityLabel={key === "manual" ? "手动记录" : "传感器来源"}
                  accessibilityState={{ selected: source === key }}
                  onPress={() => setSource(key)}
                  style={[
                    styles.segmentItem,
                    source === key ? styles.segmentItemActive : null,
                  ]}
                >
                  <Text
                    style={[
                      styles.segmentText,
                      source === key ? styles.segmentTextActive : null,
                    ]}
                  >
                    {key === "manual" ? "手动" : "传感器"}
                  </Text>
                </Pressable>
              ))}
            </View>

            {source === "manual" ? (
              <>
                {summary !== null && summary.count > 0 ? (
                  <View style={styles.card}>
                    <Text style={styles.cardTitle}>最近 7 天</Text>
                    <Text style={styles.cardBody}>
                      平均{" "}
                      {summary.averageMgDl === null
                        ? "—"
                        : `${(summary.averageMgDl / 18).toFixed(1)} mmol/L`}{" "}
                      · 记录 {summary.count} 次 · 低于 3.9 共 {summary.below70Count} 次
                    </Text>
                  </View>
                ) : null}

                {loading ? <ActivityIndicator color={colors.primary} /> : null}
                {error !== null ? <Text style={styles.error}>{error}</Text> : null}
                {manualReadings.length === 0 && !loading ? (
                  <View style={styles.card}>
                    <Text style={styles.cardTitle}>还没有记录</Text>
                    <Text style={styles.cardBody}>
                      手上有刚测的数字就记一条，之后对话里可以直接引用。
                    </Text>
                  </View>
                ) : null}

                {manualReadings.map((reading) => (
                  <View key={reading.id} style={styles.card}>
                    <Text style={styles.cardTitle}>{formatGlucose(reading)}</Text>
                    <Text style={styles.cardBody}>
                      {formatMeasuredAt(reading.measuredAt)} ·{" "}
                      {GLUCOSE_CONTEXT_LABELS[reading.context] ?? reading.context}
                      {reading.note === null ? "" : ` ·「${reading.note}」`}
                    </Text>
                  </View>
                ))}

                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="记一条血糖"
                  onPress={onRecordGlucose}
                  style={styles.primaryButton}
                >
                  <Text style={styles.primaryButtonText}>记一条血糖</Text>
                </Pressable>
              </>
            ) : (
              <>
                <View style={styles.card}>
                  <Text style={styles.cardTitle}>还没有导入传感器数据</Text>
                  <Text style={styles.cardBody}>
                    从厂家 App 导出 CSV，先预览能用的行与可疑行，确认后才入库。
                  </Text>
                </View>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="导入传感器数据"
                  onPress={onImport}
                  style={styles.primaryButton}
                >
                  <Text style={styles.primaryButtonText}>导入传感器数据</Text>
                </Pressable>
              </>
            )}
          </>
        ) : null}

        {tab === "meals" ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>饮食记录 · 下周</Text>
            <Text style={styles.cardBody}>
              先做「餐次 + 份量档位 + 照片」，碳水给估计值、允许改；不做完整营养成分库。
            </Text>
          </View>
        ) : null}

        {tab === "medication" ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>用药记录 · 下周</Text>
            <Text style={styles.cardBody}>
              记录药名、剂量、时间与频次；只记录，不给加减量建议。自行调量的行为会被单独记下，需要时可给医生看。
            </Text>
          </View>
        ) : null}

        {tab === "activity" ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>运动</Text>
            <Text style={styles.cardBody}>
              手环数据（快走、步数）会在这里汇总；对话里提到「不敢运动」会单独标出来，不和你真的做了多少混在一起。
            </Text>
          </View>
        ) : null}

        {tab === "sleep" ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>睡眠</Text>
            <Text style={styles.cardBody}>
              睡眠时长来自手环；夜里的低血糖与夜间复测会标在同一段时间轴上。
            </Text>
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.xs,
  },
  title: {
    color: colors.ink,
    fontFamily: typefaces.sansMedium,
    fontSize: 24,
    fontWeight: "700",
  },
  headerHint: {
    color: colors.faint,
    fontFamily: typefaces.sans,
    fontSize: 12,
  },
  tabRow: {
    flexGrow: 0,
    paddingHorizontal: spacing.md,
  },
  tabRowContent: {
    gap: spacing.xs,
  },
  tab: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.paperMuted,
  },
  tabActive: {
    backgroundColor: colors.primary,
  },
  tabText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 12.5,
  },
  tabTextActive: {
    color: "#FFFFFF",
    fontFamily: typefaces.sansMedium,
    fontWeight: "600",
  },
  body: {
    padding: spacing.md,
    gap: spacing.sm,
  },
  segment: {
    flexDirection: "row",
    backgroundColor: colors.paperMuted,
    borderRadius: radii.pill,
    padding: 3,
  },
  segmentItem: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 6,
    borderRadius: radii.pill,
  },
  segmentItemActive: {
    backgroundColor: colors.paper,
  },
  segmentText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 12.5,
  },
  segmentTextActive: {
    color: colors.primaryPressed,
    fontFamily: typefaces.sansMedium,
    fontWeight: "600",
  },
  card: {
    backgroundColor: colors.paper,
    borderRadius: radii.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    padding: spacing.md,
    gap: 4,
  },
  cardTitle: {
    color: colors.ink,
    fontFamily: typefaces.sansMedium,
    fontSize: 15,
    fontWeight: "600",
  },
  cardBody: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 12.5,
    lineHeight: 19,
  },
  error: {
    color: colors.danger,
    fontFamily: typefaces.sans,
    fontSize: 12.5,
  },
  primaryButton: {
    alignItems: "center",
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
    paddingVertical: 12,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontFamily: typefaces.sansMedium,
    fontSize: 14,
    fontWeight: "600",
  },
});
