import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  AppState,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { errorMessage, type ApiClient } from "../api/client";
import type { ClinicianApplication, User } from "../api/types";
import { colors } from "../ui/theme";
import { ManagementButton as Button, m } from "./management-ui";

type ApplicationApi = Pick<
  ApiClient,
  "me" | "getOwnClinicianApplication" | "submitClinicianApplication" | "logout"
>;

export function ClinicianApplicationScreen({
  api,
  onUserUpdated,
  onSignedOut,
}: {
  api: ApplicationApi;
  onUserUpdated: (user: User) => void;
  onSignedOut: () => void;
}) {
  const [application, setApplication] = useState<ClinicianApplication | null>(
    null,
  );
  const [fullName, setFullName] = useState("");
  const [organization, setOrganization] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const listener = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        setLoading(true);
        setError(null);
        setAttempt((value) => value + 1);
      }
    });
    return () => listener.remove();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      api.me(controller.signal),
      api.getOwnClinicianApplication(controller.signal),
    ])
      .then(
        ([current, request]) => {
          if (controller.signal.aborted) return;
          if (
            current.role !== "patient" ||
            current.applicationStatus === null
          ) {
            onUserUpdated(current);
            return;
          }
          setApplication(request);
          setFullName(request?.fullName ?? current.fullName ?? "");
          setOrganization(request?.organization ?? "");
        },
        (reason) => {
          if (!controller.signal.aborted) setError(errorMessage(reason));
        },
      )
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api, attempt, onUserUpdated]);

  async function resubmit() {
    setBusy(true);
    setError(null);
    try {
      await api.submitClinicianApplication(
        fullName.trim(),
        organization.trim(),
      );
      setLoading(true);
      setAttempt((value) => value + 1);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <SafeAreaView style={m.root}>
      <View style={m.header}>
        <Text style={m.title}>医护申请</Text>
        <Button
          title="退出登录"
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
        {loading ? <ActivityIndicator color={colors.primary} /> : null}
        {error ? (
          <Text accessibilityRole="alert" style={m.error}>
            {error}
          </Text>
        ) : null}
        {!application || loading ? null : (
          <View style={m.card}>
            <Text style={m.subtitle}>
              {application.status === "pending"
                ? "医护申请待审批"
                : application.status === "rejected"
                  ? "医护申请未通过"
                  : "医护申请已通过"}
            </Text>
            <Text style={m.text}>姓名：{application.fullName}</Text>
            <Text style={m.text}>所属机构：{application.organization}</Text>
            {application.status === "pending" ? (
              <Text style={m.hint}>
                开发协作者审批通过后，你可以进入医护界面。查看患者资料还需要患者单独授权。
              </Text>
            ) : null}
            {application.rejectionReason ? (
              <Text style={m.error}>
                拒绝原因：{application.rejectionReason}
              </Text>
            ) : null}
            {application.status !== "rejected" ? null : (
              <>
                <TextInput
                  accessibilityLabel="重新申请姓名"
                  style={m.input}
                  value={fullName}
                  onChangeText={setFullName}
                  maxLength={64}
                />
                <TextInput
                  accessibilityLabel="重新申请所属机构"
                  style={m.input}
                  value={organization}
                  onChangeText={setOrganization}
                  maxLength={128}
                />
                <Button
                  title="重新提交医护申请"
                  disabled={busy || !fullName.trim() || !organization.trim()}
                  onPress={() => void resubmit()}
                />
              </>
            )}
          </View>
        )}
        <Button
          title="刷新审批状态"
          disabled={loading || busy}
          onPress={() => {
            setLoading(true);
            setError(null);
            setAttempt((value) => value + 1);
          }}
        />
      </ScrollView>
    </SafeAreaView>
  );
}
