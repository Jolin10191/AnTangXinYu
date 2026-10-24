import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";

import type { ApiClient } from "../api/client";
import { errorMessage } from "../api/client";
import type {
  CgmImportPreview,
  CgmSourceSystem,
} from "../api/types";

const SOURCES: { value: CgmSourceSystem; label: string }[] = [
  { value: "sibionics", label: "硅基" },
  { value: "nightscout", label: "Nightscout" },
  { value: "libre", label: "雅培" },
  { value: "dexcom", label: "德康" },
  { value: "generic", label: "其他" },
];

type Props = {
  api: Pick<ApiClient, "previewGlucoseImport" | "importGlucoseCsv">;
  onBack: () => void;
  onImported: (insertedCount: number) => void;
};

/**
 * 传感器数据导入：先预览再入库。
 *
 * 厂家 App 导出的 CSV 常有单位混用、重复行、缺时区，所以不直接写库：
 * 先把「能用多少行、哪几行有问题、问题是什么」给患者看，确认后才存。
 */
export function GlucoseImportScreen({ api, onBack, onImported }: Props) {
  const [source, setSource] = useState<CgmSourceSystem>("sibionics");
  const [preview, setPreview] = useState<CgmImportPreview | null>(null);
  const [pending, setPending] = useState<{
    mimeType: string;
    name: string;
    uri: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pick() {
    setError(null);
    setPreview(null);
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ["text/csv", "text/comma-separated-values", "text/plain", "*/*"],
        copyToCacheDirectory: true,
      });
      if (result.canceled || result.assets.length === 0) {
        return;
      }
      const asset = result.assets[0];
      const file = {
        mimeType: asset.mimeType ?? "text/csv",
        name: asset.name,
        uri: asset.uri,
      };
      setPending(file);
      setBusy(true);
      setPreview(await api.previewGlucoseImport(file, source));
    } catch (cause) {
      setError(errorMessage(cause));
      setPending(null);
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (pending === null) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.importGlucoseCsv(pending, source);
      onImported(result.insertedCount);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="返回记录"
          onPress={onBack}
          style={styles.back}
        >
          <Text style={styles.backText}>返回</Text>
        </Pressable>
        <Text style={styles.title}>导入传感器数据</Text>
      </View>

      <Text style={styles.lead}>
        从厂家 App 导出 CSV，先核对能用的行与可疑行，确认后才存进档案。只支持 CSV，单次不超过 5 MB。
      </Text>

      <Text style={styles.label}>数据来自</Text>
      <View style={styles.chipRow}>
        {SOURCES.map((option) => {
          const active = option.value === source;
          return (
            <Pressable
              key={option.value}
              accessibilityRole="button"
              accessibilityLabel={`数据来自${option.label}`}
              accessibilityState={{ selected: active }}
              onPress={() => setSource(option.value)}
              style={[styles.chip, active ? styles.chipActive : null]}
            >
              <Text style={[styles.chipText, active ? styles.chipTextActive : null]}>
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="选择导出的 CSV 文件"
        onPress={() => void pick()}
        disabled={busy}
        style={[styles.primary, busy ? styles.disabled : null]}
      >
        <Text style={styles.primaryText}>
          {preview === null ? "选择文件" : "换一个文件"}
        </Text>
      </Pressable>

      {busy ? <ActivityIndicator style={styles.spinner} /> : null}
      {error === null ? null : <Text style={styles.error}>{error}</Text>}

      {preview === null ? null : (
        <>
          <View style={styles.card}>
            <Text style={styles.cardTitle}>核对一下</Text>
            <Text style={styles.cardBody}>{preview.fileName}</Text>
            <View style={styles.statRow}>
              <View style={styles.stat}>
                <Text style={styles.statLabel}>能导入</Text>
                <Text style={styles.statValue}>{preview.usableRows} 行</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statLabel}>跳过</Text>
                <Text style={styles.statValue}>{preview.problems.length} 行</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statLabel}>单位</Text>
                <Text style={styles.statValue}>
                  {preview.unit === "mmol/L" ? "mmol/L" : "mg/dL"}
                </Text>
              </View>
            </View>
          </View>

          {preview.problems.length === 0 ? null : (
            <View style={styles.warnCard}>
              <Text style={styles.warnTitle}>这几行没导入</Text>
              {preview.problems.map((problem) => (
                <Text key={problem} style={styles.warnLine}>
                  · {problem}
                </Text>
              ))}
            </View>
          )}

          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`确认导入 ${preview.usableRows} 行`}
            onPress={() => void confirm()}
            disabled={busy || preview.usableRows === 0}
            style={[
              styles.primary,
              busy || preview.usableRows === 0 ? styles.disabled : null,
            ]}
          >
            <Text style={styles.primaryText}>
              确认导入 {preview.usableRows} 行
            </Text>
          </Pressable>
          <Text style={styles.hint}>
            同一份文件再导一次不会重复记录。手输的血糖和传感器数值分开存，同一时刻以手输为准。
          </Text>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, gap: 12, paddingBottom: 40 },
  header: { flexDirection: "row", alignItems: "center", gap: 12 },
  back: { paddingVertical: 6, paddingRight: 6 },
  backText: { fontSize: 14, color: "#20B894" },
  title: { fontSize: 20, fontWeight: "700", color: "#17302E" },
  lead: { fontSize: 13, lineHeight: 20, color: "#667875" },
  label: { fontSize: 12, color: "#667875", marginTop: 4 },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "#EDF5F3",
  },
  chipActive: { backgroundColor: "#20B894" },
  chipText: { fontSize: 13, color: "#17302E" },
  chipTextActive: { color: "#FFFFFF", fontWeight: "600" },
  primary: {
    backgroundColor: "#20B894",
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
  },
  disabled: { opacity: 0.45 },
  primaryText: { color: "#FFFFFF", fontSize: 15, fontWeight: "600" },
  spinner: { marginTop: 4 },
  error: { color: "#DE665B", fontSize: 13 },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "#E4ECEA",
    padding: 16,
    gap: 6,
  },
  cardTitle: { fontSize: 15, fontWeight: "600", color: "#17302E" },
  cardBody: { fontSize: 12.5, color: "#667875" },
  statRow: { flexDirection: "row", gap: 12, marginTop: 6 },
  stat: { flex: 1, gap: 2 },
  statLabel: { fontSize: 11.5, color: "#91A19E" },
  statValue: { fontSize: 16, fontWeight: "600", color: "#17302E" },
  warnCard: {
    backgroundColor: "#FBF4E8",
    borderRadius: 16,
    padding: 14,
    gap: 4,
  },
  warnTitle: { fontSize: 13, fontWeight: "600", color: "#8A5A12" },
  warnLine: { fontSize: 12, lineHeight: 18, color: "#8A5A12" },
  hint: { fontSize: 11.5, lineHeight: 17, color: "#91A19E" },
});
