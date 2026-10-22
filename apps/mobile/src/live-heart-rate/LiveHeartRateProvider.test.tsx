import { Component, type ReactNode } from 'react';
import { Text } from 'react-native';
import { act, create, type ReactTestRenderer } from 'react-test-renderer';

import {
  LiveHeartRateProvider,
  useLiveHeartRateController,
} from './LiveHeartRateProvider';

function Probe() {
  const controller = useLiveHeartRateController();
  return <Text>{controller.phase}</Text>;
}

/** react-test-renderer 不会把渲染异常抛给 create()，用边界把错误渲染出来。 */
class ErrorBoundary extends Component<
  { children: ReactNode },
  { message: string | null }
> {
  state: { message: string | null } = { message: null };

  static getDerivedStateFromError(error: Error) {
    return { message: error.message };
  }

  render() {
    if (this.state.message === null) {
      return this.props.children;
    }
    return <Text>{this.state.message}</Text>;
  }
}

test('shares one live heart rate controller with the children', () => {
  let tree: ReactTestRenderer | undefined;
  act(() => {
    tree = create(
      <LiveHeartRateProvider active>
        <Probe />
      </LiveHeartRateProvider>,
    );
  });

  // 测试环境没有原生心率模块，controller 以 idle 起步。
  expect(tree!.root.findByProps({ children: 'idle' })).toBeTruthy();
  act(() => tree!.unmount());
});

test('rejects useLiveHeartRateController outside the provider', () => {
  let tree: ReactTestRenderer | undefined;
  act(() => {
    tree = create(
      <ErrorBoundary>
        <Probe />
      </ErrorBoundary>,
    );
  });

  expect(
    tree!.root.findByProps({
      children: 'useLiveHeartRateController 必须在 LiveHeartRateProvider 内使用',
    }),
  ).toBeTruthy();
  act(() => tree!.unmount());
});
