import { Pressable, StyleSheet, Text } from "react-native";
import { colors, radii, spacing } from "../ui/theme";

export function ManagementButton({
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
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={[m.button, disabled && m.disabled]}
    >
      <Text style={m.buttonText}>{title}</Text>
    </Pressable>
  );
}

export const m = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: spacing.md,
    gap: spacing.sm,
  },
  body: { padding: spacing.md, paddingBottom: spacing.xxxl, gap: spacing.md },
  title: { fontSize: 24, fontWeight: "700", color: colors.ink },
  subtitle: { fontSize: 18, fontWeight: "600", color: colors.ink },
  text: { color: colors.text, fontSize: 15, lineHeight: 23 },
  hint: { color: colors.muted, fontSize: 14, lineHeight: 22 },
  error: { color: colors.danger, fontSize: 14, lineHeight: 22 },
  card: {
    padding: spacing.md,
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radii.md,
    backgroundColor: colors.paper,
  },
  row: {
    flexDirection: "row",
    gap: spacing.sm,
    flexWrap: "wrap",
    alignItems: "center",
  },
  button: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
    backgroundColor: colors.primarySoft,
    alignSelf: "flex-start",
  },
  buttonText: { color: colors.primaryPressed, fontWeight: "600", fontSize: 14 },
  disabled: { opacity: 0.45 },
  input: {
    padding: spacing.sm,
    borderWidth: 1,
    borderRadius: radii.sm,
    borderColor: colors.line,
    color: colors.ink,
    fontSize: 16,
    minHeight: 46,
  },
  activeTab: { color: colors.primaryPressed, fontWeight: "700", fontSize: 16 },
  metric: {
    minWidth: "45%",
    flexGrow: 1,
    padding: spacing.md,
    gap: spacing.xs,
    borderRadius: radii.md,
    backgroundColor: colors.paper,
    borderWidth: 1,
    borderColor: colors.line,
  },
  number: { fontSize: 30, fontWeight: "700", color: colors.ink },
  track: {
    height: 12,
    backgroundColor: colors.primarySoft,
    borderRadius: radii.pill,
    overflow: "hidden",
  },
  bar: {
    height: 12,
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
  },
});
