import { createContext, useContext, type ReactNode } from 'react';

import { useLiveHeartRate, type LiveHeartRateController } from './use-live-heart-rate';

/**
 * 实时心率会话挂在聊天页根组件上：健康看板、对话和健康档案共用同一次 BLE 连接。
 * 只要 Provider 还挂载着，切换页面就不会断开；断开只由用户点「停止监测」，
 * 或者 App 退出、进入后台决定。
 */
const LiveHeartRateContext = createContext<LiveHeartRateController | null>(null);

export function LiveHeartRateProvider({
  active,
  children,
}: {
  active: boolean;
  children: ReactNode;
}) {
  const controller = useLiveHeartRate(active);
  return (
    <LiveHeartRateContext.Provider value={controller}>
      {children}
    </LiveHeartRateContext.Provider>
  );
}

export function useLiveHeartRateController(): LiveHeartRateController {
  const controller = useContext(LiveHeartRateContext);
  if (controller === null) {
    throw new Error('useLiveHeartRateController 必须在 LiveHeartRateProvider 内使用');
  }
  return controller;
}

/**
 * 面板允许调用方直接注入 controller，所以需要一个不抛错的读取入口：
 * 没有 Provider 时返回 null，由调用方自己决定怎么处理。
 */
export function useLiveHeartRateControllerOrNull(): LiveHeartRateController | null {
  return useContext(LiveHeartRateContext);
}
