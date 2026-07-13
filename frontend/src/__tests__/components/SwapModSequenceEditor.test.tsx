import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { swapmodApi } from '../../api/client';
import type { SwapmodSequenceEditorStatus } from '../../api/client';
import { SwapModSequenceEditor } from '../../components/swapmod/SwapModSequenceEditor';

const showToast = vi.fn();

vi.mock('../../contexts/ToastContext', () => ({
  useToast: () => ({ showToast }),
}));

const enabledStatus: SwapmodSequenceEditorStatus = {
  enabled: true,
  direct_canary_armed: false,
  feedrate_min: 1,
  feedrate_max: 30000,
  activation_supported: false,
  sequences: [
    {
      step: 'RELEASE_PLATE',
      configured: true,
      integrity_verified: true,
      editable: true,
      base_sha256: 'a'.repeat(64),
      error_code: null,
      actions: [
        { action_id: 'release-001-a1', label: 'Release action 1', target: 'X-14', feedrate: 5000 },
        { action_id: 'release-002-a2', label: 'Release action 2', target: 'Y182', feedrate: 10000 },
      ],
      latest_candidate: null,
    },
    {
      step: 'LOAD_NEXT_PLATE',
      configured: true,
      integrity_verified: true,
      editable: true,
      base_sha256: 'b'.repeat(64),
      error_code: null,
      actions: [
        { action_id: 'load-001-b1', label: 'Load action 1', target: 'Y180', feedrate: 2000 },
      ],
      latest_candidate: null,
    },
  ],
};

function renderEditor() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <SwapModSequenceEditor />
    </QueryClientProvider>,
  );
}

describe('SwapModSequenceEditor', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    showToast.mockReset();
  });

  it('stays read-only while the server feature flag is disabled', async () => {
    vi.spyOn(swapmodApi, 'getSequenceEditorStatus').mockResolvedValue({
      ...enabledStatus,
      enabled: false,
      sequences: enabledStatus.sequences.map((sequence) => ({ ...sequence, editable: false, actions: [] })),
    });

    renderEditor();

    expect(await screen.findByText('Sequence editor is disabled.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save candidate version' })).not.toBeInTheDocument();
  });

  it('shows structured targets and feedrates without raw sequence content', async () => {
    vi.spyOn(swapmodApi, 'getSequenceEditorStatus').mockResolvedValue(enabledStatus);

    renderEditor();

    expect(await screen.findByText('Release action 1')).toBeInTheDocument();
    expect(screen.getByText('X-14')).toBeInTheDocument();
    expect(screen.getByLabelText('Release action 1 feedrate')).toHaveValue(5000);
    expect(screen.getByText(`sha256 ${'a'.repeat(12)}`)).toBeInTheDocument();
    expect(screen.queryByText(/G1 X-14/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\.gcode/)).not.toBeInTheDocument();
  });

  it('does not label an unverified sequence as active pinned', async () => {
    vi.spyOn(swapmodApi, 'getSequenceEditorStatus').mockResolvedValue({
      ...enabledStatus,
      sequences: enabledStatus.sequences.map((sequence) =>
        sequence.step === 'RELEASE_PLATE'
          ? {
              ...sequence,
              configured: false,
              integrity_verified: false,
              editable: false,
              base_sha256: null,
              actions: [],
            }
          : sequence,
      ),
    });

    renderEditor();

    expect(await screen.findByText('Unavailable')).toBeInTheDocument();
    expect(screen.queryByText('Active pinned')).not.toBeInTheDocument();
  });

  it('saves every server action as a new inactive pending-review candidate', async () => {
    const user = userEvent.setup();
    vi.spyOn(swapmodApi, 'getSequenceEditorStatus').mockResolvedValue(enabledStatus);
    const save = vi.spyOn(swapmodApi, 'createSequenceCandidate').mockResolvedValue({
      version_id: 'a1mini-release-20260714t010203000000z-abc123',
      step: 'RELEASE_PLATE',
      base_sha256: 'a'.repeat(64),
      sha256: 'c'.repeat(64),
      created_at: '2026-07-14T01:02:03Z',
      created_by: 'operator',
      review_status: 'PENDING_REVIEW',
      active: false,
      activation_supported: false,
      operator_review_required: true,
      actions: enabledStatus.sequences[0].actions,
    });
    renderEditor();

    const input = await screen.findByLabelText('Release action 1 feedrate');
    await user.clear(input);
    await user.type(input, '5250');
    await user.click(screen.getByRole('button', { name: 'Save candidate version' }));

    await waitFor(() => {
      expect(save).toHaveBeenCalledWith({
        step: 'RELEASE_PLATE',
        base_sha256: 'a'.repeat(64),
        actions: [
          { action_id: 'release-001-a1', feedrate: 5250 },
          { action_id: 'release-002-a2', feedrate: 10000 },
        ],
      });
    });
    expect(await screen.findByText('Pending review')).toBeInTheDocument();
    expect(screen.getByText('Not active')).toBeInTheDocument();
    expect(showToast).toHaveBeenCalledWith('Candidate version saved for review.', 'success');

    await user.click(screen.getByRole('button', { name: 'Load' }));
    await user.click(screen.getByRole('button', { name: 'Release' }));
    expect(screen.getByText('a1mini-release-20260714t010203000000z-abc123')).toBeInTheDocument();
  });

  it('blocks saving while the direct canary is armed', async () => {
    vi.spyOn(swapmodApi, 'getSequenceEditorStatus').mockResolvedValue({
      ...enabledStatus,
      direct_canary_armed: true,
    });
    const save = vi.spyOn(swapmodApi, 'createSequenceCandidate');

    renderEditor();

    expect(await screen.findByText('Disarm the direct canary before editing sequences.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save candidate version' })).toBeDisabled();
    expect(save).not.toHaveBeenCalled();
  });

  it('rejects out-of-range feedrates before calling the API', async () => {
    const user = userEvent.setup();
    vi.spyOn(swapmodApi, 'getSequenceEditorStatus').mockResolvedValue(enabledStatus);
    const save = vi.spyOn(swapmodApi, 'createSequenceCandidate');
    renderEditor();

    const input = await screen.findByLabelText('Release action 1 feedrate');
    await user.clear(input);
    await user.type(input, '30001');

    expect(screen.getByRole('button', { name: 'Save candidate version' })).toBeDisabled();
    expect(save).not.toHaveBeenCalled();
  });

  it('switches between release and load action sets', async () => {
    const user = userEvent.setup();
    vi.spyOn(swapmodApi, 'getSequenceEditorStatus').mockResolvedValue(enabledStatus);

    renderEditor();
    await screen.findByText('Release action 1');
    await user.click(screen.getByRole('button', { name: 'Load' }));

    expect(screen.getByText('Load action 1')).toBeInTheDocument();
    expect(screen.getByText('Y180')).toBeInTheDocument();
    expect(screen.queryByText('Release action 1')).not.toBeInTheDocument();
  });
});
