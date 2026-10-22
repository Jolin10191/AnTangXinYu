import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  AppState,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { errorMessage, type ApiClient } from "../api/client";
import type {
  HealthProfile,
  PatientAccessGrant,
  PatientPage,
  User,
  WearableDashboard,
} from "../api/types";
import {
  sourceLabel,
  WearableCard,
} from "../health-overview/health-overview-screen";
import { colors, radii, spacing } from "../ui/theme";

function Button({
  title,
  onPress,
  disabled = false,
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      disabled={disabled}
      onPress={onPress}
      style={[s.button, disabled && s.disabled]}
    >
      <Text style={s.buttonText}>{title}</Text>
    </Pressable>
  );
}

type GrantApi = Pick<
  ApiClient,
  | "getPatientGrants"
  | "resolveClinician"
  | "grantPatientAccess"
  | "revokePatientAccess"
  | "me"
  | "updateAccountName"
>;

export function PatientAccessScreen({
  api,
  onClose,
}: {
  api: GrantApi;
  onClose: () => void;
}) {
  const [grants, setGrants] = useState<PatientAccessGrant[]>([]);
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [clinician, setClinician] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void api.me(controller.signal).then(
      (value) => {
        if (!controller.signal.aborted) setFullName(value.fullName ?? "");
      },
      (reason) => {
        if (!controller.signal.aborted) setError(errorMessage(reason));
      },
    );
    return () => controller.abort();
  }, [api]);
  useEffect(() => {
    const controller = new AbortController();
    void api
      .getPatientGrants(controller.signal)
      .then(
        (value) => {
          if (!controller.signal.aborted) {
            setGrants(value);
            setError(null);
          }
        },
        (reason) => {
          if (!controller.signal.aborted) setError(errorMessage(reason));
        },
      )
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api, attempt]);

  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (reason) {
      if (active.current) setError(errorMessage(reason));
    } finally {
      if (active.current) setBusy(false);
    }
  }

  return (
    <SafeAreaView style={s.root}>
      <View style={s.header}>
        <Button title="返回" onPress={onClose} />
        <Text style={s.title}>医护授权</Text>
      </View>
      <ScrollView
        contentContainerStyle={s.body}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={s.hint}>
          授权指定医护只读查看你的健康档案和设备数据。你可以随时撤销；撤销后，该医护再次查询将无法访问。
        </Text>
        <View style={s.card}>
          <Text style={s.subtitle}>我的姓名</Text>
          <Text style={s.hint}>用于获授权医护的患者列表展示。</Text>
          <TextInput
            accessibilityLabel="我的姓名"
            value={fullName}
            onChangeText={setFullName}
            maxLength={64}
            style={s.input}
            editable={!busy}
            placeholder="请填写姓名"
          />
          <Button
            title="保存姓名"
            disabled={busy || !fullName.trim()}
            onPress={() =>
              void act(async () => {
                const updated = await api.updateAccountName(fullName.trim());
                if (active.current) {
                  setFullName(updated.fullName ?? "");
                  setNotice("姓名已保存。");
                }
              })
            }
          />
        </View>
        <View style={s.card}>
          <Text style={s.subtitle}>添加医护</Text>
          <TextInput
            accessibilityLabel="医护完整用户名"
            autoCapitalize="none"
            autoCorrect={false}
            editable={!busy}
            placeholder="输入医护的完整用户名"
            value={username}
            style={s.input}
            onChangeText={(value) => {
              setUsername(value);
              setClinician(null);
            }}
          />
          <Button
            title="核对医护账号"
            disabled={busy || username.trim().length < 3}
            onPress={() =>
              void act(async () => {
                const value = await api.resolveClinician(username.trim());
                if (active.current) setClinician(value);
              })
            }
          />
          {clinician === null ? null : (
            <View style={s.card}>
              <Text style={s.subtitle}>医护：{clinician.username}</Text>
              <Text selectable style={s.hint}>
                账号 ID：{clinician.id}
              </Text>
              <Text style={s.hint}>
                授权范围：健康档案、设备历史数据，只读。请确认这是你指定的医护。
              </Text>
              <Button
                title="确认授权"
                disabled={busy}
                onPress={() =>
                  void act(async () => {
                    const grant = await api.grantPatientAccess(clinician.id);
                    if (active.current) {
                      setGrants((items) => [grant, ...items]);
                      setClinician(null);
                      setUsername("");
                      setNotice("授权成功，医护现在可以查询你的数据。");
                    }
                  })
                }
              />
            </View>
          )}
        </View>
        {error === null ? null : (
          <Text accessibilityRole="alert" style={s.error}>
            {error}
          </Text>
        )}
        {notice === null ? null : <Text style={s.hint}>{notice}</Text>}
        <View style={s.header}>
          <Text style={s.subtitle}>我的授权</Text>
          <Button
            title="刷新授权"
            disabled={busy || loading}
            onPress={() => {
              setLoading(true);
              setAttempt((value) => value + 1);
            }}
          />
        </View>
        {loading ? (
          <ActivityIndicator color={colors.primary} />
        ) : grants.length === 0 && error === null ? (
          <Text style={s.hint}>尚未向任何医护授权。</Text>
        ) : null}
        {grants.map((grant) => (
          <View key={grant.id} style={s.card}>
            <Text style={s.subtitle}>{grant.clinician.username}</Text>
            <Text style={s.hint}>
              {grant.revokedAt !== null
                ? "已撤销"
                : grant.available
                  ? "有效 · 只读"
                  : "账号当前不可用"}
            </Text>
            <Text style={s.hint}>
              授权于 {new Date(grant.grantedAt).toLocaleString("zh-CN")}
            </Text>
            {grant.revokedAt !== null ? (
              <Text style={s.hint}>
                撤销于 {new Date(grant.revokedAt).toLocaleString("zh-CN")}
              </Text>
            ) : (
              <Button
                title={`撤销 ${grant.clinician.username} 的授权`}
                disabled={busy}
                onPress={() => {
                  Alert.alert(
                    "撤销授权",
                    `撤销后，${grant.clinician.username} 再次查询将无法访问你的数据。`,
                    [
                      { text: "取消", style: "cancel" },
                      {
                        text: "撤销授权",
                        style: "destructive",
                        onPress: () =>
                          void act(async () => {
                            await api.revokePatientAccess(grant.id);
                            if (active.current) {
                              setGrants((items) =>
                                items.filter((item) => item.id !== grant.id),
                              );
                              setAttempt((value) => value + 1);
                              setNotice("已撤销授权。");
                            }
                          }),
                      },
                    ],
                  );
                }}
              />
            )}
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

type ClinicianApi = Pick<
  ApiClient,
  | "getPatients"
  | "getPatientHealthProfile"
  | "getPatientWearableDashboard"
  | "logout"
>;
type Detail = { profile: HealthProfile; dashboard: WearableDashboard };

export function ClinicianScreen({
  api,
  user,
  onSignedOut,
}: {
  api: ClinicianApi;
  user: User;
  onSignedOut: () => void;
}) {
  const [page, setPage] = useState<PatientPage>({
    patients: [],
    nextAfter: null,
  });
  const [selected, setSelected] = useState<User | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(user.role === "clinician");
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [after, setAfter] = useState<string | undefined>();
  const [foreground, setForeground] = useState(true);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      setForeground(state === "active");
      setDetail(null);
      setPage({ patients: [], nextAfter: null });
      setAfter(undefined);
      setLoading(state === "active");
      setError(null);
      if (state === "active") setAttempt((value) => value + 1);
    });
    return () => subscription.remove();
  }, []);

  useEffect(() => {
    if (!foreground || user.role !== "clinician") return;
    const controller = new AbortController();
    // 切换患者、刷新或回前台时清除上一次结果；失败时绝不继续展示旧档案。
    const task =
      selected === null
        ? api.getPatients(after, controller.signal).then((value) => {
            if (!controller.signal.aborted) setPage(value);
          })
        : Promise.all([
            api.getPatientHealthProfile(selected.id, controller.signal),
            api.getPatientWearableDashboard(selected.id, controller.signal),
          ]).then(([profile, dashboard]) => {
            if (!controller.signal.aborted) setDetail({ profile, dashboard });
          });
    void task
      .catch((reason) => {
        if (!controller.signal.aborted) setError(errorMessage(reason));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api, user.role, selected, attempt, after, foreground]);

  return (
    <SafeAreaView style={s.root}>
      <View style={s.header}>
        {selected === null ? null : (
          <Button
            title="返回患者列表"
            onPress={() => {
              setSelected(null);
              setDetail(null);
              setAfter(undefined);
              setLoading(true);
              setError(null);
            }}
          />
        )}
        <Text style={s.title}>
          {user.role === "researcher"
            ? "研发账号"
            : selected === null
              ? "授权患者"
              : selected.fullName || "患者详情"}
        </Text>
        <Button
          title="退出登录"
          onPress={() => {
            void api
              .logout()
              .then(onSignedOut, (reason) => setError(errorMessage(reason)));
          }}
        />
      </View>
      <ScrollView contentContainerStyle={s.body}>
        <Text style={s.hint}>
          {user.username} · {user.role === "clinician" ? "医护 · 只读" : "研发"}
        </Text>
        {user.role === "researcher" ? (
          <Text style={s.hint}>
            此账号没有患者资料访问权限。研究数据管理将在后续开放。
          </Text>
        ) : (
          <>
            <Button
              title={selected === null ? "刷新患者列表" : "重新查询患者数据"}
              disabled={loading}
              onPress={() => {
                setDetail(null);
                setPage({ patients: [], nextAfter: null });
                setLoading(true);
                setError(null);
                setAttempt((value) => value + 1);
              }}
            />
            {loading ? <ActivityIndicator color={colors.primary} /> : null}
            {error === null ? null : (
              <Text accessibilityRole="alert" style={s.error}>
                {error}
              </Text>
            )}
            {selected === null ? (
              <>
                <Text style={s.subtitle}>患者列表</Text>
                <Text style={s.hint}>
                  点击患者所在行查看完整健康档案和已有设备数据。
                </Text>
                {!loading && error === null && page.patients.length === 0 ? (
                  <Text style={s.hint}>
                    当前没有有效授权的患者。请患者在“医护授权”中指定你的完整用户名。
                  </Text>
                ) : null}
                {page.patients.map((patient) => (
                  <Pressable
                    key={patient.id}
                    style={s.patientRow}
                    accessibilityRole="button"
                    accessibilityLabel={`查看 ${patient.fullName || "未填写姓名"}，账号 ID ${patient.id}`}
                    onPress={() => {
                      setDetail(null);
                      setSelected(patient);
                      setLoading(true);
                      setError(null);
                      setPage({ patients: [], nextAfter: null });
                    }}
                  >
                    <Text style={s.patientName}>
                      {patient.fullName || "未填写姓名"}
                    </Text>
                    <Text selectable style={s.patientId}>
                      {patient.id}
                    </Text>
                  </Pressable>
                ))}
                {page.nextAfter === null ? null : (
                  <Button
                    title="下一页患者"
                    disabled={loading}
                    onPress={() => {
                      setAfter(page.nextAfter ?? undefined);
                      setPage({ patients: [], nextAfter: null });
                      setLoading(true);
                      setError(null);
                    }}
                  />
                )}
                {after === undefined ? null : (
                  <Button
                    title="回到第一页"
                    disabled={loading}
                    onPress={() => {
                      setAfter(undefined);
                      setPage({ patients: [], nextAfter: null });
                      setLoading(true);
                      setError(null);
                    }}
                  />
                )}
              </>
            ) : detail === null ? null : (
              <PatientData detail={detail} />
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function PatientData({ detail: { profile, dashboard } }: { detail: Detail }) {
  const personal = profile.personalProfile;
  const rows: [string, string | number | null][] = [
    ["性别", personal.sex],
    ["年龄（岁）", personal.ageYears],
    ["身高（cm）", personal.heightCm],
    ["体重（kg）", personal.weightKg],
    ["常住地", personal.residentArea],
    ["作息", personal.scheduleType],
    ["职业", personal.occupation],
  ];
  return (
    <>
      <Text style={s.hint}>以下为服务器已保存的历史记录，非实时测量。</Text>
      <View style={s.card}>
        <Text style={s.subtitle}>基础档案 · 只读</Text>
        {rows.map(([label, value]) => (
          <Text key={label} style={s.text}>
            {label}：{value ?? "未填写"}
          </Text>
        ))}
      </View>
      <View style={s.card}>
        <Text style={s.subtitle}>健康情况</Text>
        {profile.healthFacts.length === 0 ? (
          <Text style={s.hint}>暂无记录。</Text>
        ) : (
          profile.healthFacts.map((fact) => (
            <Text key={fact.id} style={s.text}>
              {fact.statement} · {fact.assertion === "absent" ? "否认" : "存在"}{" "}
              ·{" "}
              {fact.temporalStatus === "past"
                ? "既往"
                : fact.temporalStatus === "current"
                  ? "当前"
                  : "时间未注明"}
            </Text>
          ))
        )}
      </View>
      <Text style={s.subtitle}>最近设备记录</Text>
      {profile.wearableLatest.length === 0 ? (
        <Text style={s.hint}>暂无已保存的设备数据。</Text>
      ) : (
        profile.wearableLatest.map((item) => (
          <WearableCard
            key={`${item.recordType}:${item.sourcePackage}`}
            observation={item}
            heartRateTrend={profile.heartRateTrend}
          />
        ))
      )}
      <Text style={s.subtitle}>近 30 天数据概况</Text>
      <Text style={s.hint}>
        {new Date(dashboard.periodStart).toLocaleDateString("zh-CN")} 至{" "}
        {new Date(dashboard.periodEnd).toLocaleDateString("zh-CN")}
      </Text>
      {dashboard.sources.map((source) => (
        <View key={source.sourcePackage} style={s.card}>
          <Text style={s.subtitle}>{sourceLabel(source.sourcePackage)}</Text>
          <Text style={s.hint}>
            最新观测：
            {new Date(source.latestObservedAt).toLocaleString("zh-CN")}
          </Text>
          <Text style={s.text}>
            步数：{source.totals.steps} 步 · 距离：
            {source.totals.distanceMeters.toFixed(0)} m
          </Text>
          <Text style={s.text}>
            心率采样：{source.totals.heartRateSamples} 条 · 平均：
            {source.totals.heartRateAverage?.toFixed(1) ?? "无记录"} 次/分
          </Text>
          <Text style={s.text}>
            睡眠记录：{source.totals.sleepSessions} 次 · 合计：
            {source.totals.sleepMinutes.toFixed(0)} 分钟
          </Text>
        </View>
      ))}
    </>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.xs,
    padding: spacing.sm,
    flexWrap: "wrap",
  },
  body: { padding: spacing.md, gap: spacing.md, paddingBottom: spacing.xxxl },
  title: { fontSize: 22, fontWeight: "700", color: colors.ink },
  subtitle: { fontSize: 17, fontWeight: "600", color: colors.ink },
  card: {
    padding: spacing.md,
    gap: spacing.sm,
    backgroundColor: colors.paper,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
  },
  patientRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.md,
    minHeight: 64,
    borderBottomWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.paper,
  },
  patientName: { flex: 1, color: colors.ink, fontWeight: "600", fontSize: 16 },
  patientId: { flex: 2, color: colors.muted, fontSize: 12 },
  hint: { color: colors.muted, fontSize: 14, lineHeight: 22 },
  text: { color: colors.text, fontSize: 15, lineHeight: 23 },
  error: { color: colors.danger, fontSize: 14, lineHeight: 22 },
  button: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radii.sm,
    backgroundColor: colors.primarySoft,
    alignSelf: "flex-start",
  },
  buttonText: { color: colors.primaryPressed, fontSize: 14, fontWeight: "600" },
  disabled: { opacity: 0.45 },
  input: {
    color: colors.ink,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radii.sm,
    padding: spacing.sm,
    fontSize: 16,
  },
});
