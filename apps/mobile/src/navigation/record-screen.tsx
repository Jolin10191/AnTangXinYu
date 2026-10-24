import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import type { ApiClient } from "../api/client";
import type {
  GlucoseReading,
  GlucoseSummary,
  MealLog,
  MedicationLog,
  WearableDashboard,
} from "../api/types";
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

const MEAL_LABELS: Record<string, string> = {
  breakfast: "早餐",
  lunch: "午餐",
  dinner: "晚餐",
  snack: "加餐",
};

const MEDICATION_LABELS: Record<string, string> = {
  insulin: "胰岛素",
  oral: "口服药",
  other: "其它",
};

// 份量档位只用来给一个粗估，患者可以改；不做食物库、不做精确营养计算。
const PORTIONS: { label: string; grams: number }[] = [
  { label: "半碗", grams: 20 },
  { label: "一碗", grams: 45 },
  { label: "两碗", grams: 80 },
];

// 记的是真实发生的时间：下午才想起早上十点吃的药，就选「3 小时前」而不是现在。
const EVENT_OFFSETS: { label: string; minutes: number }[] = [
  { label: "刚才", minutes: 0 },
  { label: "30 分钟前", minutes: 30 },
  { label: "1 小时前", minutes: 60 },
  { label: "2 小时前", minutes: 120 },
  { label: "3 小时前", minutes: 180 },
];

