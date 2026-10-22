import { act, create, type ReactTestRenderer } from 'react-test-renderer';

import { LiveHeartRatePanel } from './LiveHeartRatePanel';
import type { LiveHeartRateController } from './use-live-heart-rate';

jest.mock('react-native-svg', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { __esModule: true, default: View, Polyline: View };
});

/** 面板从 prop 或共享 Provider 取 controller，测试直接注入一个假的。 */
function fakeController(
  overrides: Partial<LiveHeartRateController> = {},
): LiveHeartRateController {
  return {
    supported: true,
    phase: 'idle',
    devices: [],
    samples: [],
    latest: null,
    deviceName: null,
    message: null,
    busy: false,
    startScan: jest.fn(),
    stopScan: jest.fn(),
    connect: jest.fn(),
    disconnect: jest.fn(),
    ...overrides,
  };
}

function sample(beatsPerMinute: number) {
  return {
    address: '80:CC:12:D7:65:98',
    name: 'HUAWEI Band 9-598',
    beatsPerMinute,
    measuredAt: 1_790_000_000_000,
    rrIntervals: [900],
  };
}

function render(controller: LiveHeartRateController): ReactTestRenderer {
  let tree: ReactTestRenderer;
  act(() => {
    tree = create(<LiveHeartRatePanel controller={controller} />);
  });
  return tree!;
}

/** 按钮文案是 Text 的子节点，向上找到真正带 onPress 的 Pressable。 */
function pressButton(tree: ReactTestRenderer, label: string): void {
  let node = tree.root.findByProps({ children: label });
  while (typeof node.props.onPress !== 'function') {
    if (node.parent === null) {
      throw new Error(`没有找到「${label}」按钮`);
    }
    node = node.parent;
  }
  act(() => node.props.onPress());
}

test('shows the latest reading and marks it as live once samples arrive', () => {
  const tree = render(
    fakeController({
      phase: 'streaming',
      samples: [sample(76), sample(78)],
      latest: sample(78),
      deviceName: 'HUAWEI Band 9-598',
    }),
  );

  expect(tree.root.findByProps({ children: 78 })).toBeTruthy();
  expect(tree.root.findByProps({ children: '实时' })).toBeTruthy();
  expect(tree.root.findByProps({ children: 'HUAWEI Band 9-598 · 直接来自手环蓝牙广播' })).toBeTruthy();
  act(() => tree.unmount());
});

test('lists discovered broadcasters while scanning and connects the chosen one', () => {
  const controller = fakeController({
    phase: 'scanning',
    devices: [
      { address: 'AA:BB', name: 'HUAWEI Band 9-598', rssi: -45 },
      { address: 'CC:DD', name: 'Chest strap', rssi: -70 },
    ],
  });
  const tree = render(controller);

  expect(tree.root.findByProps({ children: '停止搜索' })).toBeTruthy();
  act(() => {
    tree.root.findByProps({ accessibilityLabel: '连接HUAWEI Band 9-598' }).props.onPress();
  });
  expect(controller.connect).toHaveBeenCalledWith('AA:BB');
  act(() => tree.unmount());
});

test('surfaces the native failure message instead of hiding it', () => {
  const tree = render(
    fakeController({
      phase: 'error',
      message: '这个设备没有提供标准心率服务（0x180D），无法读取实时心率',
    }),
  );

  expect(tree.root.findByProps({
    children: '这个设备没有提供标准心率服务（0x180D），无法读取实时心率',
  })).toBeTruthy();
  expect(tree.root.findByProps({ children: '重新搜索' })).toBeTruthy();
  act(() => tree.unmount());
});

test('stops monitoring when the user presses 停止监测', () => {
  const controller = fakeController({
    phase: 'streaming',
    samples: [sample(78)],
    latest: sample(78),
    deviceName: 'HUAWEI Band 9-598',
  });
  const tree = render(controller);

  pressButton(tree, '停止监测');

  expect(controller.disconnect).toHaveBeenCalledTimes(1);
  act(() => tree.unmount());
});
