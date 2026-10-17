import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import type { ApiClient } from '../api/client';
import type { PsychosocialProfile } from '../api/types';
import { colors, radii, spacing, typefaces } from '../ui/theme';

/**
 * 沟通方式自评。
 *
 * 这里的题目是我们自己写的，**不是标准化量表**：HFS-II 与它的短版是受版权保护的
 * 量表，题目不能自拟，否则分数与国际常模不可比、分档阈值也失去依据。等正式授权
 * 到位后，这里的题目、计分与 `instrument` 会整体替换，接口与分档逻辑不用改。
 *
 * 为什么要问：低血糖恐惧高的人和察觉能力受损的人需要完全不同的说话方式与联系
 * 频率；这一页决定的是「怎么跟这个人说话」，不是判断情绪。
 */

type Question = {
  id: string;
  kind: 'behavior' | 'worry';
  text: string;
};

const SCALE_OPTIONS = [
  { value: 0, label: '从不' },
  { value: 1, label: '很少' },
  { value: 2, label: '有时' },
  { value: 3, label: '经常' },
  { value: 4, label: '几乎每天' },
];

const QUESTIONS: Question[] = [
  {
    id: 'repeat-test',
    kind: 'behavior',
    text: '过去一个月，我因为担心低血糖而反复测血糖，即使刚测过。',
  },
  {
    id: 'skip-exercise',
    kind: 'behavior',
    text: '过去一个月，我因为怕低血糖而减少或取消了原本要做的运动。',
  },
  {
    id: 'bedtime-snack',
    kind: 'behavior',
    text: '过去一个月，我会在睡前额外吃东西，即使当时血糖正常。',
  },
  {
    id: 'night-worry',
    kind: 'worry',
    text: '过去一个月，我担心夜里睡着以后发生低血糖。',
  },
  {
    id: 'alone-worry',
    kind: 'worry',
    text: '过去一个月，我担心一个人时低血糖会没人帮忙。',
  },
  {
    id: 'anxious-thought',
    kind: 'worry',
    text: '过去一个月，一想到可能低血糖，我就会紧张或心慌。',
  },
];

const GOLD_OPTIONS = [
  { value: 1, label: '1' },
  { value: 2, label: '2' },
  { value: 3, label: '3' },
  { value: 4, label: '4' },
  { value: 5, label: '5' },
  { value: 6, label: '6' },
  { value: 7, label: '7' },
];

export const INSTRUMENT_ID = 'antang-behavior-v1';

function percentOf(values: number[]): number {
  const total = values.reduce((sum, value) => sum + value, 0);
  return Math.round((total / (values.length * 4)) * 100);
}

export type PsychosocialSectionProps = {
  api: Pick<
    ApiClient,
    'getPsychosocialAssessment' | 'recordPsychosocialAssessment'
  >;
};

