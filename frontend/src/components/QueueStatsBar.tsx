import { Play, Clock, Timer, Weight, CheckCircle } from 'lucide-react';
import { formatDuration } from '../utils/date';

function formatWeight(g: number): string {
  if (g >= 1000) return `${(g / 1000).toFixed(1)}kg`;
  return `${Math.round(g)}g`;
}

export function QueueStatsBar({
  activeCount,
  pendingCount,
  totalTime,
  totalWeight,
  historyCount,
  t,
}: {
  activeCount: number;
  pendingCount: number;
  totalTime: number;
  totalWeight: number;
  historyCount: number;
  t: (key: string) => string;
}) {
  const stats = [
    { icon: Play, value: activeCount, label: t('queue.summary.printing'), color: 'text-blue-400', marker: 'bg-blue-400' },
    { icon: Clock, value: pendingCount, label: t('queue.summary.queued'), color: 'text-amber-400', marker: 'bg-amber-400' },
    { icon: Timer, value: formatDuration(totalTime), label: t('queue.summary.totalTime'), color: 'text-bambu-green', marker: 'bg-bambu-green' },
    { icon: Weight, value: formatWeight(totalWeight), label: t('queue.summary.totalWeight'), color: 'text-cyan-400', marker: 'bg-cyan-400' },
    { icon: CheckCircle, value: historyCount, label: t('queue.summary.history'), color: 'text-bambu-gray', marker: 'bg-bambu-gray' },
  ];

  return (
    <div
      data-testid="queue-status-summary"
      aria-label={t('queue.title')}
      className="grid grid-cols-2 border-y border-bambu-dark-tertiary sm:grid-cols-5"
    >
      {stats.map((stat, index) => (
        <div
          key={stat.label}
          className={`flex min-h-14 min-w-0 items-center gap-2.5 px-2 py-2 sm:px-3 ${
            index > 0 ? 'sm:border-l sm:border-bambu-dark-tertiary' : ''
          } ${index % 2 === 1 ? 'border-l border-bambu-dark-tertiary sm:border-l' : ''} ${
            index >= 2 ? 'border-t border-bambu-dark-tertiary sm:border-t-0' : ''
          } ${index === stats.length - 1 ? 'col-span-2 sm:col-span-1' : ''}`}
        >
          <span className="relative flex h-7 w-7 shrink-0 items-center justify-center">
            <span className={`absolute left-0 h-5 w-0.5 ${stat.marker}`} />
            <stat.icon className={`h-4 w-4 ${stat.color}`} />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-white">{stat.value}</span>
            <span className="block truncate text-[11px] text-bambu-gray sm:text-xs">{stat.label}</span>
          </span>
        </div>
      ))}
    </div>
  );
}
