import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

let scenarioQueue: Array<
  | { type: 'ok'; dlBps: number; upBps: number; latMs: number; jitMs: number; city: string }
  | { type: 'error'; message: string }
> = [];

vi.mock('@cloudflare/speedtest', () => {
  return {
    default: class MockSpeedTest {
      onResultsChange?: (arg: any) => void;
      onFinish?: (res: any) => void;
      onError?: (err: any) => void;
      results: any = null;

      play() {
        const next = scenarioQueue.shift();
        setTimeout(() => {
          if (!next) return;
          if (next.type === 'error') {
            this.onError?.(next.message);
            return;
          }
          const finalRes = {
            getDownloadBandwidth: () => next.dlBps,
            getUploadBandwidth: () => next.upBps,
            getUnloadedLatency: () => next.latMs,
            getUnloadedJitter: () => next.jitMs,
            getSummary: () => ({ server: { city: next.city } }),
          };
          this.results = finalRes;
          this.onResultsChange?.({ type: 'download' });
          this.onFinish?.(finalRes);
        }, 5);
      }
      pause() {}
    },
  };
});

vi.mock('../services/api', () => ({
  fetchSummary: vi.fn().mockResolvedValue({ real_measurements_count: 0 }),
  fetchRecentMeasurements: vi.fn().mockResolvedValue([]),
  submitCrowdsourceMeasurement: vi.fn().mockResolvedValue({ is_test: 1 }),
}));

import { CrowdsourceMeasureView } from './CrowdsourceMeasureView';

describe('CrowdsourceMeasureView Speed Test Honesty & Multi-Run Behavior', () => {
  beforeEach(() => {
    scenarioQueue = [];
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('skip trace')));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('starts with "--" (zero fallback values), updates displayed values between Run #1 and Run #2 with IST stamps, and shows zero numbers on failure', async () => {
    scenarioQueue.push(
      { type: 'ok', dlBps: 42_500_000, upBps: 11_200_000, latMs: 18.2, jitMs: 3.1, city: 'Mumbai' },
      { type: 'ok', dlBps: 88_400_000, upBps: 24_600_000, latMs: 11.7, jitMs: 1.9, city: 'Hyderabad' },
      { type: 'error', message: 'Edge blocked by corporate firewall' }
    );

    render(<CrowdsourceMeasureView language="en" />);

    // 1. Initial idle state: ZERO default or cached speed numbers
    expect(screen.getByTestId('speed-dl-value')).toHaveTextContent('--');
    expect(screen.getByTestId('speed-lat-value')).toHaveTextContent('--');

    // 2. Execute Run #1 -> must display Run #1 values and "Run #1, measured HH:MM:SS IST"
    fireEvent.click(screen.getByTestId('speedtest-start-btn'));
    await waitFor(() => {
      expect(screen.getByTestId('speed-dl-value')).toHaveTextContent('42.5');
    });
    expect(screen.getByTestId('speed-lat-value')).toHaveTextContent('18.2');
    expect(screen.getByTestId('speedtest-run-stamp')).toHaveTextContent(/Run #1, measured \d{2}:\d{2}:\d{2} IST/);

    // 3. Execute Run #2 -> displayed metrics MUST change to Run #2 values and stamp Run #2
    fireEvent.click(screen.getByTestId('speedtest-start-btn'));
    await waitFor(() => {
      expect(screen.getByTestId('speed-dl-value')).toHaveTextContent('88.4');
    });
    expect(screen.getByTestId('speed-dl-value')).not.toHaveTextContent('42.5');
    expect(screen.getByTestId('speed-lat-value')).toHaveTextContent('11.7');
    expect(screen.getByTestId('speedtest-run-stamp')).toHaveTextContent(/Run #2, measured \d{2}:\d{2}:\d{2} IST/);

    // 4. Execute failing Run #3 -> must show "Test failed: ..." + Retry button + NO metric numbers
    fireEvent.click(screen.getByTestId('speedtest-start-btn'));
    await waitFor(() => {
      expect(screen.getByTestId('speedtest-error-banner')).toHaveTextContent(
        'Test failed: Edge blocked by corporate firewall'
      );
    });
    expect(screen.queryByTestId('speed-dl-value')).not.toBeInTheDocument();
    expect(screen.getByText('Retry Test')).toBeInTheDocument();
  });
});