export function PsychosocialSection({ api }: PsychosocialSectionProps) {
  const [profile, setProfile] = useState<PsychosocialProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [goldScore, setGoldScore] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    let active = true;
    void api.getPsychosocialAssessment().then(
      (value) => {
        if (!active) return;
        setProfile(value);
        setLoadError(null);
        setLoading(false);
      },
      (reason: unknown) => {
        if (!active) return;
        setLoadError(errorMessage(reason));
        setLoading(false);
      },
    );
    return () => {
      active = false;
      mountedRef.current = false;
    };
  }, [api]);

  const answeredCount = QUESTIONS.filter(
    (question) => answers[question.id] !== undefined,
  ).length;
  const complete = answeredCount === QUESTIONS.length && goldScore !== null;

  const selectAnswer = useCallback((questionId: string, value: number) => {
    setAnswers((current) => ({ ...current, [questionId]: value }));
    setSaveError(null);
  }, []);

  function startOver() {
    setAnswers({});
    setGoldScore(null);
    setSaveError(null);
    setOpen(true);
  }

  async function submit() {
    if (!complete || saving) return;
    const behavior = QUESTIONS.filter((question) => question.kind === 'behavior').map(
      (question) => answers[question.id],
    );
    const worry = QUESTIONS.filter((question) => question.kind === 'worry').map(
      (question) => answers[question.id],
    );
    setSaving(true);
    setSaveError(null);
    try {
      const saved = await api.recordPsychosocialAssessment({
        fearBehaviorPercent: percentOf(behavior),
        fearWorryPercent: percentOf(worry),
        goldScore,
        instrument: INSTRUMENT_ID,
        assessedAt: new Date().toISOString(),
      });
      if (!mountedRef.current) return;
      setProfile(saved);
      setOpen(false);
      setAnswers({});
      setGoldScore(null);
    } catch (reason) {
      if (mountedRef.current) setSaveError(errorMessage(reason));
    } finally {
      if (mountedRef.current) setSaving(false);
    }
  }

  return (
    <View style={styles.card}>
      <Text style={styles.kicker}>沟通方式</Text>
      <Text style={styles.title}>糖糖怎么跟你说话</Text>

      {loading ? (
        <View style={styles.loadingRow}>
          <ActivityIndicator color={colors.primary} size="small" />
          <Text style={styles.loadingText}>正在读取…</Text>
        </View>
      ) : loadError !== null ? (
        <Text style={styles.errorText}>{loadError}</Text>
      ) : open ? (
        <View>
          <Text style={styles.description}>
            六个问题，约一分钟。选最接近最近一个月实际情况的一项。
          </Text>
          {QUESTIONS.map((question, index) => (
            <View key={question.id} style={styles.question}>
              <Text style={styles.questionText}>
                {index + 1}. {question.text}
              </Text>
              <View style={styles.optionRow}>
                {SCALE_OPTIONS.map((option) => {
                  const selected = answers[question.id] === option.value;
                  return (
                    <Pressable
                      accessibilityRole="radio"
                      accessibilityState={{ selected, checked: selected }}
                      key={option.value}
                      onPress={() => selectAnswer(question.id, option.value)}
                      style={[styles.option, selected && styles.optionSelected]}
                    >
                      <Text
                        style={[
                          styles.optionText,
                          selected && styles.optionTextSelected,
                        ]}
                      >
                        {option.label}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          ))}

          <View style={styles.question}>
            <Text style={styles.questionText}>
              7. 你平时能感觉到低血糖开始了吗？
            </Text>
            <Text style={styles.goldHint}>
              1 = 总能感觉到，7 = 完全感觉不到
            </Text>
            <View style={styles.optionRow}>
              {GOLD_OPTIONS.map((option) => {
                const selected = goldScore === option.value;
                return (
                  <Pressable
                    accessibilityRole="radio"
                    accessibilityState={{ selected, checked: selected }}
                    key={option.value}
                    onPress={() => {
                      setGoldScore(option.value);
                      setSaveError(null);
                    }}
                    style={[styles.goldOption, selected && styles.optionSelected]}
                  >
                    <Text
                      style={[
                        styles.optionText,
                        selected && styles.optionTextSelected,
                      ]}
                    >
                      {option.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>

          {saveError !== null ? (
            <Text style={styles.errorText}>{saveError}</Text>
          ) : null}

          <Text style={styles.progressText}>
            {complete
              ? '已经填完了，可以保存。'
              : `还差 ${QUESTIONS.length - answeredCount + (goldScore === null ? 1 : 0)} 题。`}
          </Text>

          <Pressable
            accessibilityRole="button"
            accessibilityState={{ disabled: !complete || saving }}
            disabled={!complete || saving}
            onPress={() => void submit()}
            style={[styles.primaryButton, (!complete || saving) && styles.buttonDisabled]}
          >
            {saving ? (
              <ActivityIndicator color={colors.white} size="small" />
            ) : (
              <Text style={styles.primaryButtonText}>保存</Text>
            )}
          </Pressable>
          <Pressable
            accessibilityRole="button"
            onPress={() => {
              setOpen(false);
              setSaveError(null);
            }}
            style={styles.secondaryButton}
          >
            <Text style={styles.secondaryButtonText}>以后再说</Text>
          </Pressable>
        </View>
      ) : (
        <View>
          {profile === null ? (
            <Text style={styles.description}>
              还没填过。答完这七个问题，糖糖会按你的情况调整说话方式和主动联系的频率。
            </Text>
          ) : (
            <View>
              <Text style={styles.description}>
                糖糖现在每周主动联系你约 {profile.weeklyContactLimit} 次。
              </Text>
              <Text style={styles.metaText}>
                上次填写：{formatDate(profile.assessedAt)}
              </Text>
            </View>
          )}
          <Pressable
            accessibilityRole="button"
            onPress={startOver}
            style={styles.primaryButton}
          >
            <Text style={styles.primaryButtonText}>
              {profile === null ? '开始填写' : '重新填写'}
            </Text>
          </Pressable>
        </View>
      )}

      <Text style={styles.noteText}>
        这几道题是我们自己写的，不是标准化量表，只用来决定沟通方式，不作为诊断依据。
      </Text>
    </View>
  );
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, '0')}-${String(
    parsed.getDate(),
  ).padStart(2, '0')}`;
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
    fontSize: 20,
    marginBottom: spacing.xs,
  },
  description: {
    color: colors.text,
    fontFamily: typefaces.sans,
    fontSize: 14,
    lineHeight: 21,
    marginBottom: spacing.sm,
  },
  loadingRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.xs,
  },
  loadingText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 14,
  },
  errorText: {
    color: colors.danger,
    fontFamily: typefaces.sans,
    fontSize: 13,
    lineHeight: 20,
    marginBottom: spacing.xs,
  },
  question: {
    borderTopColor: colors.line,
    borderTopWidth: 1,
    paddingTop: spacing.sm,
    marginBottom: spacing.sm,
  },
  questionText: {
    color: colors.ink,
    fontFamily: typefaces.sans,
    fontSize: 14,
    lineHeight: 21,
    marginBottom: spacing.xs,
  },
  goldHint: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 12,
    marginBottom: spacing.xs,
  },
  optionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  option: {
    backgroundColor: colors.paperMuted,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  goldOption: {
    alignItems: 'center',
    backgroundColor: colors.paperMuted,
    borderRadius: radii.sm,
    minWidth: 36,
    paddingHorizontal: spacing.xs,
    paddingVertical: spacing.xs,
  },
  optionSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
    borderWidth: 1,
  },
  optionText: {
    color: colors.text,
    fontFamily: typefaces.sans,
    fontSize: 13,
  },
  optionTextSelected: {
    color: colors.primaryPressed,
    fontFamily: typefaces.sansMedium,
  },
  progressText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 12,
    marginTop: spacing.xs,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: radii.sm,
    marginTop: spacing.sm,
    paddingVertical: spacing.sm,
  },
  buttonDisabled: {
    backgroundColor: colors.disabled,
  },
  primaryButtonText: {
    color: colors.white,
    fontFamily: typefaces.sansMedium,
    fontSize: 15,
  },
  secondaryButton: {
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  secondaryButtonText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 14,
  },
  metaText: {
    color: colors.muted,
    fontFamily: typefaces.sans,
    fontSize: 12,
    marginBottom: spacing.xs,
  },
  noteText: {
    color: colors.faint,
    fontFamily: typefaces.sans,
    fontSize: 12,
    lineHeight: 18,
    marginTop: spacing.sm,
  },
});
