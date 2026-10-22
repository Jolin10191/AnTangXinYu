import { act, create, type ReactTestRenderer } from 'react-test-renderer';

import type { FearSummary } from '../api/types';
import { FearBehaviorSection } from './FearBehaviorSection';

function summary(overrides: Partial<FearSummary> = {}): FearSummary {
  return {
    windowStart: '2026-10-03T09:00:00+08:00',
    windowEnd: '2026-10-31T09:00:00+08:00',
    behaviorCounts: { extra_check: 6, exercise_avoidance: 2 },
    behaviorTotal: 8,
    monitoringWeekly: 1.5,
    avoidanceWeekly: 0.5,
    beliefs: [],
    assessment: null,
    discrepancy: 'unknown',
    discrepancyNote: '',
    ...overrides,
  };
}

function buildApi(value: FearSummary) {
  return { getFearSummary: jest.fn().mockResolvedValue(value) };
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
    tree = create(<FearBehaviorSection api={api} />);
  });
  return tree!;
}

describe('FearBehaviorSection', () => {
  it('展示聊天里记下的行为次数与每周频率', async () => {
    const tree = await render(buildApi(summary()));
    const text = treeText(tree);
    expect(text).toContain('最近 28 天');
    expect(text).toContain('额外查血糖');
    expect(text).toContain('6 次');
    expect(text).toContain('回避运动');
    expect(text).toContain('反复确认血糖平均每周 1.5 次');
    expect(text).toContain('因担心而回避运动或自行减药，平均每周 0.5 次');
  });

  it('展示反复出现的信念原话，并且不出现分数', async () => {
    const tree = await render(
      buildApi(
        summary({
          beliefs: [
            {
              beliefCode: 'hypo_causes_coma',
              label: '低血糖会让我昏迷',
              mentions: 3,
              reframes: 1,
              denials: 0,
              latestQuote: '总怕半夜低血糖昏过去没人知道',
              latestDetectedAt: '2026-10-30T23:10:00+08:00',
              resolved: false,
            },
          ],
        }),
      ),
    );
    const text = treeText(tree);
    expect(text).toContain('低血糖会让我昏迷');
    expect(text).toContain('提到 3 次');
    expect(text).toContain('总怕半夜低血糖昏过去没人知道');
    expect(text).not.toContain('%');
  });

  it('没有记录时给出空状态说明', async () => {
    const tree = await render(
      buildApi(
        summary({
          behaviorCounts: {},
          behaviorTotal: 0,
          monitoringWeekly: 0,
          avoidanceWeekly: 0,
        }),
      ),
    );
    expect(treeText(tree)).toContain('还没有记录');
  });

  it('读取失败时显示错误文案', async () => {
    const api = {
      getFearSummary: jest.fn().mockRejectedValue(new Error('网络不可用')),
    };
    const tree = await render(api);
    expect(treeText(tree)).toContain('网络不可用');
  });
});
