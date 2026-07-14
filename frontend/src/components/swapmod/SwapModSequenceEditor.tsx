import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, FileClock, Loader2, RotateCcw, Save } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { swapmodApi } from '../../api/client';
import type {
  SwapmodEditableSequence,
  SwapmodSequenceCandidate,
  SwapmodSequenceCandidateRequest,
  SwapmodSequenceEditorStatus,
  SwapmodStep,
} from '../../api/client';
import { useToast } from '../../contexts/ToastContext';
import { Button } from '../Button';

const STEP_OPTIONS: Array<{ step: SwapmodStep; label: string }> = [
  { step: 'RELEASE_PLATE', label: 'Release' },
  { step: 'LOAD_NEXT_PLATE', label: 'Load' },
];

function shortHash(value: string | null | undefined) {
  return value ? value.slice(0, 12) : 'not configured';
}

function sequenceErrorMessage(sequence: SwapmodEditableSequence) {
  if (!sequence.configured) return 'Pinned sequence is not configured.';
  if (sequence.error_code === 'sequence_sha256_mismatch') return 'Pinned sequence hash verification failed.';
  if (sequence.error_code === 'sequence_has_no_editable_actions') return 'No editable movement feedrates were found.';
  return 'Pinned sequence cannot be edited until its configuration is repaired.';
}

