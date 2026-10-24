import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radii, spacing, typefaces } from "../ui/theme";

export type AppTabKey = "chat" | "records" | "profile";

export const APP_TABS: { key: AppTabKey; label: string }[] = [
  { key: "chat", label: "对话" },
  { key: "records", label: "记录" },
  { key: "profile", label: "我的" },
];

type Props = {
  active: AppTabKey;
  onChange: (key: AppTabKey) => void;
};

/**
 * 底部三个 tab。抽屉式菜单与它在功能上重复（都指向 对话/记录/我的），
 * 所以这一版把抽屉去掉，只留一条固定的底部导航。
 */
export function AppTabBar({ active, onChange }: Props) {
  return (
    <View style={styles.bar} accessibilityRole="tablist">
      {APP_TABS.map((tab) => {
        const selected = tab.key === active;
        return (
          <Pressable
            key={tab.key}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            accessibilityLabel={`${tab.label}标签页`}
            onPress={() => onChange(tab.key)}
            style={styles.item}
          >
            <View style={[styles.dot, selected ? styles.dotActive : null]} />
            <Text style={[styles.label, selected ? styles.labelActive : null]}>
              {tab.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
    backgroundColor: colors.paper,
    paddingTop: spacing.xs,
    paddingBottom: spacing.sm,
  },
  item: {
    flex: 1,
    alignItems: "center",
    gap: 3,
    paddingVertical: spacing.xs,
  },
  dot: {
    width: 18,
    height: 3,
    borderRadius: radii.pill,
    backgroundColor: "transparent",
  },
  dotActive: {
    backgroundColor: colors.primary,
  },
  label: {
    color: colors.faint,
    fontFamily: typefaces.sans,
    fontSize: 12,
  },
  labelActive: {
    color: colors.primaryPressed,
    fontFamily: typefaces.sansMedium,
    fontWeight: "600",
  },
});
