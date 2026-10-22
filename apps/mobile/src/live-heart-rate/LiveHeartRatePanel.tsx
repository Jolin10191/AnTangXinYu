import { Dimensions, Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Polyline } from 'react-native-svg';

import { colors, radii, spacing, typefaces } from '../ui/theme';
import { useLiveHeartRateControllerOrNull } from './LiveHeartRateProvider';
import { buildSparklinePoints, toSvgPoints } from './sparkline';
import type { LiveHeartRateController } from './use-live-heart-rate';

const W = Dimensions.get('window').width;
const CARD_INNER_WIDTH = W - spacing.md * 2 - spacing.md * 2;
const SPARKLINE_HEIGHT = 64;

type Badge = { label: string; color: string; background: string };

function badgeOf(live: LiveHeartRateController): Badge {
  switch (live.phase) {
    case 'streaming':
      return { label: '实时', color: colors.primaryPressed, background: colors.primarySoft };
    case 'scanning':
      return { label: '搜索中', color: colors.muted, background: colors.paperMuted };
    case 'connecting':
      return { label: '连接中', color: colors.muted, background: colors.paperMuted };
    case 'error':
      return { label: '未连接', color: colors.danger, background: colors.dangerSoft };
    default:
      return { label: '未连接', color: colors.muted, background: colors.paperMuted };
  }
}

/**
 * 健康看板顶部的实时心率卡片。数据直接来自手环的 BLE 心率广播，
 * 不经过服务器，所以和下面「服务器已保存的近 30 天观测」明确分开。
 *
 * 默认从共享的 LiveHeartRateProvider 取会话，这样在健康看板、对话和健康档案
 * 之间切换不会断开连接；controller 只用于调用方显式注入（例如测试）。
 */
