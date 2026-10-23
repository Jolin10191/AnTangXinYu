import { act, create, type ReactTestRenderer } from 'react-test-renderer';

import type { ApiClient } from '../api/client';
import { DeleteAccountScreen } from './delete-account-screen';

function fakeApi(deleteAccount: jest.Mock): ApiClient {
  return { deleteAccount } as unknown as ApiClient;
}

async function mount(
  deleteAccount: jest.Mock,
  handlers: { onCancel?: () => void; onDeleted?: () => void } = {},
): Promise<ReactTestRenderer> {
  let renderer: ReactTestRenderer | null = null;
  await act(async () => {
    renderer = create(
      <DeleteAccountScreen
        api={fakeApi(deleteAccount)}
        onCancel={handlers.onCancel ?? (() => undefined)}
        onDeleted={handlers.onDeleted ?? (() => undefined)}
      />,
    );
  });
  return renderer as unknown as ReactTestRenderer;
}

describe('DeleteAccountScreen', () => {
  it('says what will be deleted and keeps the button off until a password is typed', async () => {
    const deleteAccount = jest.fn(async () => undefined);
    const renderer = await mount(deleteAccount);

    expect(JSON.stringify(renderer.toJSON())).toContain('无法恢复');
    const button = renderer.root.findByProps({
      accessibilityLabel: '永久删除这个账号',
    });
    expect(button.props.disabled).toBe(true);

    await act(async () => {
      renderer.root
        .findByProps({ accessibilityLabel: '注销账号时输入登录密码' })
        .props.onChangeText('probe-pass-123');
    });
    expect(
      renderer.root.findByProps({ accessibilityLabel: '永久删除这个账号' }).props
        .disabled,
    ).toBe(false);
  });

  it('deletes with the typed password and tells the app it happened', async () => {
    const deleteAccount = jest.fn(async () => undefined);
    const onDeleted = jest.fn();
    const renderer = await mount(deleteAccount, { onDeleted });

    await act(async () => {
      renderer.root
        .findByProps({ accessibilityLabel: '注销账号时输入登录密码' })
        .props.onChangeText('probe-pass-123');
    });
    await act(async () => {
      renderer.root
        .findByProps({ accessibilityLabel: '永久删除这个账号' })
        .props.onPress();
    });

    expect(deleteAccount).toHaveBeenCalledWith('probe-pass-123');
    expect(onDeleted).toHaveBeenCalled();
  });

  it('shows why the deletion failed instead of closing quietly', async () => {
    const deleteAccount = jest.fn(async () => {
      throw new Error('密码不对');
    });
    const onDeleted = jest.fn();
    const renderer = await mount(deleteAccount, { onDeleted });

    await act(async () => {
      renderer.root
        .findByProps({ accessibilityLabel: '注销账号时输入登录密码' })
        .props.onChangeText('wrong');
    });
    await act(async () => {
      renderer.root
        .findByProps({ accessibilityLabel: '永久删除这个账号' })
        .props.onPress();
    });

    expect(JSON.stringify(renderer.toJSON())).toContain('密码不对');
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it('can back out', async () => {
    const onCancel = jest.fn();
    const renderer = await mount(jest.fn(), { onCancel });

    act(() => {
      renderer.root.findByProps({ accessibilityLabel: '先不删' }).props.onPress();
    });
    expect(onCancel).toHaveBeenCalled();
  });
});
