import { afterEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
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
};

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
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it.each([
    { reason: 'canary disabled', status: { enabled: false, allow_real_commands: false }, context: {}, queriesStatus: true },
    { reason: 'real commands disabled', status: { enabled: true, allow_real_commands: false }, context: {}, queriesStatus: true },
    { reason: 'printer disconnected', status: { enabled: true, allow_real_commands: true }, context: { isConnected: false }, queriesStatus: false },
    { reason: 'control permission missing', status: { enabled: true, allow_real_commands: true }, context: { canControl: false }, queriesStatus: false },
    { reason: 'printer is not A1 Mini', status: { enabled: true, allow_real_commands: true }, context: { isA1Mini: false }, queriesStatus: false },
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
    const cycle = { cycle_key: cycleKey } as SwapmodCycle;

    vi.spyOn(Date, 'now').mockReturnValue(1700000000000);
    vi.spyOn(swapmodApi, 'getCanaryStatus').mockResolvedValue(canaryStatus);
    const createCycle = vi.spyOn(swapmodApi, 'createCycle').mockResolvedValue(cycle);
    const confirmationPreview = vi
      .spyOn(swapmodApi, 'confirmationPreview')
      .mockResolvedValue(preview);
    const transportStep = vi.spyOn(swapmodApi, 'transportStep').mockResolvedValue(cycle);
    const verify = vi.spyOn(swapmodApi, 'verify').mockResolvedValue(cycle);

    renderControl();

    await user.click(await screen.findByRole('button', { name: 'Plate change (SwapMod)' }));
    expect(screen.getByTestId('card-swapmod-plate-change')).toHaveAttribute(
      'id',
      'card-swapmod-plate-change-7',
    );

    await waitFor(() => {
      expect(createCycle).toHaveBeenCalledWith({
        triggerKey: `${cycleKey}-trigger`,
        cycleKey,
        printerId: printer.id,
      });
    });
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
      await screen.findByText(/Cycle ended in MANUAL_REVIEW/),
    ).toBeInTheDocument();
  });
});
