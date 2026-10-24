import { act, create } from 'react-test-renderer';

import { AppMenu } from './app-menu';

describe('AppMenu', () => {
  test('lists conversations and opens health, settings and a new chat', async () => {
    const onClose = jest.fn();
    const onOpenHealth = jest.fn();
    const onOpenSettings = jest.fn();
    const onSelectConversation = jest.fn();
    const onNewChat = jest.fn();

    let tree: ReturnType<typeof create>;
    await act(async () => {
      tree = create(
        <AppMenu
          conversations={[
            {
              group: '今天',
              id: 'conversation-1',
              title: '最近有点担心低血糖',
              time: '17:30',
            },
          ]}
          activeConversationId="conversation-1"
          onNewChat={onNewChat}
          onClose={onClose}
          onOpenHealth={onOpenHealth}
          onOpenSettings={onOpenSettings}
          onSelectConversation={onSelectConversation}
          username="demo-user"
          visible
          gadgetbridgeChecking={false}
          gadgetbridgeConnected={false}
          gadgetbridgeSyncing={false}
          gadgetbridgeError={null}
          gadgetbridgeProgress={null}
          gadgetbridgeLastSyncedAt={null}
          onGadgetbridgeConnect={() => {}}
          onGadgetbridgeSync={() => {}}
        />,
      );
    });

    act(() => {
      tree!.root.findByProps({ accessibilityLabel: '健康档案' }).props.onPress();
      tree!.root.findByProps({ accessibilityLabel: '打开设置' }).props.onPress();
      tree!.root
        .findByProps({ accessibilityLabel: '最近有点担心低血糖 17:30' })
        .props.onPress();
      tree!.root
        .findByProps({ accessibilityLabel: '开始新的对话' })
        .props.onPress();
    });

    expect(onOpenHealth).toHaveBeenCalledTimes(1);
    expect(onOpenSettings).toHaveBeenCalledTimes(1);
    expect(onSelectConversation).toHaveBeenCalledWith('conversation-1');
    expect(onNewChat).toHaveBeenCalledTimes(1);

    // 「检查更新」搬进设置页了，侧边栏不再挂这一行。
    expect(
      tree!.root.findAllByProps({ accessibilityLabel: '检查更新' }),
    ).toHaveLength(0);

    act(() => tree!.unmount());
  });
});
