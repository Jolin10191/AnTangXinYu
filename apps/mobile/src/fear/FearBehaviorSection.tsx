import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import type { ApiClient } from '../api/client';
import type {
  BeliefEventRecord,
  FearBehaviorLog,
  FearSummary,
  HypoglycemiaBeliefNode,
} from '../api/types';
import { colors, radii, spacing, typefaces } from '../ui/theme';

/**
 * 行为与担心：把聊天里自然说出来的行为和念头摊开给自己看。
 *
 * 这一页没有输入框——数据全部来自对话本身（模型调用 `log_fear_behavior` /
 * `record_hypoglycemia_belief` 时落库），因为让患者每天手动打卡的行为数据几乎一定
 * 会断更，而「又测了一次」「今晚不敢跑步」这类话本来就会在对话里出现。
 *
 * 不显示分数、不给分级、不下判断：显性量表分在「沟通方式」那一页，这里只呈现
 * 次数与原话，两者的对照说明由后端给出（`discrepancyNote`），并且明确写成
 * 「一致不一致」，不是诊断。
 *
 * 下半部分是可逐条撤回的记录。汇总卡片只给次数，患者看着「夜间查血糖 6 次」却
 * 没法说「那次不算」，等于没给撤回权；所以这里列出单条记录、带上 id，删之前
 * 还要再确认一次（AGENTS.md 的要求，且这类记录删了就找不回来）。
 */

export const BEHAVIOR_LABELS: Record<string, string> = {
  extra_check: '额外查血糖',
  night_check: '夜间查血糖',
  comfort_meal: '因为担心而加餐',
  exercise_avoidance: '回避运动',
  insulin_hold: '自行减少胰岛素',
};

const BEHAVIOR_ORDER = [
  'extra_check',
  'night_check',
  'comfort_meal',
  'exercise_avoidance',
  'insulin_hold',
];

export type FearBehaviorSectionProps = {
  api: Pick<
    ApiClient,
    | 'getFearSummary'
    | 'getFearBehaviorLogs'
    | 'getBeliefEvents'
    | 'deleteFearBehaviorLog'
    | 'deleteBeliefEvent'
  >;
};

type PendingDelete = { kind: 'behavior' | 'belief'; id: string };

