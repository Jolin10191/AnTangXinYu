import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { errorMessage } from '../api/client';
import type { ApiClient } from '../api/client';
import { colors, radii, spacing, typefaces } from '../ui/theme';

type Props = {
  api: ApiClient;
  onCancel: () => void;
  onDeleted: () => void;
};

/**
 * 注销账号。
 *
 * 删除动作和「关怀设置」里那一块用的是同一个 `DELETE /auth/account`；这里只是
 * 把入口从关怀设置里独立出来，免得患者点了「注销账号」却跳进关怀设置。
 */
export function DeleteAccountScreen({ api, onCancel, onDeleted }: Props) {
  const [password, setPassword] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    if (running || password.length === 0) return;
    setRunning(true);
    setError(null);
    try {
      await api.deleteAccount(password);
      setPassword('');
      onDeleted();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setRunning(false);
    }
  }

  return (
    <View style={styles.screen}>
      <View style={styles.navbar}>
        <Pressable
          accessibilityLabel="返回"
          accessibilityRole="button"
          onPress={onCancel}
          style={styles.back}
        >
          <Text style={styles.backText}>‹</Text>
        </Pressable>
        <Text style={styles.navTitle}>注销账号</Text>
        <View style={styles.back} />
      </View>

      <ScrollView contentContainerStyle={styles.body}>
        <Text style={styles.groupTitle}>这会删掉什么</Text>
        <View style={styles.group}>
          <Text style={styles.explain}>
            健康档案、全部对话、血糖与手环记录、行为与念头记录、陪伴记忆，一起删除，无法恢复。
          </Text>
        </View>

        <Text style={styles.groupTitle}>确认身份</Text>
        <View style={styles.group}>
          <TextInput
            accessibilityLabel="注销账号时输入登录密码"
            onChangeText={setPassword}
            placeholder="输入登录密码"
            placeholderTextColor={colors.faint}
            secureTextEntry
            style={styles.input}
            value={password}
          />
        </View>

        {error === null ? null : <Text style={styles.error}>{error}</Text>}

        <Pressable
          accessibilityLabel="永久删除这个账号"
          accessibilityRole="button"
          disabled={running || password.length === 0}
          onPress={() => void remove()}
          style={({ pressed }) => [
            styles.dangerButton,
            (running || password.length === 0) && styles.disabled,
            pressed && styles.pressed,
          ]}
        >
          {running ? (
            <ActivityIndicator color={colors.paper} size="small" />
          ) : (
            <Text style={styles.dangerText}>永久删除这个账号</Text>
          )}
        </Pressable>

        <Pressable
          accessibilityLabel="先不删"
          accessibilityRole="button"
          onPress={onCancel}
          style={styles.ghost}
        >
          <Text style={styles.ghostText}>先不删</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  navbar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
    backgroundColor: colors.paper,
  },
  back: { width: 24 },
  backText: { color: colors.ink, fontSize: 22, lineHeight: 26 },
  navTitle: {
    flex: 1,
    textAlign: 'center',
    color: colors.ink,
    fontFamily: typefaces.sansMedium,
    fontSize: 16,
  },
  body: { paddingBottom: spacing.xxl },
  groupTitle: {
    color: colors.faint,
    fontFamily: typefaces.sans,
    fontSize: 11,
    marginTop: spacing.md,
    marginBottom: spacing.xs,
    marginHorizontal: spacing.lg,
  },
  group: {
    backgroundColor: colors.paper,
    borderRadius: radii.md,
    marginHorizontal: spacing.sm,
    padding: spacing.sm,
  },
  explain: {
    color: colors.text,
    fontFamily: typefaces.sans,
    fontSize: 12,
    lineHeight: 20,
  },
  input: {
    borderColor: colors.line,
    borderRadius: radii.sm,
    borderWidth: 1,
    color: colors.ink,
    fontFamily: typefaces.sans,
    fontSize: 13,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  error: {
    color: colors.danger,
    fontFamily: typefaces.sans,
    fontSize: 12,
    lineHeight: 18,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
  },
  dangerButton: {
    alignItems: 'center',
    backgroundColor: colors.danger,
    borderRadius: radii.pill,
    marginHorizontal: spacing.sm,
    marginTop: spacing.lg,
    paddingVertical: spacing.sm,
  },
  disabled: { opacity: 0.5 },
  pressed: { opacity: 0.85 },
  dangerText: {
    color: colors.paper,
    fontFamily: typefaces.sansMedium,
    fontSize: 14,
  },
  ghost: { alignItems: 'center', paddingVertical: spacing.sm },
  ghostText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 13,
  },
});
