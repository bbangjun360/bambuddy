import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { RefreshCw, AlertTriangle, CheckCircle, X } from 'lucide-react';
import { swapmodApi } from '../../api/client';
import type { Printer, SwapmodStep, SwapmodConfirmationPreview } from '../../api/client';

/**
 * WP-110 slice 4 (DRAFT). Supervised SwapMod plate-change control rendered on a
 * connected printer card. It only appears while the canary is armed, and every
 * motion goes through the existing gated endpoints: the operator ticks the full
 * checklist and the server-provided confirmation phrase is shown read-only. The
 * UI never fabricates the checklist or the phrase.
 */

type Phase =
  | 'idle'
  | 'confirm-release'
  | 'verify-release'
  | 'confirm-load'
  | 'verify-load'
  | 'done'
  | 'manual-review';

interface SwapModPlateChangeControlProps {
  printer: Printer;
  isConnected: boolean;
  canControl: boolean;
  isA1Mini: boolean;
}

export function SwapModPlateChangeControl({
  printer,
  isConnected,
  canControl,
  isA1Mini,
}: SwapModPlateChangeControlProps) {
  const { t } = useTranslation();
  const [phase, setPhase] = useState<Phase>('idle');
  const [cycleKey, setCycleKey] = useState<string | null>(null);
  const [preview, setPreview] = useState<SwapmodConfirmationPreview | null>(null);
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const eligible = isConnected && canControl && isA1Mini;

  const canaryStatus = useQuery({
    queryKey: ['swapmod-canary-status'],
    queryFn: () => swapmodApi.getCanaryStatus(),
    refetchInterval: 15000,
    enabled: eligible,
  });

  const armed =
    eligible &&
    !!canaryStatus.data?.enabled &&
    !!canaryStatus.data?.allow_real_commands &&
    canaryStatus.data?.target_printer_id === printer.id;

  const recentCycles = useQuery({
    queryKey: ['swapmod-cycles', 'plate-change-control', printer.id],
    queryFn: () => swapmodApi.listCycles({ printerId: printer.id, limit: 50 }),
    refetchInterval: 15000,
    enabled: armed,
  });

  const unresolvedCycle = useMemo(() => {
    for (const candidate of recentCycles.data?.cycles ?? []) {
      if (candidate.state === 'READY_FOR_NEXT_PRINT') break;
      if (candidate.cycle_key !== cycleKey) return candidate;
    }
    return null;
  }, [cycleKey, recentCycles.data]);

  const allChecked = useMemo(
    () => !!preview && preview.checklist_fields.length > 0 && preview.checklist_fields.every((f) => checks[f]),
    [preview, checks],
  );

  const reset = async () => {
    await recentCycles.refetch();
    setPhase('idle');
    setCycleKey(null);
    setPreview(null);
    setChecks({});
    setError(null);
  };

  useEffect(() => {
    if (armed) return;
    setPhase('idle');
    setCycleKey(null);
    setPreview(null);
    setChecks({});
    setError(null);
  }, [armed]);

  const openConfirm = async (key: string, step: SwapmodStep, nextPhase: Phase) => {
    setError(null);
    const p = await swapmodApi.confirmationPreview(printer.id, key, step);
    setPreview(p);
    setChecks({});
    setPhase(nextPhase);
  };

  const startCycle = useMutation({
    mutationFn: async () => {
      const key = `swapmod-ui-${printer.id}-${Date.now()}`;
      const confirmation = await swapmodApi.confirmationPreview(printer.id, key, 'RELEASE_PLATE');
      return { key, confirmation };
    },
    onSuccess: ({ key, confirmation }) => {
      setCycleKey(key);
      setPreview(confirmation);
      setChecks({});
      setPhase('confirm-release');
    },
    onError: (e: Error) => setError(e.message),
  });

  const sendStep = useMutation({
    mutationFn: async (step: SwapmodStep) => {
      if (!cycleKey || !preview?.required_operator_approval_phrase) {
        throw new Error(t('swapmod.control.noPreview', 'Confirmation phrase not loaded.'));
      }
      if (step === 'RELEASE_PLATE') {
        const created = await swapmodApi.createCycle({
          triggerKey: `${cycleKey}-trigger`,
          cycleKey,
          printerId: printer.id,
        });
        if (
          created.cycle_key !== cycleKey ||
          created.state !== 'READY_TO_RELEASE' ||
          created.manual_review_required
        ) {
          throw new Error(t('swapmod.control.cycleNotReady', 'The SwapMod cycle was not created in a safe ready state.'));
        }
      }
      const checklist: Record<string, boolean> = {};
      for (const f of preview.checklist_fields) checklist[f] = true;
      return swapmodApi.transportStep(cycleKey, {
        canary_key: `${cycleKey}-${step.toLowerCase()}`,
        printer_id: printer.id,
        step,
        operator_approved: true,
        operator_approval_phrase: preview.required_operator_approval_phrase,
        checklist,
      });
    },
    onSuccess: (cycle, step) => {
      const expectedState = step === 'RELEASE_PLATE' ? 'VERIFY_RELEASED' : 'VERIFY_LOADED';
      if (
        cycle.direct_canary_status !== 'COMMAND_SENT' ||
        !cycle.real_command_sent ||
        !cycle.printer_command_sent ||
        cycle.manual_review_required ||
        cycle.state !== expectedState
      ) {
        setError(
          cycle.blocked_reason ??
            t('swapmod.control.transportFailed', 'The command was not confirmed as sent. Manual review is required.'),
        );
        setPreview(null);
        setChecks({});
        setPhase('manual-review');
        void recentCycles.refetch();
        return;
      }
      setPhase(step === 'RELEASE_PLATE' ? 'verify-release' : 'verify-load');
    },
    onError: (e: Error) => {
      setError(e.message);
      setPreview(null);
      setChecks({});
      setPhase('manual-review');
      void recentCycles.refetch();
    },
  });

  const sendVerify = useMutation({
    mutationFn: ({ step, result }: { step: SwapmodStep; result: 'pass' | 'fail' }) => {
      if (!cycleKey) throw new Error('No active cycle');
      return swapmodApi
        .verify(cycleKey, {
          verification_key: `${cycleKey}-${step.toLowerCase()}-verify`,
          verification_source: 'manual',
          verification_result: result,
          note: 'operator confirmed via printer-card control',
        })
        .then((cycle) => ({ cycle, step, result }));
    },
    onSuccess: async ({ cycle, step, result }) => {
      if (result === 'fail') {
        setPhase('manual-review');
        void recentCycles.refetch();
        return;
      }
      const expectedState = step === 'RELEASE_PLATE' ? 'READY_TO_LOAD' : 'READY_FOR_NEXT_PRINT';
      if (cycle.manual_review_required || cycle.state !== expectedState) {
        setError(
          cycle.blocked_reason ??
            t('swapmod.control.verifyFailed', 'The verification result was not accepted. Manual review is required.'),
        );
        setPhase('manual-review');
        void recentCycles.refetch();
        return;
      }
      if (step === 'RELEASE_PLATE') {
        if (cycleKey) {
          try {
            await openConfirm(cycleKey, 'LOAD_NEXT_PLATE', 'confirm-load');
          } catch (e) {
            setError(e instanceof Error ? e.message : t('swapmod.control.previewFailed', 'Confirmation preview failed.'));
            setPhase('manual-review');
          }
        }
      } else {
        setPhase('done');
        void recentCycles.refetch();
      }
    },
    onError: (e: Error) => {
      setError(e.message);
      setPreview(null);
      setChecks({});
      setPhase('manual-review');
      void recentCycles.refetch();
    },
  });

  // The backend repeats every gate; these checks also keep ineligible cards inert.
  if (!armed) return null;

  if (phase === 'idle' && unresolvedCycle) {
    return (
      <div
        id={`card-swapmod-plate-change-${printer.id}`}
        data-testid="card-swapmod-plate-change"
        role="alert"
        className="mt-3 rounded-lg border border-yellow-500/40 bg-yellow-500/10 p-3 text-sm text-yellow-600 dark:text-yellow-400"
      >
        {t(
          'swapmod.control.unresolvedCycle',
          'An existing SwapMod cycle requires review before another plate change.',
        )}
      </div>
    );
  }

  if (phase === 'idle' && (recentCycles.error || !recentCycles.data)) {
    if (!recentCycles.error) return null;
    return (
      <div
        id={`card-swapmod-plate-change-${printer.id}`}
        data-testid="card-swapmod-plate-change"
        role="alert"
        className="mt-3 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-500"
      >
        {t('swapmod.control.cycleStatusUnavailable', 'SwapMod cycle status is unavailable. Controls are disabled.')}
      </div>
    );
  }

  const busy = startCycle.isPending || sendStep.isPending || sendVerify.isPending;

  return (
    <div
      id={`card-swapmod-plate-change-${printer.id}`}
      data-testid="card-swapmod-plate-change"
      className="mt-3 rounded-lg border border-bambu-dark-tertiary bg-bambu-dark-secondary p-3"
    >
      <div className="flex items-center gap-2 mb-2">
        <RefreshCw className="w-4 h-4 text-bambu-green" />
        <span className="text-sm font-semibold text-gray-900 dark:text-white">
          {t('swapmod.control.title', 'SwapMod plate change')}
        </span>
        <span className="ml-auto inline-flex items-center gap-1 text-xs text-yellow-500">
          <AlertTriangle className="w-3.5 h-3.5" />
          {t('swapmod.control.armed', 'Armed — supervised')}
        </span>
      </div>

      {error && (
        <div role="alert" className="mb-2 rounded border border-red-500/40 bg-red-500/10 px-2 py-1 text-xs text-red-400">
          {error}
        </div>
      )}

      {phase === 'idle' && (
        <button
          onClick={() => startCycle.mutate()}
          disabled={busy}
          className="w-full rounded-lg bg-bambu-green px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {t('swapmod.control.start', 'Plate change (SwapMod)')}
        </button>
      )}

      {(phase === 'verify-release' || phase === 'verify-load') && (
        <div className="space-y-2">
          <p className="text-sm text-gray-900 dark:text-white">
            {phase === 'verify-release'
              ? t('swapmod.control.verifyRelease', 'Did the plate release correctly (ejected, bed clear)?')
              : t('swapmod.control.verifyLoad', 'Did the new plate seat correctly (fixed on the bed)?')}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() =>
                sendVerify.mutate({ step: phase === 'verify-release' ? 'RELEASE_PLATE' : 'LOAD_NEXT_PLATE', result: 'pass' })
              }
              disabled={busy}
              className="flex-1 rounded-lg bg-bambu-green px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {t('swapmod.control.verifyPass', 'Verified OK')}
            </button>
            <button
              onClick={() =>
                sendVerify.mutate({ step: phase === 'verify-release' ? 'RELEASE_PLATE' : 'LOAD_NEXT_PLATE', result: 'fail' })
              }
              disabled={busy}
              className="flex-1 rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {t('swapmod.control.verifyFail', 'Failed / stop')}
            </button>
          </div>
        </div>
      )}

      {phase === 'done' && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-bambu-green">
            <CheckCircle className="w-4 h-4" />
            {t('swapmod.control.done', 'Plate change complete — ready for next print.')}
          </div>
          <button
            onClick={reset}
            className="w-full rounded-lg border border-bambu-dark-tertiary px-3 py-2 text-sm text-bambu-gray"
          >
            {t('swapmod.control.startAnother', 'Start another')}
          </button>
        </div>
      )}

      {phase === 'manual-review' && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-yellow-500">
            <AlertTriangle className="w-4 h-4" />
            {t(
              'swapmod.control.manualReview',
              'Cycle stopped in MANUAL_REVIEW or an unexpected state. Inspect the printer and cycle log before retrying.',
            )}
          </div>
          <button
            onClick={reset}
            className="w-full rounded-lg border border-bambu-dark-tertiary px-3 py-2 text-sm text-bambu-gray"
          >
            {t('swapmod.control.dismiss', 'Dismiss')}
          </button>
        </div>
      )}

      {(phase === 'confirm-release' || phase === 'confirm-load') && preview && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 sm:items-center">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={`swapmod-confirm-title-${printer.id}`}
            className="max-h-[calc(100vh-2rem)] w-full max-w-lg overflow-y-auto rounded-lg border border-bambu-dark-tertiary bg-bambu-dark-secondary p-5"
          >
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <div className="text-xs font-semibold text-yellow-500">
                  {printer.name} · {t('swapmod.control.supervised', 'supervised actuation')}
                </div>
                <h3 id={`swapmod-confirm-title-${printer.id}`} className="text-lg font-bold text-gray-900 dark:text-white">
                  {t('swapmod.control.confirmTitle', 'Confirm')} {preview.step}
                </h3>
                <p className="text-sm text-bambu-gray">
                  {t('swapmod.control.confirmHelp', 'Tick every item after physically checking it. Nothing moves until you confirm.')}
                </p>
              </div>
              <button onClick={reset} aria-label="Cancel" className="p-1 text-bambu-gray hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mb-3 space-y-2">
              {preview.checklist_fields.map((field) => (
                <label key={field} className="flex items-center gap-2 text-sm text-gray-900 dark:text-white">
                  <input
                    type="checkbox"
                    checked={!!checks[field]}
                    onChange={(e) => setChecks((c) => ({ ...c, [field]: e.target.checked }))}
                  />
                  <span className="capitalize">{field.replaceAll('_', ' ')}</span>
                </label>
              ))}
            </div>

            <div className="mb-3 rounded border border-bambu-dark-tertiary bg-bambu-dark p-2">
              <div className="text-xs font-semibold text-bambu-gray">
                {t('swapmod.control.phraseLabel', 'Confirmation phrase (from server, read-only)')}
              </div>
              <div className="break-all text-xs font-semibold text-gray-900 dark:text-white">
                {preview.required_operator_approval_phrase ?? t('swapmod.control.noSequence', 'Sequence not configured')}
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => sendStep.mutate(preview.step as SwapmodStep)}
                disabled={!allChecked || busy || !preview.required_operator_approval_phrase}
                className="flex-1 rounded-lg bg-bambu-green px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {t('swapmod.control.confirmSend', 'Confirm & send')} {preview.step}
              </button>
              <button
                onClick={reset}
                className="rounded-lg border border-bambu-dark-tertiary px-3 py-2 text-sm text-bambu-gray"
              >
                {t('swapmod.control.cancel', 'Cancel')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