export function FearBehaviorSection({ api }: FearBehaviorSectionProps) {
  const [summary, setSummary] = useState<FearSummary | null>(null);
  const [logs, setLogs] = useState<FearBehaviorLog[]>([]);
  const [events, setEvents] = useState<BeliefEventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingDelete | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let active = true;
    // 三个接口一起要：汇总给次数，两个列表给可删的条目。setState 全部放在
    // then/catch 回调里，不在 effect 体里同步调用（react-hooks 规则）。
    void Promise.all([
      api.getFearSummary(),
      api.getFearBehaviorLogs(),
      api.getBeliefEvents(),
    ])
      .then(([nextSummary, nextLogs, nextEvents]) => {
        if (!active) return;
        setSummary(nextSummary);
        setLogs(nextLogs);
        setEvents(nextEvents);
        setLoadError(null);
        setLoading(false);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setLoadError(errorMessage(reason));
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);

  const remove = useCallback(
    async (target: PendingDelete): Promise<void> => {
      setDeleting(true);
      try {
        if (target.kind === 'behavior') {
          await api.deleteFearBehaviorLog(target.id);
          setLogs((current) => current.filter((log) => log.id !== target.id));
        } else {
          await api.deleteBeliefEvent(target.id);
          setEvents((current) =>
            current.filter((event) => event.id !== target.id),
          );
        }
        setActionError(null);
        setPending(null);
        // 汇总的数字要跟着变，否则刚删掉的那几条还挂在「6 次」里。
        setSummary(await api.getFearSummary());
      } catch (reason) {
        setActionError(errorMessage(reason));
      } finally {
        setDeleting(false);
      }
    },
    [api],
  );

  return (
    <View style={styles.card}>
      <Text style={styles.kicker}>行为记录</Text>
      <Text style={styles.title}>你最近在做什么</Text>

      {loading ? (
        <View style={styles.loadingRow}>
          <ActivityIndicator color={colors.primary} size="small" />
          <Text style={styles.loadingText}>正在读取…</Text>
        </View>
      ) : loadError !== null ? (
        <Text style={styles.errorText}>{loadError}</Text>
      ) : summary === null ? null : isEmpty(summary) ? (
        <Text style={styles.description}>
          还没有记录。聊天时顺口提到的「刚才又测了一次」「今晚不敢跑步」这类事，糖糖会记在这里，下次就记得了。
        </Text>
      ) : (
        <View>
          <Text style={styles.description}>
            最近 {windowDays(summary)} 天，聊天里提到这些：
          </Text>

          {BEHAVIOR_ORDER.filter(
            (kind) => (summary.behaviorCounts[kind] ?? 0) > 0,
          ).map((kind) => (
            <View key={kind} style={styles.row}>
              <Text style={styles.rowLabel}>{behaviorLabel(kind)}</Text>
              <Text style={styles.rowValue}>
                {summary.behaviorCounts[kind]} 次
              </Text>
            </View>
          ))}

          {summary.monitoringWeekly > 0 ? (
            <Text style={styles.metaText}>
              反复确认血糖平均每周 {formatRate(summary.monitoringWeekly)} 次。
            </Text>
          ) : null}

          {summary.avoidanceWeekly > 0 ? (
            <Text style={styles.metaText}>
              因担心而回避运动或自行减药，平均每周{' '}
              {formatRate(summary.avoidanceWeekly)} 次。
            </Text>
          ) : null}

          {summary.beliefs.length > 0 ? (
            <View style={styles.beliefBlock}>
              <Text style={styles.subtitle}>反复出现的念头</Text>
              {summary.beliefs.map((belief) => (
                <BeliefRow belief={belief} key={belief.beliefCode} />
              ))}
            </View>
          ) : null}

          {summary.discrepancy !== 'unknown' &&
          summary.discrepancyNote.length > 0 ? (
            <Text style={styles.noteText}>{summary.discrepancyNote}</Text>
          ) : null}
        </View>
      )}

      {actionError !== null ? (
        <Text style={styles.errorText}>{actionError}</Text>
      ) : null}

      {logs.length > 0 || events.length > 0 ? (
        <View style={styles.recordsBlock}>
          <Text style={styles.subtitle}>可以删掉的记录</Text>
          <Text style={styles.description}>
            每一条都是聊天里你自己说的。删掉就真的没了，所以先确认一次。
          </Text>
          {logs.map((log) => (
            <RecordRow
              body={log.note}
              deleting={deleting}
              key={log.id}
              label={log.label}
              onCancel={() => setPending(null)}
              onConfirm={() => void remove({ kind: 'behavior', id: log.id })}
              onRequest={() => setPending({ kind: 'behavior', id: log.id })}
              pending={
                pending?.kind === 'behavior' && pending.id === log.id
              }
              when={formatWhen(log.occurredAt)}
            />
          ))}
          {events.map((event) => (
            <RecordRow
              body={`「${event.quote}」`}
              deleting={deleting}
              key={event.id}
              label={event.label}
              onCancel={() => setPending(null)}
              onConfirm={() => void remove({ kind: 'belief', id: event.id })}
              onRequest={() => setPending({ kind: 'belief', id: event.id })}
              pending={pending?.kind === 'belief' && pending.id === event.id}
              when={formatWhen(event.detectedAt)}
            />
          ))}
        </View>
      ) : null}

      <Text style={styles.noteText}>
        这些是聊天里你自己说的事，不是量表分数，也不用来给你打分。不想要的那条，上面可以直接删。
      </Text>
    </View>
  );
}

type RecordRowProps = {
  label: string;
  body: string | null;
  when: string;
  pending: boolean;
  deleting: boolean;
  onRequest: () => void;
  onCancel: () => void;
  onConfirm: () => void;
};

function RecordRow({
  label,
  body,
  when,
  pending,
  deleting,
  onRequest,
  onCancel,
  onConfirm,
}: RecordRowProps) {
  return (
    <View style={styles.recordRow}>
      <View style={styles.beliefHead}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={styles.rowTag}>{when}</Text>
      </View>
      {body !== null && body.length > 0 ? (
        <Text style={styles.quoteText}>{body}</Text>
      ) : null}
      {pending ? (
        <View style={styles.confirmRow}>
          <Text style={styles.confirmText}>删掉这条？</Text>
          <Pressable
            accessibilityLabel="确认删除"
            disabled={deleting}
            onPress={onConfirm}
            style={styles.confirmDelete}
          >
            <Text style={styles.confirmDeleteText}>
              {deleting ? '删除中…' : '删掉'}
            </Text>
          </Pressable>
          <Pressable
            accessibilityLabel="取消删除"
            disabled={deleting}
            onPress={onCancel}
            style={styles.confirmCancel}
          >
            <Text style={styles.confirmCancelText}>取消</Text>
          </Pressable>
        </View>
      ) : (
        <Pressable
          accessibilityLabel={`删除${label}`}
          onPress={onRequest}
          style={styles.deleteLink}
        >
          <Text style={styles.deleteLinkText}>删除</Text>
        </Pressable>
      )}
    </View>
  );
}

function BeliefRow({ belief }: { belief: HypoglycemiaBeliefNode }) {
  return (
    <View style={styles.beliefRow}>
      <View style={styles.beliefHead}>
        <Text style={styles.rowLabel}>{belief.label}</Text>
        <Text style={styles.rowTag}>
          {belief.resolved ? '最近松动了' : `提到 ${belief.mentions} 次`}
        </Text>
      </View>
      <Text style={styles.quoteText}>「{belief.latestQuote}」</Text>
    </View>
  );
}

function isEmpty(summary: FearSummary): boolean {
  return summary.behaviorTotal === 0 && summary.beliefs.length === 0;
}

function behaviorLabel(kind: string): string {
  return BEHAVIOR_LABELS[kind] ?? kind;
}

function windowDays(summary: FearSummary): number {
  const start = new Date(summary.windowStart).getTime();
  const end = new Date(summary.windowEnd).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return 28;
  return Math.round((end - start) / (24 * 60 * 60 * 1000));
}

function formatRate(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function formatWhen(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (part: number): string => String(part).padStart(2, '0');
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error && reason.message.length > 0
    ? reason.message
    : '读取失败，请稍后再试';
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.paper,
    borderColor: colors.line,
    borderRadius: radii.md,
    borderWidth: 1,
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  kicker: {
    color: colors.muted,
    fontFamily: typefaces.sansMedium,
    fontSize: 12,
    letterSpacing: 1,
    marginBottom: spacing.xxs,
  },
  title: {
    color: colors.ink,
    fontFamily: typefaces.sansMedium,
    fontSize: 18,
    marginBottom: spacing.xs,
  },
  subtitle: {
    color: colors.ink,
    fontFamily: typefaces.sansMedium,
    fontSize: 14,
    marginBottom: spacing.xs,
    marginTop: spacing.sm,
  },
  description: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 14,
    lineHeight: 21,
  },
  loadingRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.xs,
    paddingVertical: spacing.sm,
  },
  loadingText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 14,
  },
  errorText: {
    color: colors.danger,
    fontFamily: typefaces.sans,
    fontSize: 14,
    lineHeight: 20,
  },
  row: {
    alignItems: 'center',
    borderBottomColor: colors.line,
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
  },
  rowLabel: {
    color: colors.ink,
    flexShrink: 1,
    fontFamily: typefaces.sans,
    fontSize: 15,
  },
  rowValue: {
    color: colors.ink,
    fontFamily: typefaces.sansMedium,
    fontSize: 15,
  },
  rowTag: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 12,
  },
  metaText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 13,
    lineHeight: 19,
    marginTop: spacing.xs,
  },
  beliefBlock: {
    marginTop: spacing.xs,
  },
  recordsBlock: {
    marginTop: spacing.xs,
  },
  beliefRow: {
    borderBottomColor: colors.line,
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingVertical: spacing.xs,
  },
  recordRow: {
    borderBottomColor: colors.line,
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingVertical: spacing.xs,
  },
  beliefHead: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  quoteText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 13,
    lineHeight: 19,
    marginTop: spacing.xxs,
  },
  deleteLink: {
    alignSelf: 'flex-start',
    paddingVertical: spacing.xxs,
  },
  deleteLinkText: {
    color: colors.danger,
    fontFamily: typefaces.sans,
    fontSize: 13,
  },
  confirmRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.xs,
    marginTop: spacing.xxs,
  },
  confirmText: {
    color: colors.ink,
    fontFamily: typefaces.sans,
    fontSize: 13,
  },
  confirmDelete: {
    backgroundColor: colors.danger,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xxs,
  },
  confirmDeleteText: {
    color: colors.paper,
    fontFamily: typefaces.sansMedium,
    fontSize: 13,
  },
  confirmCancel: {
    borderColor: colors.line,
    borderRadius: radii.sm,
    borderWidth: 1,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xxs,
  },
  confirmCancelText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 13,
  },
  noteText: {
    color: colors.faint,
    fontFamily: typefaces.sans,
    fontSize: 12,
    lineHeight: 18,
    marginTop: spacing.sm,
  },
});