export function LiveHeartRatePanel({ controller }: { controller?: LiveHeartRateController }) {
  const contextController = useLiveHeartRateControllerOrNull();
  const live = controller ?? contextController;
  if (live === null) {
    throw new Error(
      'LiveHeartRatePanel 需要 controller 参数，或者放在 LiveHeartRateProvider 内使用',
    );
  }
  const badge = badgeOf(live);

  if (!live.supported) {
    return (
      <View style={s.card}>
        <View style={s.head}>
          <Text style={s.title}>实时心率</Text>
          <View style={[s.badge, { backgroundColor: colors.paperMuted }]}>
            <Text style={[s.badgeText, { color: colors.muted }]}>不可用</Text>
          </View>
        </View>
        <Text style={s.hint}>当前安装包没有编译进实时心率模块，需要重新生成 Android 构建。</Text>
      </View>
    );
  }

  const values = live.samples.map((sample) => sample.beatsPerMinute);
  const points = buildSparklinePoints(values, CARD_INNER_WIDTH, SPARKLINE_HEIGHT);
  const candidates = [...live.devices].sort((left, right) => right.rssi - left.rssi);

  return (
    <View style={s.card}>
      <View style={s.head}>
        <Text style={s.title}>实时心率</Text>
        <View style={[s.badge, { backgroundColor: badge.background }]}>
          <Text style={[s.badgeText, { color: badge.color }]}>{badge.label}</Text>
        </View>
      </View>

      {live.latest === null ? null : (
        <>
          <View style={s.readingRow}>
            <Text style={s.reading}>{live.latest.beatsPerMinute}</Text>
            <Text style={s.unit}>bpm</Text>
          </View>
          <Text style={s.device}>
            {`${live.deviceName ?? '心率广播设备'} · 直接来自手环蓝牙广播`}
          </Text>
          {points.length < 2 ? null : (
            <Svg height={SPARKLINE_HEIGHT} style={s.chart} width={CARD_INNER_WIDTH}>
              <Polyline
                fill="none"
                points={toSvgPoints(points)}
                stroke={colors.primary}
                strokeLinejoin="round"
                strokeWidth={2}
              />
            </Svg>
          )}
        </>
      )}

      {live.message === null ? null : <Text style={s.message}>{live.message}</Text>}

      {live.phase === 'idle' && live.latest === null ? (
        <Text style={s.hint}>
          请先在华为手环上开启「心率广播」（手环设置 → 心率广播），
          然后点下面的按钮搜索手环。
        </Text>
      ) : null}

      {live.phase === 'scanning' && candidates.length === 0 ? (
        <Text style={s.hint}>正在搜索正在广播心率的手环…请保持手环亮屏并靠近手机。</Text>
      ) : null}

      {live.phase === 'connecting' ? (
        <Text style={s.hint}>正在连接手环并订阅心率通知…</Text>
      ) : null}

      {live.phase === 'scanning' && candidates.length > 0 ? (
        <View style={s.deviceList}>
          {candidates.map((device) => (
            <Pressable
              accessibilityLabel={`连接${device.name ?? device.address}`}
              accessibilityRole="button"
              disabled={live.busy}
              key={device.address}
              onPress={() => live.connect(device.address)}
              style={({ pressed }) => [s.deviceRow, pressed && s.pressed]}
            >
              <Text style={s.deviceName}>{device.name ?? device.address}</Text>
              <Text style={s.deviceAction}>连接</Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      <View style={s.actions}>
        {live.phase === 'idle' ? (
          <ActionButton
            disabled={live.busy}
            label="开始实时监测"
            onPress={live.startScan}
            tone="primary"
          />
        ) : null}
        {live.phase === 'scanning' ? (
          <ActionButton disabled={live.busy} label="停止搜索" onPress={live.stopScan} tone="ghost" />
        ) : null}
        {live.phase === 'connecting' || live.phase === 'streaming' ? (
          <ActionButton disabled={live.busy} label="停止监测" onPress={live.disconnect} tone="ghost" />
        ) : null}
        {live.phase === 'error' ? (
          <ActionButton disabled={live.busy} label="重新搜索" onPress={live.startScan} tone="primary" />
        ) : null}
      </View>
    </View>
  );
}

function ActionButton({
  label,
  onPress,
  disabled,
  tone,
}: {
  label: string;
  onPress: () => void;
  disabled: boolean;
  tone: 'primary' | 'ghost';
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        s.button,
        tone === 'primary' ? s.buttonPrimary : s.buttonGhost,
        pressed && s.pressed,
        disabled && s.buttonDisabled,
      ]}
    >
      <Text style={tone === 'primary' ? s.buttonPrimaryText : s.buttonGhostText}>{label}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  card: {
    backgroundColor: colors.paper,
    borderRadius: radii.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { color: colors.ink, fontFamily: typefaces.sansMedium, fontSize: 15 },
  badge: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: radii.pill },
  badgeText: { fontFamily: typefaces.sansMedium, fontSize: 11 },
  readingRow: { flexDirection: 'row', alignItems: 'flex-end', marginTop: spacing.sm },
  reading: { color: colors.ink, fontFamily: typefaces.sansMedium, fontSize: 44, lineHeight: 48 },
  unit: { color: colors.muted, fontFamily: typefaces.sans, fontSize: 13, marginLeft: 6, marginBottom: 6 },
  device: { color: colors.muted, fontFamily: typefaces.sans, fontSize: 11, marginTop: 2 },
  chart: { marginTop: spacing.sm, borderRadius: radii.sm },
  message: { color: colors.danger, fontFamily: typefaces.sans, fontSize: 12, lineHeight: 19, marginTop: spacing.sm },
  hint: { color: colors.muted, fontFamily: typefaces.sans, fontSize: 12, lineHeight: 20, marginTop: spacing.sm },
  deviceList: { marginTop: spacing.sm, gap: spacing.xs },
  deviceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.paperMuted,
    borderRadius: radii.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
  },
  deviceName: { color: colors.text, fontFamily: typefaces.sans, fontSize: 13, flex: 1 },
  deviceAction: { color: colors.primaryPressed, fontFamily: typefaces.sansMedium, fontSize: 13 },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  button: { flex: 1, alignItems: 'center', justifyContent: 'center', borderRadius: radii.pill, paddingVertical: 11 },
  buttonPrimary: { backgroundColor: colors.primary },
  buttonGhost: { backgroundColor: colors.paperMuted },
  buttonDisabled: { opacity: 0.5 },
  buttonPrimaryText: { color: colors.white, fontFamily: typefaces.sansMedium, fontSize: 14 },
  buttonGhostText: { color: colors.muted, fontFamily: typefaces.sansMedium, fontSize: 14 },
  pressed: { opacity: 0.7 },
});
