import { act, create, type ReactTestRenderer } from 'react-test-renderer';

import type { PsychosocialProfile } from '../api/types';
import { INSTRUMENT_ID, PsychosocialSection } from './PsychosocialSection';

function profile(overrides: Partial<PsychosocialProfile> = {}): PsychosocialProfile {
  return {
    assessedAt: '2026-10-31T09:00:00+08:00',
    instrument: INSTRUMENT_ID,
    fearPercent: 75,
    fearHigh: true,
    goldScore: 5,
    awareness: 'impaired',
    quadrant: 'high_fear_impaired_awareness',
    weeklyContactLimit: 4,
    ...overrides,
  };
}

function buildApi(existing: PsychosocialProfile | null) {
  return {
    getPsychosocialAssessment: jest.fn().mockResolvedValue(existing),
    recordPsychosocialAssessment: jest.fn().mockResolvedValue(profile()),
  };
}

function collectText(children: unknown): string {
  if (typeof children === 'string') return children;
  if (typeof children === 'number') return String(children);
  if (Array.isArray(children)) return children.map(collectText).join('');
  if (children !== null && typeof children === 'object' && 'props' in children) {
    const element = children as { props?: { children?: unknown } };
    return collectText(element.props?.children);
  }
  return '';
}

/** 组件的文案常常被拆成多个子节点，所以按整棵子树拼文本再匹配。 */
function treeText(tree: ReactTestRenderer): string {
  return tree.root
    .findAll(() => true)
    .map((node) => collectText(node.props?.children))
    .join('\n');
}

async function render(
  api: ReturnType<typeof buildApi>,
): Promise<ReactTestRenderer> {
  let tree: ReactTestRenderer | undefined;
  await act(async () => {
    tree = create(<PsychosocialSection api={api} />);
  });
  return tree!;
}

function findPressable(tree: ReactTestRenderer, label: string) {
  const target = tree.root.findAll(
    (node) =>
      node.props?.accessibilityRole !== undefined &&
      typeof node.props?.onPress === 'function' &&
      collectText(node.props.children).includes(label),
  );
  if (target.length === 0) throw new Error(`找不到按钮：${label}`);
  return target[0];
}

function press(tree: ReactTestRenderer, label: string) {
  const target = findPressable(tree, label);
  act(() => {
    target.props.onPress();
  });
}

describe('PsychosocialSection', () => {
  it('没有评估时先展示入口，点开后出现七道题', async () => {
    const api = buildApi(null);
    const tree = await render(api);

    expect(api.getPsychosocialAssessment).toHaveBeenCalledTimes(1);
    expect(treeText(tree)).toContain('开始填写');
    expect(treeText(tree)).toContain('糖糖怎么跟你说话');

    press(tree, '开始填写');

    const text = treeText(tree);
    expect(text).toContain('你平时能感觉到低血糖开始了吗');
    expect(text).toContain('反复测血糖');
    expect(text).toContain('不是标准化量表');
  });

  it('答完六道题并选好察觉评分后，按百分比提交', async () => {
    const api = buildApi(null);
    const tree = await render(api);
    press(tree, '开始填写');

    const radios = () =>
      tree.root.findAll(
        (node) =>
          node.props?.accessibilityRole === 'radio' &&
          typeof node.props?.onPress === 'function',
      );

    // 六道题各五个选项，第七题（察觉评分）七个选项。
    expect(radios().length).toBe(6 * 5 + 7);

    // 前三题（行为）都选「几乎每天」= 4；后三题（担忧）都选「从不」= 0。
    for (let index = 0; index < 3; index += 1) {
      act(() => {
        radios()[index * 5 + 4].props.onPress();
      });
    }
    for (let index = 3; index < 6; index += 1) {
      act(() => {
        radios()[index * 5].props.onPress();
      });
    }
    act(() => {
      radios()[30 + 4].props.onPress();
    });

    expect(treeText(tree)).toContain('已经填完了');

    await act(async () => {
      findPressable(tree, '保存').props.onPress();
    });

    expect(api.recordPsychosocialAssessment).toHaveBeenCalledTimes(1);
    const input = api.recordPsychosocialAssessment.mock.calls[0][0];
    expect(input.fearBehaviorPercent).toBe(100);
    expect(input.fearWorryPercent).toBe(0);
    expect(input.goldScore).toBe(5);
    expect(input.instrument).toBe(INSTRUMENT_ID);
    expect(typeof input.assessedAt).toBe('string');
  });

  it('没填完时保存按钮不可用', async () => {
    const api = buildApi(null);
    const tree = await render(api);
    press(tree, '开始填写');

    expect(
      findPressable(tree, '保存').props.accessibilityState?.disabled,
    ).toBe(true);
  });

  it('已有评估时展示每周联系次数，而不是分数', async () => {
    const api = buildApi(profile());
    const tree = await render(api);

    const text = treeText(tree);
    expect(text).toContain('每周主动联系你约 4 次');
    expect(text).toContain('上次填写：2026-10-31');
    // 不向用户复述分数或量表名。
    expect(text).not.toContain('HFS');
    expect(text).not.toContain('75');
  });
});
