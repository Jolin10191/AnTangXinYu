import { NativeModule, requireOptionalNativeModule } from 'expo';
import { Platform } from 'react-native';

/**
 * 实时心率走的是标准 BLE 心率服务：手环开启「心率广播」后作为外设广播，
 * 本应用作为中心设备接收。这些类型与原生模块 `live-heart-rate` 的字段一一对应。
 */
export type LiveHeartRateDevice = {
  address: string;
  name: string | null;
  rssi: number;
};

export type LiveHeartRateSample = {
  address: string | null;
  name: string | null;
  /** 手环上报的瞬时心率。 */
  beatsPerMinute: number;
  /** 手机收到这一帧的时刻（epoch 毫秒）。 */
  measuredAt: number;
  /** 相邻心跳间隔，多数手环会一并给出。 */
  rrIntervals: number[];
};

export type LiveHeartRatePhase = 'idle' | 'scanning' | 'connecting' | 'streaming' | 'error';

export type LiveHeartRateStatus = {
  phase: LiveHeartRatePhase;
  address: string | null;
  name: string | null;
  message: string | null;
};

type LiveHeartRateEvents = {
  onDevice: (device: LiveHeartRateDevice) => void;
  onSample: (sample: LiveHeartRateSample) => void;
  onStatus: (status: LiveHeartRateStatus) => void;
};

declare class LiveHeartRateNativeModule extends NativeModule<LiveHeartRateEvents> {
  isAvailable(): boolean;
  startScan(): Promise<void>;
  stopScan(): Promise<void>;
  connect(address: string): Promise<void>;
  disconnect(): Promise<void>;
}

const nativeModule = requireOptionalNativeModule<LiveHeartRateNativeModule>('LiveHeartRate');

function requireModule(): LiveHeartRateNativeModule {
  if (Platform.OS !== 'android') {
    throw new Error('实时心率监测目前只在 Android 上可用。');
  }
  if (nativeModule === null) {
    throw new Error('当前安装包没有编译进实时心率模块，请重新生成 Android 构建。');
  }
  return nativeModule;
}

export function isLiveHeartRateAvailable(): boolean {
  if (Platform.OS !== 'android' || nativeModule === null) return false;
  return nativeModule.isAvailable();
}

export function startLiveHeartRateScan(): Promise<void> {
  return requireModule().startScan();
}

export function stopLiveHeartRateScan(): Promise<void> {
  return requireModule().stopScan();
}

export function connectLiveHeartRateDevice(address: string): Promise<void> {
  return requireModule().connect(address);
}

export function disconnectLiveHeartRate(): Promise<void> {
  return requireModule().disconnect();
}

export function addLiveHeartRateListener<EventName extends keyof LiveHeartRateEvents>(
  event: EventName,
  listener: LiveHeartRateEvents[EventName],
): { remove: () => void } {
  return requireModule().addListener(event, listener);
}
