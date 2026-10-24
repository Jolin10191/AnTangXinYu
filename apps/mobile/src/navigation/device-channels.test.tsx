import { act, create, type ReactTestRenderer } from 'react-test-renderer';

import { DeviceChannels } from './device-channels';
import { fakeGadgetbridge, fakeHealthConnect } from './device-controllers.fake';

async function mount(
  healthConnect = fakeHealthConnect(),
  gadgetbridge = fakeGadgetbridge(),
): Promise<ReactTestRenderer> {
  let tree: ReactTestRenderer | null = null;
  await act(async () => {
    tree = create(
      <DeviceChannels gadgetbridge={gadgetbridge} healthConnect={healthConnect} />,
    );
  });
  return tree as unknown as ReactTestRenderer;
}

function text(tree: ReactTestRenderer): string {
  return JSON.stringify(tree.toJSON());
}

describe('DeviceChannels', () => {
  it('把两条手环通道分开列，并说清各自适合什么手机', async () => {
    const tree = await mount();
    const body = text(tree);
    expect(body).toContain('设备与手环');
    expect(body).toContain('Health Connect');
    expect(body).toContain('系统健康数据');
    expect(body).toContain('导出文件导入');
    expect(body).toContain('华为手环 / 华为运动健康');
    expect(body).toContain('华为手机大多没有 Health Connect');
  });

  it('未连接时点一下是去连接，已连接时点一下是同步', async () => {
    const disconnected = fakeHealthConnect();
    const first = await mount(disconnected);
    await act(async () => {
      first.root
        .findByProps({ accessibilityLabel: '连接 Health Connect' })
        .props.onPress();
    });
    expect(disconnected.connect).toHaveBeenCalledTimes(1);
    expect(disconnected.sync).not.toHaveBeenCalled();

    const connected = fakeHealthConnect({ connected: true });
    const second = await mount(connected);
    await act(async () => {
      second.root
        .findByProps({ accessibilityLabel: '连接 Health Connect' })
        .props.onPress();
    });
    expect(connected.sync).toHaveBeenCalledTimes(1);
    expect(connected.connect).not.toHaveBeenCalled();
  });

  it('错误只落在出问题的那一行，不把两条通道一起变红', async () => {
    const tree = await mount(
      fakeHealthConnect({ error: '这台手机没有安装 Health Connect。' }),
      fakeGadgetbridge({ connected: true, heartRateCount: 12 }),
    );
    const body = text(tree);
    expect(body).toContain('这台手机没有安装 Health Connect。');
    expect(body).toContain('已导入 12 条心率记录');
    expect(body).toContain('再导入');
  });
});
