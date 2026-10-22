import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  AppState,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { errorMessage, type ApiClient } from "../api/client";
import type {
  ApplicationsPage,
  ApplicationStatus,
  PatientPage,
  User,
  UserOverview,
} from "../api/types";
import { colors } from "../ui/theme";
import { ManagementButton as Button, m } from "./management-ui";

type AdminApi = Pick<
  ApiClient,
  | "getAdminOverview"
  | "getClinicianApplications"
  | "reviewClinicianApplication"
  | "getClinicians"
  | "createClinician"
  | "assignClinician"
  | "logout"
>;
type Tab = "overview" | "applications" | "clinicians";

export function AdministrationScreen({
  api,
  user,
  onSignedOut,
}: {
  api: AdminApi;
  user: User;
  onSignedOut: () => void;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const [status, setStatus] = useState<ApplicationStatus>("pending");
  const [overview, setOverview] = useState<UserOverview | null>(null);
  const [applications, setApplications] = useState<ApplicationsPage>({
    applications: [],
    nextAfter: null,
  });
  const [clinicians, setClinicians] = useState<PatientPage>({
    patients: [],
    nextAfter: null,
  });
  const [after, setAfter] = useState<string | undefined>();
  const [attempt, setAttempt] = useState(0);
  const [foreground, setForeground] = useState(true);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [existingUsername, setExistingUsername] = useState("");
  const beginLoad = useCallback(() => {
    setLoading(true);
    setError(null);
    setOverview(null);
    setApplications({ applications: [], nextAfter: null });
    setClinicians({ patients: [], nextAfter: null });
  }, []);

  useEffect(() => {
    const listener = AppState.addEventListener("change", (state) => {
      setForeground(state === "active");
      beginLoad();
      if (state === "active") setAttempt((n) => n + 1);
    });
    return () => listener.remove();
  }, [beginLoad]);

  useEffect(() => {
    if (!foreground) return;
    const controller = new AbortController();
    void Promise.all([
      api.getAdminOverview(controller.signal),
      tab === "applications"
        ? api.getClinicianApplications(status, after, controller.signal)
        : Promise.resolve(null),
      tab === "clinicians"
        ? api.getClinicians(after, controller.signal)
        : Promise.resolve(null),
    ])
      .then(
        ([counts, requests, doctors]) => {
          if (controller.signal.aborted) return;
          setOverview(counts);
          if (requests) setApplications(requests);
          if (doctors) setClinicians(doctors);
        },
        (reason) => {
          if (!controller.signal.aborted) setError(errorMessage(reason));
        },
      )
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api, tab, status, after, attempt, foreground]);

  async function act(action: () => Promise<string>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      setNotice(await action());
      beginLoad();
      setAfter(undefined);
      setAttempt((n) => n + 1);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  function selectTab(value: Tab) {
    beginLoad();
    setAttempt((n) => n + 1);
    setTab(value);
    setAfter(undefined);
    setNotice(null);
    setError(null);
  }

  const nextAfter =
    tab === "applications" ? applications.nextAfter : clinicians.nextAfter;
  return (
    <SafeAreaView style={m.root}>
      <View style={m.header}>
        <Text accessibilityRole="header" style={m.title}>
          研发管理
        </Text>
        <Button
          title="退出登录"
          disabled={busy}
          onPress={() => {
            void api
              .logout()
              .then(onSignedOut, (reason) => setError(errorMessage(reason)));
          }}
        />
      </View>
      <ScrollView
        contentContainerStyle={m.body}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={m.hint}>
          {user.fullName || user.username} · 开发协作者
        </Text>
        <View style={m.row}>
          {(
            [
              ["overview", "人员总览"],
              ["applications", "医护审批"],
              ["clinicians", "医护账号"],
            ] as const
          ).map(([key, label]) => (
            <Pressable
              key={key}
              accessibilityRole="tab"
              accessibilityLabel={label}
              accessibilityState={{ selected: tab === key, disabled: busy }}
              disabled={busy}
              style={m.button}
              onPress={() => selectTab(key)}
            >
              <Text style={tab === key ? m.activeTab : m.hint}>{label}</Text>
            </Pressable>
          ))}
        </View>
        <Button
          title="刷新管理数据"
          disabled={busy || loading}
          onPress={() => {
            beginLoad();
            setAttempt((n) => n + 1);
          }}
        />
        {loading ? <ActivityIndicator color={colors.primary} /> : null}
        {error ? (
          <Text accessibilityRole="alert" style={m.error}>
            {error}
          </Text>
        ) : null}
        {notice ? (
          <Text accessibilityLiveRegion="polite" style={m.text}>
            {notice}
          </Text>
        ) : null}

        {tab !== "overview" || !overview ? null : (
          <>
            <Text style={m.subtitle}>已注册账号</Text>
            <View style={m.row}>
              {(
                [
                  ["总用户", overview.totalUsers],
                  ["患者", overview.patients],
                  ["医护人员", overview.clinicians],
                  ["开发协作者", overview.collaborators],
                ] as const
              ).map(([label, count]) => (
                <View
                  key={label}
                  style={m.metric}
                  accessibilityLabel={`${label}：${count}`}
                >
                  <Text style={m.hint}>{label}</Text>
                  <Text style={m.number}>{count}</Text>
                </View>
              ))}
            </View>
            <View style={m.card}>
              <Text style={m.subtitle}>身份分布</Text>
              {(
                [
                  ["患者", overview.patients],
                  ["医护人员", overview.clinicians],
                  ["开发协作者", overview.collaborators],
                ] as const
              ).map(([label, count]) => (
                <View key={label} style={{ gap: 6 }}>
                  <Text style={m.text}>
                    {label}：{count} 人
                  </Text>
                  <View style={m.track} accessibilityLabel={`${label}占比图`}>
                    <View
                      style={[
                        m.bar,
                        {
                          width: `${overview.totalUsers ? (count / overview.totalUsers) * 100 : 0}%`,
                        },
                      ]}
                    />
                  </View>
                </View>
              ))}
              <Text style={m.hint}>
                按当前账号身份统计，待审批账号仍计入患者。
              </Text>
            </View>
            <Button
              title={`待审批医护：${overview.pendingApplications} 人`}
              onPress={() => {
                setStatus("pending");
                selectTab("applications");
              }}
            />
          </>
        )}

        {tab !== "applications" ? null : (
          <>
            <View style={m.row}>
              {(
                [
                  ["pending", "待审批"],
                  ["approved", "已通过"],
                  ["rejected", "已拒绝"],
                ] as const
              ).map(([value, label]) => (
                <Pressable
                  key={value}
                  accessibilityRole="tab"
                  accessibilityLabel={label}
                  accessibilityState={{ selected: status === value }}
                  disabled={busy}
                  style={m.button}
                  onPress={() => {
                    beginLoad();
                    setStatus(value);
                    setAfter(undefined);
                    setAttempt((n) => n + 1);
                  }}
                >
                  <Text style={status === value ? m.activeTab : m.hint}>
                    {label}
                  </Text>
                </Pressable>
              ))}
            </View>
            {!loading && !error && applications.applications.length === 0 ? (
              <Text style={m.hint}>当前没有此状态的申请。</Text>
            ) : null}
            {applications.applications.map((application) => (
              <View key={application.id} style={m.card}>
                <Text style={m.subtitle}>{application.fullName}</Text>
                <Text style={m.text}>所属机构：{application.organization}</Text>
                <Text selectable style={m.hint}>
                  账号：{application.applicant.username}
                </Text>
                <Text selectable style={m.hint}>
                  账号 ID：{application.applicant.id}
                </Text>
                <Text style={m.hint}>
                  申请于{" "}
                  {new Date(application.createdAt).toLocaleString("zh-CN")}
                </Text>
                {application.rejectionReason ? (
                  <Text style={m.text}>
                    拒绝原因：{application.rejectionReason}
                  </Text>
                ) : null}
                {application.status !== "pending" ? null : (
                  <>
                    <Button
                      title={`通过 ${application.fullName} 的申请`}
                      disabled={busy}
                      onPress={() =>
                        void act(async () => {
                          await api.reviewClinicianApplication(
                            application.id,
                            "approve",
                          );
                          return `已通过 ${application.fullName} 的医护申请。`;
                        })
                      }
                    />
                    <TextInput
                      accessibilityLabel={`${application.fullName} 的拒绝原因`}
                      style={m.input}
                      placeholder="如需拒绝，请填写原因"
                      maxLength={512}
                      editable={!busy}
                      value={reasons[application.id] ?? ""}
                      onChangeText={(value) =>
                        setReasons((values) => ({
                          ...values,
                          [application.id]: value,
                        }))
                      }
                    />
                    <Button
                      title={`拒绝 ${application.fullName} 的申请`}
                      disabled={busy || !(reasons[application.id] ?? "").trim()}
                      onPress={() =>
                        void act(async () => {
                          await api.reviewClinicianApplication(
                            application.id,
                            "reject",
                            reasons[application.id].trim(),
                          );
                          return `已拒绝 ${application.fullName} 的申请，申请人可查看原因并重新提交。`;
                        })
                      }
                    />
                  </>
                )}
              </View>
            ))}
          </>
        )}

        {tab !== "clinicians" ? null : (
          <>
            <View style={m.card}>
              <Text style={m.subtitle}>创建医护账号</Text>
              <TextInput
                accessibilityLabel="新医护姓名"
                placeholder="姓名"
                style={m.input}
                maxLength={64}
                value={fullName}
                onChangeText={setFullName}
                editable={!busy}
              />
              <TextInput
                accessibilityLabel="新医护用户名"
                placeholder="用户名，至少 3 个字符"
                style={m.input}
                maxLength={32}
                autoCapitalize="none"
                value={username}
                onChangeText={setUsername}
                editable={!busy}
              />
              <TextInput
                accessibilityLabel="新医护密码"
                placeholder="初始密码，至少 8 个字符"
                style={m.input}
                maxLength={128}
                secureTextEntry
                autoCapitalize="none"
                value={password}
                onChangeText={setPassword}
                editable={!busy}
              />
              <Button
                title="创建医护账号"
                disabled={
                  busy ||
                  !fullName.trim() ||
                  username.trim().length < 3 ||
                  password.length < 8
                }
                onPress={() =>
                  void act(async () => {
                    const created = await api.createClinician(
                      username.trim(),
                      password,
                      fullName.trim(),
                    );
                    setUsername("");
                    setPassword("");
                    setFullName("");
                    return `已创建医护账号 ${created.username}，可使用刚设置的密码登录。`;
                  })
                }
              />
            </View>
            <View style={m.card}>
              <Text style={m.subtitle}>添加已有账号为医护</Text>
              <Text style={m.hint}>
                核对完整用户名，添加后该账号将以医护身份使用。
              </Text>
              <TextInput
                accessibilityLabel="已有账号用户名"
                placeholder="完整用户名"
                style={m.input}
                maxLength={32}
                autoCapitalize="none"
                value={existingUsername}
                onChangeText={setExistingUsername}
                editable={!busy}
              />
              <Button
                title="添加为医护"
                disabled={busy || existingUsername.trim().length < 3}
                onPress={() =>
                  void act(async () => {
                    const added = await api.assignClinician(
                      existingUsername.trim(),
                    );
                    setExistingUsername("");
                    return `已将 ${added.username} 添加为医护，重新登录后生效。`;
                  })
                }
              />
            </View>
            <Text style={m.subtitle}>医护人员列表</Text>
            {!loading && !error && clinicians.patients.length === 0 ? (
              <Text style={m.hint}>暂无医护账号。</Text>
            ) : null}
            {clinicians.patients.map((doctor) => (
              <View key={doctor.id} style={m.card}>
                <Text style={m.subtitle}>
                  {doctor.fullName || "未填写姓名"}
                </Text>
                <Text selectable style={m.text}>
                  账号：{doctor.username}
                </Text>
                <Text selectable style={m.hint}>
                  账号 ID：{doctor.id}
                </Text>
              </View>
            ))}
          </>
        )}
        {tab === "overview" ? null : (
          <View style={m.row}>
            {nextAfter === null ? null : (
              <Button
                title="下一页"
                disabled={busy || loading}
                onPress={() => {
                  beginLoad();
                  setAfter(nextAfter);
                }}
              />
            )}
            {!after ? null : (
              <Button
                title="回到第一页"
                disabled={busy || loading}
                onPress={() => {
                  beginLoad();
                  setAfter(undefined);
                }}
              />
            )}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