export function SwapModSequenceEditor() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const [activeStep, setActiveStep] = useState<SwapmodStep>('RELEASE_PLATE');
  const [feedrates, setFeedrates] = useState<Record<string, string>>({});
  const [savedCandidate, setSavedCandidate] = useState<SwapmodSequenceCandidate | null>(null);

  const editorQuery = useQuery({
    queryKey: ['swapmod-sequence-editor'],
    queryFn: swapmodApi.getSequenceEditorStatus,
    staleTime: 5000,
    refetchOnWindowFocus: false,
  });
  const sequence = editorQuery.data?.sequences.find((item) => item.step === activeStep);

  useEffect(() => {
    if (!sequence) return;
    setFeedrates(Object.fromEntries(sequence.actions.map((action) => [action.action_id, String(action.feedrate)])));
    setSavedCandidate(sequence.latest_candidate);
  }, [sequence]);

  const normalizedActions = useMemo(
    () =>
      (sequence?.actions ?? []).map((action) => ({
        action_id: action.action_id,
        feedrate: Number(feedrates[action.action_id]),
      })),
    [feedrates, sequence],
  );
  const feedratesValid = Boolean(
    editorQuery.data
      && normalizedActions.length > 0
      && normalizedActions.every(
        (action) =>
          Number.isInteger(action.feedrate)
          && action.feedrate >= editorQuery.data.feedrate_min
          && action.feedrate <= editorQuery.data.feedrate_max,
      ),
  );
  const hasChanges = Boolean(
    sequence
      && normalizedActions.some((action, index) => action.feedrate !== sequence.actions[index]?.feedrate),
  );

  const saveMutation = useMutation({
    mutationFn: (body: SwapmodSequenceCandidateRequest) => swapmodApi.createSequenceCandidate(body),
    onSuccess: (candidate) => {
      queryClient.setQueryData<SwapmodSequenceEditorStatus>(['swapmod-sequence-editor'], (current) =>
        current
          ? {
              ...current,
              sequences: current.sequences.map((item) =>
                item.step === candidate.step ? { ...item, latest_candidate: candidate } : item,
              ),
            }
          : current,
      );
      setSavedCandidate(candidate);
      showToast(t('settings.swapmod.sequenceSaved', 'Candidate version saved for review.'), 'success');
    },
    onError: (error: Error) => {
      showToast(error.message, 'error');
    },
  });

  const resetFeedrates = () => {
    if (!sequence) return;
    setFeedrates(Object.fromEntries(sequence.actions.map((action) => [action.action_id, String(action.feedrate)])));
  };

  const saveCandidate = () => {
    if (!sequence?.base_sha256 || !feedratesValid || !hasChanges) return;
    saveMutation.mutate({
      step: sequence.step,
      base_sha256: sequence.base_sha256,
      actions: normalizedActions,
    });
  };

  if (editorQuery.isLoading) {
    return (
      <section className="flex min-h-32 items-center justify-center border border-bambu-dark-tertiary bg-bambu-dark-secondary p-6 rounded-lg">
        <Loader2 className="h-5 w-5 animate-spin text-bambu-green" aria-label={t('common.loading', 'Loading')} />
      </section>
    );
  }

  if (editorQuery.isError || !editorQuery.data) {
    return (
      <section className="flex items-start gap-3 border border-red-500/40 bg-red-500/10 p-4 rounded-lg">
        <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-400" />
        <p className="text-sm text-red-300">
          {t('settings.swapmod.sequenceLoadFailed', 'Sequence editor status could not be loaded.')}
        </p>
      </section>
    );
  }

  if (!editorQuery.data.enabled) {
    return (
      <section className="flex items-start gap-3 border border-bambu-dark-tertiary bg-bambu-dark-secondary p-4 rounded-lg">
        <FileClock className="mt-0.5 h-5 w-5 flex-shrink-0 text-bambu-gray" />
        <div>
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
            {t('settings.swapmod.sequenceEditor', 'Sequence editor')}
          </h4>
          <p className="mt-1 text-sm text-bambu-gray">
            {t('settings.swapmod.sequenceDisabled', 'Sequence editor is disabled.')}
          </p>
        </div>
      </section>
    );
  }

  const savingBlocked = editorQuery.data.direct_canary_armed;
  const canSave = Boolean(
    sequence?.editable
      && sequence.base_sha256
      && feedratesValid
      && hasChanges
      && !savingBlocked
      && !saveMutation.isPending,
  );

  return (
    <section className="space-y-3" id="card-swapmod-sequences">
      <div className="flex flex-col gap-3 border border-bambu-dark-tertiary bg-bambu-dark-secondary p-4 rounded-lg sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <FileClock className="h-5 w-5 flex-shrink-0 text-bambu-green" />
            <h4 className="text-base font-semibold text-gray-900 dark:text-white">
              {t('settings.swapmod.sequenceEditor', 'Sequence editor')}
            </h4>
          </div>
          <p className="mt-1 text-sm text-bambu-gray">
            {t(
              'settings.swapmod.sequenceSafety',
              'Candidate versions remain inactive until a separate operator review and configuration change.',
            )}
          </p>
        </div>
        <div className="inline-flex w-full rounded-lg border border-bambu-dark-tertiary bg-bambu-dark p-1 sm:w-auto">
          {STEP_OPTIONS.map((option) => (
            <button
              key={option.step}
              type="button"
              aria-pressed={activeStep === option.step}
              className={`min-h-10 flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors sm:flex-none ${
                activeStep === option.step
                  ? 'bg-bambu-green text-white'
                  : 'text-bambu-gray hover:bg-bambu-dark-tertiary hover:text-white'
              }`}
              onClick={() => setActiveStep(option.step)}
            >
              {t(`settings.swapmod.${option.label.toLowerCase()}`, option.label)}
            </button>
          ))}
        </div>
      </div>

      {savingBlocked && (
        <div className="flex items-start gap-3 border border-amber-500/40 bg-amber-500/10 p-3 rounded-lg">
          <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-400" />
          <p className="text-sm text-amber-200">
            {t(
              'settings.swapmod.sequenceDisarmRequired',
              'Disarm the direct canary before editing sequences.',
            )}
          </p>
        </div>
      )}

      {sequence && (
        <div className="flex flex-col gap-3 border border-bambu-dark-tertiary bg-bambu-dark-secondary p-4 rounded-lg sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-gray-900 dark:text-white">
              {activeStep === 'RELEASE_PLATE'
                ? t('settings.swapmod.releaseSequence', 'Release sequence')
                : t('settings.swapmod.loadSequence', 'Load sequence')}
            </p>
            <p className="mt-1 break-all font-mono text-xs text-bambu-gray">
              sha256 {shortHash(sequence.base_sha256)}
            </p>
          </div>
          {sequence.integrity_verified ? (
            <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-emerald-500/15 px-2.5 py-1 text-xs font-semibold text-emerald-300">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {t('settings.swapmod.activePinned', 'Active pinned')}
            </span>
          ) : (
            <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-amber-400/15 px-2.5 py-1 text-xs font-semibold text-amber-200">
              <AlertTriangle className="h-3.5 w-3.5" />
              {t('settings.swapmod.unavailable', 'Unavailable')}
            </span>
          )}
        </div>
      )}

      {sequence && !sequence.editable ? (
        <div className="flex items-start gap-3 border border-amber-500/40 bg-amber-500/10 p-4 rounded-lg">
          <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-400" />
          <p className="text-sm text-amber-200">{sequenceErrorMessage(sequence)}</p>
        </div>
      ) : (
        <div className="overflow-hidden border border-bambu-dark-tertiary bg-bambu-dark-secondary rounded-lg">
          <div className="hidden grid-cols-[minmax(180px,1fr)_minmax(120px,180px)_minmax(180px,220px)] gap-4 border-b border-bambu-dark-tertiary bg-bambu-dark px-4 py-3 text-xs font-semibold text-bambu-gray sm:grid">
            <span>{t('settings.swapmod.action', 'Action')}</span>
            <span>{t('settings.swapmod.target', 'Target')}</span>
            <span>{t('settings.swapmod.feedrate', 'Speed (feedrate)')}</span>
          </div>
          {(sequence?.actions ?? []).map((action) => (
            <div
              key={action.action_id}
              className="grid grid-cols-1 gap-3 border-b border-bambu-dark-tertiary px-4 py-3 last:border-b-0 sm:grid-cols-[minmax(180px,1fr)_minmax(120px,180px)_minmax(180px,220px)] sm:items-center sm:gap-4"
            >
              <div className="min-w-0 text-sm font-medium text-gray-900 dark:text-white">{action.label}</div>
              <div className="font-mono text-sm text-bambu-gray">
                <span className="mr-2 text-xs font-sans font-semibold text-bambu-gray sm:hidden">
                  {t('settings.swapmod.target', 'Target')}
                </span>
                {action.target}
              </div>
              <label className="flex min-w-0 items-center gap-2">
                <span className="text-xs font-semibold text-bambu-gray sm:hidden">
                  {t('settings.swapmod.feedrateShort', 'Feedrate')}
                </span>
                <span className="text-sm font-semibold text-bambu-gray">F</span>
                <input
                  type="number"
                  min={editorQuery.data.feedrate_min}
                  max={editorQuery.data.feedrate_max}
                  step={1}
                  aria-label={`${action.label} feedrate`}
                  value={feedrates[action.action_id] ?? ''}
                  disabled={savingBlocked || saveMutation.isPending}
                  onChange={(event) =>
                    setFeedrates((current) => ({
                      ...current,
                      [action.action_id]: event.target.value,
                    }))
                  }
                  className="min-h-10 min-w-0 flex-1 rounded-md border border-bambu-dark-tertiary bg-bambu-dark px-3 py-2 text-sm font-semibold text-gray-900 outline-none focus:border-bambu-green focus:ring-1 focus:ring-bambu-green disabled:cursor-not-allowed disabled:opacity-60 dark:text-white"
                />
                <span className="whitespace-nowrap text-xs text-bambu-gray">mm/min</span>
              </label>
            </div>
          ))}
        </div>
      )}

      {savedCandidate && savedCandidate.step === activeStep && (
        <div className="flex flex-col gap-3 border border-amber-500/40 bg-amber-500/10 p-4 rounded-lg sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="break-all text-sm font-semibold text-amber-100">{savedCandidate.version_id}</p>
            <p className="mt-1 break-all font-mono text-xs text-amber-200/80">
              sha256 {shortHash(savedCandidate.sha256)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-amber-400/15 px-2.5 py-1 text-xs font-semibold text-amber-200">
              {t('settings.swapmod.pendingReview', 'Pending review')}
            </span>
            <span className="rounded-full bg-bambu-dark-tertiary px-2.5 py-1 text-xs font-semibold text-bambu-gray">
              {t('settings.swapmod.notActive', 'Not active')}
            </span>
          </div>
        </div>
      )}

      {sequence?.editable && (
        <div className="flex flex-col gap-3 border border-bambu-dark-tertiary bg-bambu-dark-secondary p-4 rounded-lg sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs leading-5 text-bambu-gray">
            {t(
              'settings.swapmod.sequenceCandidateOnly',
              'Saving writes a new candidate and audit manifest. The active pinned sequence is unchanged.',
            )}
          </p>
          <div className="flex w-full flex-col-reverse gap-2 sm:w-auto sm:flex-row">
            <Button
              type="button"
              variant="secondary"
              onClick={resetFeedrates}
              disabled={!hasChanges || saveMutation.isPending}
            >
              <RotateCcw className="h-4 w-4" />
              {t('common.reset', 'Reset')}
            </Button>
            <Button type="button" onClick={saveCandidate} disabled={!canSave}>
              {saveMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {t('settings.swapmod.saveCandidate', 'Save candidate version')}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