export function formatGlucose(reading: GlucoseReading): string {
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

export function eventIso(minutesAgo: number): string {
  const now = new Date(Date.now() - minutesAgo * 60_000);
  const offset = -now.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const hours = `${Math.floor(Math.abs(offset) / 60)}`.padStart(2, "0");
  const minutes = `${Math.abs(offset) % 60}`.padStart(2, "0");
  return `${now.getFullYear()}-${`${now.getMonth() + 1}`.padStart(2, "0")}-${`${now.getDate()}`.padStart(2, "0")}T${`${now.getHours()}`.padStart(2, "0")}:${`${now.getMinutes()}`.padStart(2, "0")}:00${sign}${hours}:${minutes}`;
}

export function nowIso(): string {
  return eventIso(0);
}

type Props = {
  api: Pick<
    ApiClient,
    | "getGlucoseReadings"
    | "getGlucoseSummary"
    | "getMealLogs"
    | "createMealLog"
    | "deleteMealLog"
    | "getMedicationLogs"
    | "createMedicationLog"
    | "deleteMedicationLog"
    | "getWearableDashboard"
  >;
  onImport: () => void;
  onRecordGlucose: () => void;
};

/**
 * 记录页：血糖 / 饮食 / 用药 / 运动 / 睡眠。
 * 血糖内部再分「手动 / 传感器」两种来源；运动与睡眠的数据来自手环导入。
 *
 * 这是导航重构的提案实现：还没有接进 App.tsx，见 README-nav-v2.md。
 */
export function RecordScreen({ api, onImport, onRecordGlucose }: Props) {
  const [tab, setTab] = useState<RecordTabKey>("glucose");
  const [source, setSource] = useState<"manual" | "sensor">("manual");

  const [readings, setReadings] = useState<GlucoseReading[]>([]);
  const [summary, setSummary] = useState<GlucoseSummary | null>(null);
  const [meals, setMeals] = useState<MealLog[]>([]);
  const [medications, setMedications] = useState<MedicationLog[]>([]);
  const [dashboard, setDashboard] = useState<WearableDashboard | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [mealType, setMealType] = useState<"breakfast" | "lunch" | "dinner" | "snack">(
    "lunch",
  );
  const [mealMinutesAgo, setMealMinutesAgo] = useState(0);
  const [mealDescription, setMealDescription] = useState("");
  const [mealCarbs, setMealCarbs] = useState<string>("");
  const [medMinutesAgo, setMedMinutesAgo] = useState(0);
  const [medName, setMedName] = useState("");
  const [medDose, setMedDose] = useState("");
  const [medKind, setMedKind] = useState<"insulin" | "oral" | "other">("insulin");

  useEffect(() => {
    let active = true;
    Promise.all([
      api.getGlucoseReadings(),
      api.getGlucoseSummary(),
      api.getMealLogs(),
      api.getMedicationLogs(),
      api.getWearableDashboard(),
    ])
      .then(([rows, nextSummary, nextMeals, nextMedications, nextDashboard]) => {
        if (!active) {
          return;
        }
        setReadings(rows);
        setSummary(nextSummary);
        setMeals(nextMeals);
        setMedications(nextMedications);
        setDashboard(nextDashboard);
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

  const totalSteps =
    dashboard?.sources.reduce(
      (sum, sourceItem) => sum + sourceItem.totals.steps,
      0,
    ) ?? 0;
  const sleepMinutes =
    dashboard?.sources.reduce(
      (sum, sourceItem) => sum + sourceItem.totals.sleepMinutes,
      0,
    ) ?? 0;
  const sleepSessions =
    dashboard?.sources.reduce(
      (sum, sourceItem) => sum + sourceItem.totals.sleepSessions,
      0,
    ) ?? 0;

  async function saveMeal() {
    setSaving(true);
    try {
      const created = await api.createMealLog({
        eatenAt: eventIso(mealMinutesAgo),
        mealType,
        description: mealDescription.trim(),
        carbsGrams: mealCarbs.trim() === "" ? null : Number(mealCarbs),
      });
      setMeals((current) => [created, ...current]);
      setMealDescription("");
      setMealCarbs("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "这餐没记上");
    } finally {
      setSaving(false);
    }
  }

  async function saveMedication() {
    setSaving(true);
    try {
      const created = await api.createMedicationLog({
        takenAt: eventIso(medMinutesAgo),
        name: medName.trim(),
        doseText: medDose.trim(),
        kind: medKind,
      });
      setMedications((current) => [created, ...current]);
      setMedName("");
      setMedDose("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "这条用药没记上");
    } finally {
      setSaving(false);
    }
  }

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
        {loading ? <ActivityIndicator color={colors.primary} /> : null}
        {error !== null ? <Text style={styles.error}>{error}</Text> : null}

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
          <>
            {meals.length === 0 ? (
              <View style={styles.card}>
                <Text style={styles.cardTitle}>还没有记过饭</Text>
                <Text style={styles.cardBody}>
                  记「吃了什么 + 大概多少」就够了，碳水是估计值，可以改。
                </Text>
              </View>
            ) : null}
            {meals.map((meal) => (
              <View key={meal.id} style={styles.card}>
                <Text style={styles.cardTitle}>
                  {MEAL_LABELS[meal.mealType] ?? meal.mealType}
                  {meal.carbsGrams === null ? "" : ` · 碳水约 ${meal.carbsGrams} g`}
                </Text>
                <Text style={styles.cardBody}>
                  {formatMeasuredAt(meal.eatenAt)}
                  {meal.description === "" ? "" : ` · ${meal.description}`}
                </Text>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="删除这条饮食记录"
                  onPress={() =>
                    void api
                      .deleteMealLog(meal.id)
                      .then(() =>
                        setMeals((current) => current.filter((row) => row.id !== meal.id)),
                      )
                      .catch((cause: unknown) =>
                        setError(cause instanceof Error ? cause.message : "删除失败"),
                      )
                  }
                >
                  <Text style={styles.linkDanger}>删除</Text>
                </Pressable>
              </View>
            ))}

            <View style={styles.form}>
              <Text style={styles.formTitle}>记一餐</Text>
              <View style={styles.chipRow}>
                {(["breakfast", "lunch", "dinner", "snack"] as const).map((key) => (
                  <Pressable
                    key={key}
                    accessibilityRole="button"
                    accessibilityLabel={`选择${MEAL_LABELS[key] ?? key}`}
                    onPress={() => setMealType(key)}
                    style={[styles.chip, mealType === key ? styles.chipActive : null]}
                  >
                    <Text
                      style={[styles.chipText, mealType === key ? styles.chipTextActive : null]}
                    >
                      {MEAL_LABELS[key] ?? key}
                    </Text>
                  </Pressable>
                ))}
              </View>
              <TextInput
                accessibilityLabel="这一餐吃了什么"
                placeholder="吃了什么（可选）"
                placeholderTextColor={colors.faint}
                value={mealDescription}
                onChangeText={setMealDescription}
                style={styles.input}
                maxLength={200}
              />
              <View style={styles.chipRow}>
                {PORTIONS.map((portion) => (
                  <Pressable
                    key={portion.label}
                    accessibilityRole="button"
                    accessibilityLabel={`份量${portion.label}`}
                    onPress={() => setMealCarbs(`${portion.grams}`)}
                    style={[styles.chip, mealCarbs === `${portion.grams}` ? styles.chipActive : null]}
                  >
                    <Text
                      style={[
                        styles.chipText,
                        mealCarbs === `${portion.grams}` ? styles.chipTextActive : null,
                      ]}
                    >
                      {portion.label}
                    </Text>
                  </Pressable>
                ))}
                <TextInput
                  accessibilityLabel="碳水估计值"
                  placeholder="碳水 g"
                  placeholderTextColor={colors.faint}
                  value={mealCarbs}
                  onChangeText={setMealCarbs}
                  keyboardType="number-pad"
                  style={[styles.input, styles.inputNarrow]}
                  maxLength={3}
                />
              </View>
              <Text style={styles.fieldLabel}>这一餐是什么时候吃的</Text>
              <View style={styles.chipRow}>
                {EVENT_OFFSETS.map((option) => (
                  <Pressable
                    key={option.label}
                    accessibilityRole="button"
                    accessibilityLabel={`这一餐${option.label}`}
                    onPress={() => setMealMinutesAgo(option.minutes)}
                    style={[
                      styles.chip,
                      mealMinutesAgo === option.minutes ? styles.chipActive : null,
                    ]}
                  >
                    <Text
                      style={[
                        styles.chipText,
                        mealMinutesAgo === option.minutes
                          ? styles.chipTextActive
                          : null,
                      ]}
                    >
                      {option.label}
                    </Text>
                  </Pressable>
                ))}
              </View>
              <Text style={styles.cardHint}>
                记到 {formatMeasuredAt(eventIso(mealMinutesAgo))}，不是现在。
              </Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="保存这餐"
                onPress={() => void saveMeal()}
                disabled={saving}
                style={[styles.primaryButton, saving ? styles.buttonDisabled : null]}
              >
                <Text style={styles.primaryButtonText}>保存这餐</Text>
              </Pressable>
            </View>
          </>
        ) : null}

        {tab === "medication" ? (
          <>
            {medications.length === 0 ? (
              <View style={styles.card}>
                <Text style={styles.cardTitle}>还没有记过用药</Text>
                <Text style={styles.cardBody}>
                  记下药名、剂量和时间。这里只记录，不算剂量、不给建议。
                </Text>
              </View>
            ) : null}
            {medications.map((log) => (
              <View key={log.id} style={styles.card}>
                <Text style={styles.cardTitle}>
                  {log.name}
                  {log.doseText === "" ? "" : ` · ${log.doseText}`}
                </Text>
                <Text style={styles.cardBody}>
                  {formatMeasuredAt(log.takenAt)} · {MEDICATION_LABELS[log.kind] ?? log.kind}
                  {log.note === null ? "" : ` · ${log.note}`}
                </Text>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="删除这条用药记录"
                  onPress={() =>
                    void api
                      .deleteMedicationLog(log.id)
                      .then(() =>
                        setMedications((current) =>
                          current.filter((row) => row.id !== log.id),
                        ),
                      )
                      .catch((cause: unknown) =>
                        setError(cause instanceof Error ? cause.message : "删除失败"),
                      )
                  }
                >
                  <Text style={styles.linkDanger}>删除</Text>
                </Pressable>
              </View>
            ))}

            <View style={styles.form}>
              <Text style={styles.formTitle}>记一次用药</Text>
              <View style={styles.chipRow}>
                {(["insulin", "oral", "other"] as const).map((key) => (
                  <Pressable
                    key={key}
                    accessibilityRole="button"
                    accessibilityLabel={`选择${MEDICATION_LABELS[key] ?? key}`}
                    onPress={() => setMedKind(key)}
                    style={[styles.chip, medKind === key ? styles.chipActive : null]}
                  >
                    <Text
                      style={[styles.chipText, medKind === key ? styles.chipTextActive : null]}
                    >
                      {MEDICATION_LABELS[key] ?? key}
                    </Text>
                  </Pressable>
                ))}
              </View>
              <TextInput
                accessibilityLabel="药名"
                placeholder="药名（例如 诺和锐）"
                placeholderTextColor={colors.faint}
                value={medName}
                onChangeText={setMedName}
                style={styles.input}
                maxLength={64}
              />
              <TextInput
                accessibilityLabel="剂量"
                placeholder="剂量（例如 6 单位 / 一片）"
                placeholderTextColor={colors.faint}
                value={medDose}
                onChangeText={setMedDose}
                style={styles.input}
                maxLength={64}
              />
              <Text style={styles.fieldLabel}>这次用药是什么时候</Text>
              <View style={styles.chipRow}>
                {EVENT_OFFSETS.map((option) => (
                  <Pressable
                    key={option.label}
                    accessibilityRole="button"
                    accessibilityLabel={`这次用药${option.label}`}
                    onPress={() => setMedMinutesAgo(option.minutes)}
                    style={[
                      styles.chip,
                      medMinutesAgo === option.minutes ? styles.chipActive : null,
                    ]}
                  >
                    <Text
                      style={[
                        styles.chipText,
                        medMinutesAgo === option.minutes
                          ? styles.chipTextActive
                          : null,
                      ]}
                    >
                      {option.label}
                    </Text>
                  </Pressable>
                ))}
              </View>
              <Text style={styles.cardHint}>
                记到 {formatMeasuredAt(eventIso(medMinutesAgo))}，不是现在。
              </Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="保存这次用药"
                onPress={() => void saveMedication()}
                disabled={saving || medName.trim() === ""}
                style={[
                  styles.primaryButton,
                  saving || medName.trim() === "" ? styles.buttonDisabled : null,
                ]}
              >
                <Text style={styles.primaryButtonText}>保存这次用药</Text>
              </Pressable>
            </View>
          </>
        ) : null}

        {tab === "activity" ? (
          <>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>手环里的运动</Text>
              <Text style={styles.cardBody}>
                近 7 天步数 {totalSteps.toLocaleString()} 步
                {sleepSessions > 0 ? ` · 睡眠 ${sleepSessions} 段` : ""}
              </Text>
              <Text style={styles.cardHint}>
                数据来自手环导入（华为运动健康 / Health Connect），不需要再手填。
              </Text>
            </View>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>对话里提到的回避</Text>
              <Text style={styles.cardBody}>
                「不敢运动」这类话会单独标出来，不和你真的做了多少混在一起。
              </Text>
            </View>
          </>
        ) : null}

        {tab === "sleep" ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>手环里的睡眠</Text>
            <Text style={styles.cardBody}>
              {sleepMinutes > 0
                ? `共 ${sleepSessions} 段，合计约 ${Math.round(sleepMinutes / 60)} 小时`
                : "还没有导入睡眠数据"}
            </Text>
            <Text style={styles.cardHint}>
              夜里的低血糖与夜间复测会标在同一段时间轴上；睡眠数据来自手环，不单独手填。
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
  cardHint: {
    color: colors.faint,
    fontFamily: typefaces.sans,
    fontSize: 11.5,
    lineHeight: 17,
  },
  fieldLabel: {
    color: colors.muted,
    fontFamily: typefaces.sansMedium,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 4,
  },
  error: {
    color: colors.danger,
    fontFamily: typefaces.sans,
    fontSize: 12.5,
  },
  linkDanger: {
    color: colors.danger,
    fontFamily: typefaces.sans,
    fontSize: 12,
    marginTop: 4,
  },
  form: {
    backgroundColor: colors.paper,
    borderRadius: radii.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    padding: spacing.md,
    gap: spacing.xs,
  },
  formTitle: {
    color: colors.ink,
    fontFamily: typefaces.sansMedium,
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 2,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    alignItems: "center",
  },
  chip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.paperMuted,
  },
  chipActive: {
    backgroundColor: colors.primarySoft,
  },
  chipText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 12,
  },
  chipTextActive: {
    color: colors.primaryPressed,
    fontFamily: typefaces.sansMedium,
    fontWeight: "600",
  },
  input: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    borderRadius: radii.md,
    backgroundColor: colors.paperMuted,
    paddingHorizontal: spacing.sm,
    paddingVertical: 9,
    color: colors.ink,
    fontFamily: typefaces.sans,
    fontSize: 13.5,
  },
  inputNarrow: {
    width: 92,
  },
  primaryButton: {
    alignItems: "center",
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
    paddingVertical: 12,
    marginTop: spacing.xs,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontFamily: typefaces.sansMedium,
    fontSize: 14,
    fontWeight: "600",
  },
});
