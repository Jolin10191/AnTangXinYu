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
});
