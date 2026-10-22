import { useCallback, useEffect, useMemo, useState } from 'react';
import { AppState, PermissionsAndroid, Platform } from 'react-native';

import {
  addLiveHeartRateListener,
  connectLiveHeartRateDevice,
  disconnectLiveHeartRate,
  isLiveHeartRateAvailable,
  startLiveHeartRateScan,
  stopLiveHeartRateScan,
  type LiveHeartRateDevice,
  type LiveHeartRatePhase,
  type LiveHeartRateSample,
} from '../../modules/live-heart-rate';

/** 面板上保留的最新样本条数：手环通常每秒一帧，180 条约等于最近 3 分钟。 */
export const LIVE_SAMPLE_LIMIT = 180;

export type LiveHeartRateController = {
  /** 当前安装包是否带实时心率原生模块。 */
  supported: boolean;
  phase: LiveHeartRatePhase;
  devices: LiveHeartRateDevice[];
  samples: LiveHeartRateSample[];
  latest: LiveHeartRateSample | null;
  deviceName: string | null;
  message: string | null;
  busy: boolean;
  startScan: () => void;
  stopScan: () => void;
  connect: (address: string) => void;
  disconnect: () => void;
};

function describeError(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

/**
 * Android 12 起扫描 BLE 需要「附近的设备」权限，11 及以下则强制要求位置权限。
 * 权限在 JS 侧申请，原生模块只做一次兜底校验。
 */
async function requestBluetoothPermissions(): Promise<void> {
  if (Platform.OS !== 'android') {
    throw new Error('实时心率监测目前只在 Android 上可用。');
  }
  const apiLevel = typeof Platform.Version === 'number'
    ? Platform.Version
    : Number.parseInt(String(Platform.Version), 10);
  const permissions = apiLevel >= 31
    ? [
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
    ]
    : [PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION];
  const granted = await PermissionsAndroid.requestMultiple(permissions);
  const missing = permissions.filter(
    (permission) => granted[permission] !== PermissionsAndroid.RESULTS.GRANTED,
  );
  if (missing.length > 0) {
    throw new Error('读取实时心率需要「附近的设备」权限，请在系统设置里允许后重试。');
  }
}

export function useLiveHeartRate(active: boolean): LiveHeartRateController {
  const supported = useMemo(() => isLiveHeartRateAvailable(), []);
  const [phase, setPhase] = useState<LiveHeartRatePhase>('idle');
  const [devices, setDevices] = useState<LiveHeartRateDevice[]>([]);
  const [samples, setSamples] = useState<LiveHeartRateSample[]>([]);
  const [deviceName, setDeviceName] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!supported) return undefined;
    const subscriptions = [
      addLiveHeartRateListener('onDevice', (device) => {
        setDevices((current) => current.some((item) => item.address === device.address)
          ? current.map((item) => (item.address === device.address ? device : item))
          : [...current, device]);
      }),
      addLiveHeartRateListener('onSample', (sample) => {
        setSamples((current) => [...current, sample].slice(-LIVE_SAMPLE_LIMIT));
        setDeviceName(sample.name);
        setMessage(null);
        setPhase('streaming');
      }),
      addLiveHeartRateListener('onStatus', (status) => {
        setPhase(status.phase);
        setMessage(status.message);
        if (status.name !== null) setDeviceName(status.name);
        if (status.phase === 'idle' || status.phase === 'error') setDevices([]);
      }),
    ];
    return () => {
      for (const subscription of subscriptions) subscription.remove();
      // 退出账号会卸载 Provider；原生模块仍存在，必须结束本次 BLE 会话。
      void disconnectLiveHeartRate().catch((reason: unknown) => {
        console.warn('结束实时心率连接失败', describeError(reason));
      });
    };
  }, [supported]);

  // 面板关闭时立刻断开，避免手环在后台一直连着耗电。
  // 断开后的界面状态由原生模块发出的 idle 事件统一收敛，这里不直接改 state。
  useEffect(() => {
    if (active || !supported) return undefined;
    // 断开是尽力而为的收尾动作；此时面板已不可见，失败信息留到下次打开时展示。
    void disconnectLiveHeartRate().catch((reason: unknown) => {
      setMessage(describeError(reason));
    });
    return undefined;
  }, [active, supported]);

  useEffect(() => {
    if (!supported) return undefined;
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') return;
      // 后台不继续收集；回到前台由用户重新开始，避免把旧样本当实时值。
      setSamples([]);
      void disconnectLiveHeartRate().catch((reason: unknown) => {
        setMessage(describeError(reason));
        setPhase('error');
      });
    });
    return () => subscription.remove();
  }, [supported]);

  const startScan = useCallback(() => {
    setBusy(true);
    setMessage(null);
    setDevices([]);
    void (async () => {
      try {
        await requestBluetoothPermissions();
        await startLiveHeartRateScan();
      } catch (reason) {
        setMessage(describeError(reason));
        setPhase('error');
      } finally {
        setBusy(false);
      }
    })();
  }, []);

  const stopScan = useCallback(() => {
    setBusy(true);
    void stopLiveHeartRateScan()
      .catch((reason: unknown) => setMessage(describeError(reason)))
      .finally(() => setBusy(false));
  }, []);

  const connect = useCallback((address: string) => {
    setBusy(true);
    setMessage(null);
    setSamples([]);
    void connectLiveHeartRateDevice(address)
      .catch((reason: unknown) => {
        setMessage(describeError(reason));
        setPhase('error');
      })
      .finally(() => setBusy(false));
  }, []);

  const disconnect = useCallback(() => {
    setBusy(true);
    setMessage(null);
    void disconnectLiveHeartRate()
      .catch((reason: unknown) => setMessage(describeError(reason)))
      .finally(() => {
        setPhase('idle');
        setDevices([]);
        setDeviceName(null);
        setSamples([]);
        setBusy(false);
      });
  }, []);

  return {
    supported,
    phase,
    devices,
    samples,
    latest: samples.length === 0 ? null : samples[samples.length - 1],
    deviceName,
    message,
    busy,
    startScan,
    stopScan,
    connect,
    disconnect,
  };
}
