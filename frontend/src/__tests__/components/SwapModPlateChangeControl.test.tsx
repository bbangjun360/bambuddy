import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { SwapModPlateChangeControl } from '../../components/swapmod/SwapModPlateChangeControl';
import { swapmodApi } from '../../api/client';
import type {
  Printer,
  SwapmodCanaryStatus,
  SwapmodConfirmationPreview,
  SwapmodCycle,
} from '../../api/client';

const printer = {
  id: 7,
  name: 'Synthetic A1 Mini',
} as Printer;

const checklistFields = [
  'operator_present',
  'printer_visible',
  'emergency_stop_ready',
  'power_cutoff_ready',
  'a1_mini_confirmed',
  'swapmod_hardware_installed',
  'bed_area_clear',
  'plate_stack_ready',
  'no_other_job_running',
  'dry_run_gate_reviewed',
];

const canaryStatus: SwapmodCanaryStatus = {
  mode: 'a1_mini_direct_canary',
  enabled: true,
  allow_real_commands: true,
  release_sequence_configured: true,
  load_sequence_configured: true,
  single_printer_only: true,
  human_confirmation_required: true,
  target_printer_id: printer.id,
};

function cycle(overrides: Partial<SwapmodCycle> = {}): SwapmodCycle {
  return {
    id: 1,
    cycle_key: 'swapmod-ui-7-1700000000000',
    printer_id: printer.id,
    source_print_run_id: null,
    state: 'READY_TO_RELEASE',
    dry_run: false,
    ready_for_next_print: false,
    manual_review_required: false,
    retry_available: false,
    blocked_reason: null,
    current_step: 'RELEASE_PLATE',
    retry_step: null,
    verification_source: null,
    verification_result: null,
    note: null,
    seen_event_ids: [],
    transition_log: [],
    transition_count: 1,
    created_at: null,
    updated_at: null,
    ...overrides,
  };
}

async function checkEveryItem(user: ReturnType<typeof userEvent.setup>) {
  const checkboxes = await screen.findAllByRole('checkbox');
  for (const checkbox of checkboxes) await user.click(checkbox);
}

interface ControlContext {
  isConnected: boolean;
  canControl: boolean;
  isA1Mini: boolean;
}

function renderControl(overrides: Partial<ControlContext> = {}) {
  const context: ControlContext = {
    isConnected: true,
    canControl: true,
    isA1Mini: true,
    ...overrides,
  };
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <SwapModPlateChangeControl printer={printer} {...context} />
    </QueryClientProvider>,
  );

  return { ...result, queryClient };
}

