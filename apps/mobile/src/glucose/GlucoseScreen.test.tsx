import { act, create } from 'react-test-renderer';

import { GlucoseScreen } from './GlucoseScreen';

const NOW = '2026-10-20T08:30:00+08:00';

function fakeApi(readings: unknown[]) {
  return {
    getGlucoseReadings: async () =>
      readings as never,
    getGlucoseSummary: async () => ({
      days: 7,
      count: 0,
      averageMgDl: null,
      minimumMgDl: null,
      maximumMgDl: null,
      below70Count: 0,
    }),
    createGlucoseReading: async () => {
      throw new Error('not used');
    },
    revokeGlucoseReading: async () => undefined,
  };
}

async function render(readings: unknown[]) {
  let tree: ReturnType<typeof create> | null = null;
  await act(async () => {
    tree = create(<GlucoseScreen api={fakeApi(readings)} />);
  });
  if (tree === null) throw new Error('render failed');
  return JSON.stringify((tree as ReturnType<typeof create>).toJSON());
}

type Node = { props: Record<string, unknown>; children: Node[] | null };

/** 按 accessibilityLabel 找可点的节点，找不到就报错，避免测试静默通过。 */
function byLabel(tree: ReturnType<typeof create>, label: string): Node {
  const found = tree.root.findAll(
    node => node.props.accessibilityLabel === label,
  );
  if (found.length === 0) throw new Error(`找不到 ${label}`);
  return found[0] as unknown as Node;
}

function press(tree: ReturnType<typeof create>, label: string): void {
  (byLabel(tree, label).props.onPress as () => void)();
}

function typeInto(
  tree: ReturnType<typeof create>,
  label: string,
  text: string,
): void {
  (byLabel(tree, label).props.onChangeText as (value: string) => void)(text);
}

describe('GlucoseScreen', () => {
  it('shows the empty hint when nothing has been logged', async () => {
    const rendered = await render([]);
    expect(rendered).toContain('记一条血糖');
    expect(rendered).toContain('还没有记录');
  });

  it('shows a revoked row as revoked instead of hiding it', async () => {
    const rendered = await render([
      {
        id: 'g1',
        valueMgDl: 62,
        measuredAt: NOW,
        context: 'bedtime',
        source: 'manual',
        note: null,
        revokedAt: NOW,
        createdAt: NOW,
      },
    ]);
    expect(rendered).toContain('62');
    expect(rendered).toContain('已撤回');
    expect(rendered).toContain('睡前');
  });

  it('shows the context label and note for a live row', async () => {
    const rendered = await render([
      {
        id: 'g2',
        valueMgDl: 148,
        measuredAt: NOW,
        context: 'post_meal',
        source: 'manual',
        note: '刚吃了两碗饭',
        revokedAt: null,
        createdAt: NOW,
      },
    ]);
    expect(rendered).toContain('148');
    expect(rendered).toContain('餐后');
    expect(rendered).toContain('刚吃了两碗饭');
    expect(rendered).not.toContain('已撤回');
  });

  it('sends the meter with a fingerstick reading', async () => {
    const sent: Record<string, unknown>[] = [];
    const api = {
      ...fakeApi([]),
      createGlucoseReading: async (input: Record<string, unknown>) => {
        sent.push(input);
        return { id: 'g3' } as never;
      },
    };
    let tree: ReturnType<typeof create> | null = null;
    await act(async () => {
      tree = create(<GlucoseScreen api={api as never} />);
    });
    if (tree === null) throw new Error('render failed');

    await act(async () => {
      typeInto(tree as ReturnType<typeof create>, '血糖数值', '96');
    });
    await act(async () => {
      press(tree as ReturnType<typeof create>, '血糖仪 三诺');
    });
    await act(async () => {
      press(tree as ReturnType<typeof create>, '保存这条血糖记录');
    });

    expect(sent).toHaveLength(1);
    expect(sent[0].valueMgDl).toBe(96);
    expect(sent[0].source).toBe('fingerstick');
    expect(sent[0].sourceDevice).toBe('sannuo');
  });

  it('hides the meter row for a lab reading and sends no meter', async () => {
    const sent: Record<string, unknown>[] = [];
    const api = {
      ...fakeApi([]),
      createGlucoseReading: async (input: Record<string, unknown>) => {
        sent.push(input);
        return { id: 'g4' } as never;
      },
    };
    let tree: ReturnType<typeof create> | null = null;
    await act(async () => {
      tree = create(<GlucoseScreen api={api as never} />);
    });
    if (tree === null) throw new Error('render failed');
    const host = tree as ReturnType<typeof create>;

    // 先在指尖血下选一台机器，再切到静脉血：行要消失，值也不能带出去。
    await act(async () => {
      press(host, '血糖仪 罗氏');
    });
    await act(async () => {
      press(host, '血糖来源 静脉血');
    });
    await act(async () => {
      typeInto(host, '血糖数值', '104');
    });
    await act(async () => {
      press(host, '保存这条血糖记录');
    });

    expect(
      host.root.findAll(node => node.props.accessibilityLabel === '血糖仪 三诺'),
    ).toHaveLength(0);
    expect(sent).toHaveLength(1);
    expect(sent[0].source).toBe('lab');
    expect(sent[0].sourceDevice).toBeUndefined();
  });
});
