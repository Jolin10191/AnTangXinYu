import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, radii, spacing, typefaces } from "../ui/theme";

type Row = {
  label: string;
  hint?: string;
  onPress: () => void;
  tone?: "normal" | "danger";
};

type Props = {
  name: string;
  status?: string;
  onOpenHealthProfile: () => void;
  onOpenHealthDashboard: () => void;
  onOpenPsychosocial: () => void;
  onOpenPatientAccess: () => void;
  onOpenFearRecords: () => void;
  onOpenHistory: () => void;
  onOpenDevices: () => void;
  onOpenPrivacy: () => void;
  onOpenSettings: () => void;
};

function Group({ rows }: { rows: Row[] }) {
  return (
    <View style={styles.group}>
      {rows.map((row, index) => (
        <Pressable
          key={row.label}
          accessibilityRole="button"
          accessibilityLabel={row.label}
          onPress={row.onPress}
          style={[styles.row, index === rows.length - 1 ? styles.rowLast : null]}
        >
          <Text style={[styles.rowLabel, row.tone === "danger" ? styles.rowDanger : null]}>
            {row.label}
          </Text>
          <Text style={styles.rowHint}>{row.hint ?? "›"}</Text>
        </Pressable>
      ))}
    </View>
  );
}

/**
 * 「我的」页：低频但重要的入口集中在这里，避免每条都占侧边栏。
 * 健康档案与健康看板沿用原有页面，只换入口。
 */
export function ProfileScreen(props: Props) {
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.body}>
      <View style={styles.card}>
        <Text style={styles.name}>{props.name}</Text>
        <Text style={styles.status}>{props.status ?? "安糖心语账号"}</Text>
      </View>

      <Group
        rows={[
          { label: "健康档案", onPress: props.onOpenHealthProfile },
          { label: "健康看板", hint: "30 天手环记录 ›", onPress: props.onOpenHealthDashboard },
          { label: "沟通方式自评", hint: "上次填写 ›", onPress: props.onOpenPsychosocial },
          { label: "医护授权", hint: "只读 · 可撤销 ›", onPress: props.onOpenPatientAccess },
        ]}
      />

      <Group
        rows={[
          { label: "我的记录与撤回", onPress: props.onOpenFearRecords },
          { label: "历史对话", onPress: props.onOpenHistory },
          { label: "设备与数据源", hint: "手环 · Health Connect ›", onPress: props.onOpenDevices },
        ]}
      />

      <Group
        rows={[
          { label: "隐私与数据", onPress: props.onOpenPrivacy },
          { label: "设置与更新", hint: "1.0.0 ›", onPress: props.onOpenSettings },
        ]}
      />

      <Text style={styles.footnote}>
        注销账号在「设置与更新 › 账号」里，需要输入密码，删除后无法恢复。
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  body: {
    padding: spacing.md,
    gap: spacing.sm,
  },
  card: {
    backgroundColor: colors.paper,
    borderRadius: radii.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    padding: spacing.md,
    gap: 3,
  },
  name: {
    color: colors.ink,
    fontFamily: typefaces.sansMedium,
    fontSize: 18,
    fontWeight: "700",
  },
  status: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 12.5,
  },
  group: {
    backgroundColor: colors.paper,
    borderRadius: radii.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    paddingHorizontal: spacing.md,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  rowLast: {
    borderBottomWidth: 0,
  },
  rowLabel: {
    color: colors.ink,
    fontFamily: typefaces.sans,
    fontSize: 14,
  },
  rowDanger: {
    color: colors.danger,
  },
  rowHint: {
    color: colors.faint,
    fontFamily: typefaces.sans,
    fontSize: 12,
  },
  footnote: {
    color: colors.faint,
    fontFamily: typefaces.sans,
    fontSize: 11.5,
    lineHeight: 18,
    paddingHorizontal: spacing.xs,
  },
});