describe('SwapModPlateChangeControl', () => {
  beforeEach(() => {
    vi.spyOn(swapmodApi, 'listCycles').mockResolvedValue({ cycles: [] });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it.each([
    { reason: 'canary disabled', status: { enabled: false, allow_real_commands: false }, context: {}, queriesStatus: true },
    { reason: 'real commands disabled', status: { enabled: true, allow_real_commands: false }, context: {}, queriesStatus: true },
    { reason: 'printer disconnected', status: { enabled: true, allow_real_commands: true }, context: { isConnected: false }, queriesStatus: false },
    { reason: 'control permission missing', status: { enabled: true, allow_real_commands: true }, context: { canControl: false }, queriesStatus: false },
    { reason: 'printer is not A1 Mini', status: { enabled: true, allow_real_commands: true }, context: { isA1Mini: false }, queriesStatus: false },
    { reason: 'printer is not the named canary', status: { enabled: true, allow_real_commands: true, target_printer_id: 99 }, context: {}, queriesStatus: true },
  ])('stays hidden when $reason', async ({ status, context, queriesStatus }) => {
    const getStatus = vi.spyOn(swapmodApi, 'getCanaryStatus').mockResolvedValue({
      ...canaryStatus,
      ...status,
    });
    const createCycle = vi.spyOn(swapmodApi, 'createCycle');

    const { container, queryClient } = renderControl(context);

    if (queriesStatus) {
      await waitFor(() => {
        expect(getStatus).toHaveBeenCalledTimes(1);
        expect(queryClient.getQueryData(['swapmod-canary-status'])).toMatchObject({
          ...canaryStatus,
          ...status,
        });
        expect(container).toBeEmptyDOMElement();
      });
    } else {
      expect(getStatus).not.toHaveBeenCalled();
      expect(container).toBeEmptyDOMElement();
    }
    expect(createCycle).not.toHaveBeenCalled();
  });

  it('requires every server checklist item and uses the read-only phrase before sending', async () => {
    const user = userEvent.setup();
    const cycleKey = 'swapmod-ui-7-1700000000000';
    const phrase = `CONFIRM_A1_MINI_DIRECT_PLATE_CHANGE 7 ${cycleKey} RELEASE_PLATE release-sha`;
    const preview: SwapmodConfirmationPreview = {
      printer_id: printer.id,
      cycle_key: cycleKey,
      step: 'RELEASE_PLATE',
      sequence_configured: true,
      sequence_sha256: 'release-sha',
      required_operator_approval_phrase: phrase,
      checklist_fields: checklistFields,
    };
    const currentCycle = cycle({ cycle_key: cycleKey });

    vi.spyOn(Date, 'now').mockReturnValue(1700000000000);
    vi.spyOn(swapmodApi, 'getCanaryStatus').mockResolvedValue(canaryStatus);
    const createCycle = vi.spyOn(swapmodApi, 'createCycle').mockResolvedValue(currentCycle);
    const confirmationPreview = vi
      .spyOn(swapmodApi, 'confirmationPreview')
      .mockResolvedValue(preview);
    const transportStep = vi.spyOn(swapmodApi, 'transportStep').mockResolvedValue({
      ...currentCycle,
      state: 'VERIFY_RELEASED',
      direct_canary_status: 'COMMAND_SENT',
      real_command_sent: true,
      printer_command_sent: true,
    });
    const verify = vi.spyOn(swapmodApi, 'verify').mockResolvedValue(
      cycle({ cycle_key: cycleKey, state: 'MANUAL_REVIEW_REQUIRED', manual_review_required: true }),
    );

    renderControl();

    await user.click(await screen.findByRole('button', { name: 'Plate change (SwapMod)' }));
    expect(screen.getByTestId('card-swapmod-plate-change')).toHaveAttribute(
      'id',
      'card-swapmod-plate-change-7',
    );

    expect(createCycle).not.toHaveBeenCalled();
    expect(confirmationPreview).toHaveBeenCalledWith(printer.id, cycleKey, 'RELEASE_PLATE');
    expect(await screen.findByText(phrase)).toBeInTheDocument();
    expect(screen.queryByDisplayValue(phrase)).not.toBeInTheDocument();

    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(10);
    const confirm = screen.getByRole('button', { name: 'Confirm & send RELEASE_PLATE' });
    expect(confirm).toBeDisabled();

    for (const checkbox of checkboxes.slice(0, -1)) {
      await user.click(checkbox);
    }
    expect(confirm).toBeDisabled();
    expect(transportStep).not.toHaveBeenCalled();

    await user.click(checkboxes.at(-1)!);
    expect(confirm).toBeEnabled();
    await user.click(confirm);

    const checklist = Object.fromEntries(checklistFields.map((field) => [field, true]));
    await waitFor(() => {
      expect(createCycle).toHaveBeenCalledWith({
        triggerKey: `${cycleKey}-trigger`,
        cycleKey,
        printerId: printer.id,
      });
      expect(transportStep).toHaveBeenCalledWith(cycleKey, {
        canary_key: `${cycleKey}-release_plate`,
        printer_id: printer.id,
        step: 'RELEASE_PLATE',
        operator_approved: true,
        operator_approval_phrase: phrase,
        checklist,
      });
    });

    await user.click(
      await screen.findByRole('button', { name: 'Failed / stop' }),
    );
    await waitFor(() => {
      expect(verify).toHaveBeenCalledWith(cycleKey, {
        verification_key: `${cycleKey}-release_plate-verify`,
        verification_source: 'manual',
        verification_result: 'fail',
        note: 'operator confirmed via printer-card control',
      });
    });
    expect(
      await screen.findByText(/MANUAL_REVIEW/),
    ).toBeInTheDocument();
  });

  it('fails closed when the transport reports that no command was sent', async () => {
    const user = userEvent.setup();
    const cycleKey = 'swapmod-ui-7-1700000000000';
    vi.spyOn(Date, 'now').mockReturnValue(1700000000000);
    vi.spyOn(swapmodApi, 'getCanaryStatus').mockResolvedValue(canaryStatus);
    vi.spyOn(swapmodApi, 'createCycle').mockResolvedValue(cycle({ cycle_key: cycleKey }));
    vi.spyOn(swapmodApi, 'confirmationPreview').mockResolvedValue({
      printer_id: printer.id,
      cycle_key: cycleKey,
      step: 'RELEASE_PLATE',
      sequence_configured: true,
      sequence_sha256: 'release-sha',
      required_operator_approval_phrase: 'server phrase',
      checklist_fields: checklistFields,
    });
    vi.spyOn(swapmodApi, 'transportStep').mockResolvedValue({
      ...cycle({
        cycle_key: cycleKey,
        state: 'BLOCKED_TIMEOUT',
        manual_review_required: true,
        blocked_reason: 'command send failed',
      }),
      direct_canary_status: 'COMMAND_FAILED',
      real_command_sent: false,
      printer_command_sent: false,
    });
    const verify = vi.spyOn(swapmodApi, 'verify');

    renderControl();
    await user.click(await screen.findByRole('button', { name: 'Plate change (SwapMod)' }));
    await checkEveryItem(user);
    await user.click(screen.getByRole('button', { name: 'Confirm & send RELEASE_PLATE' }));

    expect(await screen.findByText(/MANUAL_REVIEW/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Verified OK' })).not.toBeInTheDocument();
    expect(verify).not.toHaveBeenCalled();
  });

  it('fails closed when the transport response is uncertain', async () => {
    const user = userEvent.setup();
    const cycleKey = 'swapmod-ui-7-1700000000000';
    vi.spyOn(Date, 'now').mockReturnValue(1700000000000);
    vi.spyOn(swapmodApi, 'getCanaryStatus').mockResolvedValue(canaryStatus);
    vi.spyOn(swapmodApi, 'createCycle').mockResolvedValue(cycle({ cycle_key: cycleKey }));
    vi.spyOn(swapmodApi, 'confirmationPreview').mockResolvedValue({
      printer_id: printer.id,
      cycle_key: cycleKey,
      step: 'RELEASE_PLATE',
      sequence_configured: true,
      sequence_sha256: 'release-sha',
      required_operator_approval_phrase: 'server phrase',
      checklist_fields: checklistFields,
    });
    vi.spyOn(swapmodApi, 'transportStep').mockRejectedValue(new Error('connection lost'));
    const verify = vi.spyOn(swapmodApi, 'verify');

    renderControl();
    await user.click(await screen.findByRole('button', { name: 'Plate change (SwapMod)' }));
    await checkEveryItem(user);
    await user.click(screen.getByRole('button', { name: 'Confirm & send RELEASE_PLATE' }));

    expect(await screen.findByText(/MANUAL_REVIEW/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirm & send RELEASE_PLATE' })).not.toBeInTheDocument();
    expect(verify).not.toHaveBeenCalled();
  });

  it('fails closed when the verification response is uncertain', async () => {
    const user = userEvent.setup();
    const cycleKey = 'swapmod-ui-7-1700000000000';
    vi.spyOn(Date, 'now').mockReturnValue(1700000000000);
    vi.spyOn(swapmodApi, 'getCanaryStatus').mockResolvedValue(canaryStatus);
    vi.spyOn(swapmodApi, 'createCycle').mockResolvedValue(cycle({ cycle_key: cycleKey }));
    vi.spyOn(swapmodApi, 'confirmationPreview').mockResolvedValue({
      printer_id: printer.id,
      cycle_key: cycleKey,
      step: 'RELEASE_PLATE',
      sequence_configured: true,
      sequence_sha256: 'release-sha',
      required_operator_approval_phrase: 'server phrase',
      checklist_fields: checklistFields,
    });
    vi.spyOn(swapmodApi, 'transportStep').mockResolvedValue({
      ...cycle({ cycle_key: cycleKey, state: 'VERIFY_RELEASED' }),
      direct_canary_status: 'COMMAND_SENT',
      real_command_sent: true,
      printer_command_sent: true,
    });
    const verify = vi.spyOn(swapmodApi, 'verify').mockRejectedValue(new Error('verification response lost'));

    renderControl();
    await user.click(await screen.findByRole('button', { name: 'Plate change (SwapMod)' }));
    await checkEveryItem(user);
    await user.click(screen.getByRole('button', { name: 'Confirm & send RELEASE_PLATE' }));
    await user.click(await screen.findByRole('button', { name: 'Verified OK' }));

    expect(await screen.findByText(/MANUAL_REVIEW/)).toBeInTheDocument();
    expect(screen.getByText('verification response lost')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Verified OK' })).not.toBeInTheDocument();
    expect(verify).toHaveBeenCalledTimes(1);
  });

  it('does not load the next plate after an unexpected verification state', async () => {
    const user = userEvent.setup();
    const cycleKey = 'swapmod-ui-7-1700000000000';
    vi.spyOn(Date, 'now').mockReturnValue(1700000000000);
    vi.spyOn(swapmodApi, 'getCanaryStatus').mockResolvedValue(canaryStatus);
    vi.spyOn(swapmodApi, 'createCycle').mockResolvedValue(cycle({ cycle_key: cycleKey }));
    const preview = vi.spyOn(swapmodApi, 'confirmationPreview').mockResolvedValue({
      printer_id: printer.id,
      cycle_key: cycleKey,
      step: 'RELEASE_PLATE',
      sequence_configured: true,
      sequence_sha256: 'release-sha',
      required_operator_approval_phrase: 'server phrase',
      checklist_fields: checklistFields,
    });
    vi.spyOn(swapmodApi, 'transportStep').mockResolvedValue({
      ...cycle({ cycle_key: cycleKey, state: 'VERIFY_RELEASED' }),
      direct_canary_status: 'COMMAND_SENT',
      real_command_sent: true,
      printer_command_sent: true,
    });
    vi.spyOn(swapmodApi, 'verify').mockResolvedValue(
      cycle({
        cycle_key: cycleKey,
        state: 'BLOCKED_UNKNOWN_STATE',
        manual_review_required: true,
        blocked_reason: 'unexpected state',
      }),
    );

    renderControl();
    await user.click(await screen.findByRole('button', { name: 'Plate change (SwapMod)' }));
    await checkEveryItem(user);
    await user.click(screen.getByRole('button', { name: 'Confirm & send RELEASE_PLATE' }));
    await user.click(await screen.findByRole('button', { name: 'Verified OK' }));

    expect(await screen.findByText(/MANUAL_REVIEW/)).toBeInTheDocument();
    expect(preview).toHaveBeenCalledTimes(1);
  });

  it('clears a checked confirmation when the canary is disarmed', async () => {
    const user = userEvent.setup();
    vi.spyOn(swapmodApi, 'getCanaryStatus').mockResolvedValue(canaryStatus);
    vi.spyOn(swapmodApi, 'createCycle').mockResolvedValue(cycle());
    vi.spyOn(swapmodApi, 'confirmationPreview').mockResolvedValue({
      printer_id: printer.id,
      cycle_key: cycle().cycle_key,
      step: 'RELEASE_PLATE',
      sequence_configured: true,
      sequence_sha256: 'release-sha',
      required_operator_approval_phrase: 'server phrase',
      checklist_fields: checklistFields,
    });

    const { queryClient } = renderControl();
    await user.click(await screen.findByRole('button', { name: 'Plate change (SwapMod)' }));
    await checkEveryItem(user);
    expect(screen.getByRole('button', { name: 'Confirm & send RELEASE_PLATE' })).toBeEnabled();

    act(() => queryClient.setQueryData(['swapmod-canary-status'], { ...canaryStatus, enabled: false }));
    await waitFor(() => expect(screen.queryByTestId('card-swapmod-plate-change')).not.toBeInTheDocument());
    act(() => queryClient.setQueryData(['swapmod-canary-status'], canaryStatus));

    expect(await screen.findByRole('button', { name: 'Plate change (SwapMod)' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirm & send RELEASE_PLATE' })).not.toBeInTheDocument();
  });

  it('does not offer a new action while another unresolved cycle exists', async () => {
    vi.spyOn(swapmodApi, 'getCanaryStatus').mockResolvedValue(canaryStatus);
    vi.mocked(swapmodApi.listCycles).mockResolvedValue({
      cycles: [cycle({ cycle_key: 'existing-cycle', state: 'VERIFY_RELEASED' })],
    });
    const createCycle = vi.spyOn(swapmodApi, 'createCycle');

    renderControl();

    expect(await screen.findByText(/existing SwapMod cycle requires review/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Plate change (SwapMod)' })).not.toBeInTheDocument();
    expect(createCycle).not.toHaveBeenCalled();
  });
});
