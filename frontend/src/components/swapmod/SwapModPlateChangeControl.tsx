import { useMemo, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { RefreshCw, AlertTriangle, CheckCircle, X } from 'lucide-react';
import { swapmodApi } from '../../api/client';
import type { Printer, SwapmodStep, SwapmodConfirmationPreview, SwapmodCycle } from '../../api/client';

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

export function SwapModPlateChangeControl({ printer }: { printer: Printer }) {
  const { t } = useTranslation();
  const [phase, setPhase] = useState<Phase>('idle');
  const [cycleKey, setCycleKey] = useState<string | null>(null);
  const [preview, setPreview] = useState<SwapmodConfirmationPreview | null>(null);
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  const canaryStatus = useQuery({
    queryKey: ['swapmod-canary-status'],
    queryFn: () => swapmodApi.getCanaryStatus(),
    refetchInterval: 15000,
  });

  const armed = !!canaryStatus.data?.enabled && !!canaryStatus.data?.allow_real_commands;

  const allChecked = useMemo(
    () => !!preview && preview.checklist_fields.length > 0 && preview.checklist_fields.every((f) => checks[f]),
    [preview, checks],
  );

  const reset = () => {
    setPhase('idle');
    setCycleKey(null);
    setPreview(null);
    setChecks({});
    setError(null);
  };

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
      await swapmodApi.createCycle({ triggerKey: `${key}-trigger`, cycleKey: key, printerId: printer.id });
      return key;
    },
    onSuccess: async (key) => {
      setCycleKey(key);
      await openConfirm(key, 'RELEASE_PLATE', 'confirm-release');
    },
    onError: (e: Error) => setError(e.message),
  });

  const sendStep = useMutation({
    mutationFn: (step: SwapmodStep) => {
      if (!cycleKey || !preview?.required_operator_approval_phrase) {
        throw new Error(t('swapmod.control.noPreview', 'Confirmation phrase not loaded.'));
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
    onSuccess: (_cycle: SwapmodCycle, step) => {
      setPhase(step === 'RELEASE_PLATE' ? 'verify-release' : 'verify-load');
    },
    onError: (e: Error) => setError(e.message),
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
    onSuccess: async ({ step, result }) => {
      if (result === 'fail') {
        setPhase('manual-review');
        return;
      }
      if (step === 'RELEASE_PLATE') {
        if (cycleKey) await openConfirm(cycleKey, 'LOAD_NEXT_PLATE', 'confirm-load');
      } else {
        setPhase('done');
      }
    },
    onError: (e: Error) => setError(e.message),
  });

  // The control only appears while the canary is armed for a supervised window.
  if (!armed) return null;

  const busy = startCycle.isPending || sendStep.isPending || sendVerify.isPending;

  return (
    <div
      id="card-swapmod-plate-change"
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
        <div className="mb-2 rounded border border-red-500/40 bg-red-500/10 px-2 py-1 text-xs text-red-400">
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
            {t('swapmod.control.manualReview', 'Cycle ended in MANUAL_REVIEW. Inspect the printer before retrying.')}
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-lg border border-bambu-dark-tertiary bg-bambu-dark-secondary p-5">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <div className="text-xs font-semibold text-yellow-500">
                  {printer.name} · {t('swapmod.control.supervised', 'supervised actuation')}
                </div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
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
                  {field}
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
