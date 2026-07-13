import { Archive, ListOrdered, Menu, Printer, type LucideIcon } from 'lucide-react';
import { NavLink } from 'react-router-dom';

interface OperatorTopBarProps {
  activeIcon: LucideIcon;
  activeLabel: string;
  archiveLabel: string;
  isCompact: boolean;
  needsClearPlate: boolean;
  onOpenMenu: () => void;
  openMenuLabel: string;
  pendingQueueCount: number;
  pendingUploadsCount: number;
  plateClearLabel: string;
  queueLabel: string;
  workspaceLabel: string;
}

function displayCount(count: number): string {
  return count > 99 ? '99+' : String(count);
}

export function OperatorTopBar({
  activeIcon: ActiveIcon,
  activeLabel,
  archiveLabel,
  isCompact,
  needsClearPlate,
  onOpenMenu,
  openMenuLabel,
  pendingQueueCount,
  pendingUploadsCount,
  plateClearLabel,
  queueLabel,
  workspaceLabel,
}: OperatorTopBarProps) {
  return (
    <header
      aria-label={workspaceLabel}
      className="sticky top-0 z-30 flex h-14 w-full items-center justify-between gap-3 border-b border-bambu-dark-tertiary bg-bambu-dark-secondary/95 px-3 backdrop-blur-sm sm:px-4"
    >
      <div className="flex min-w-0 items-center gap-2">
        {isCompact && (
          <button
            type="button"
            onClick={onOpenMenu}
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md text-bambu-gray-light transition-colors hover:bg-bambu-dark-tertiary hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bambu-green"
            aria-label={openMenuLabel}
            title={openMenuLabel}
          >
            <Menu className="h-5 w-5" />
          </button>
        )}

        <div className="flex min-w-0 items-center gap-2" aria-live="polite">
          <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-bambu-green/10 text-bambu-green">
            <ActiveIcon className="h-4 w-4" />
          </span>
          <span className="truncate text-sm font-semibold text-gray-900 dark:text-white sm:text-base">
            {activeLabel}
          </span>
        </div>
      </div>

      <div className="flex flex-shrink-0 items-center gap-1.5">
        {needsClearPlate && (
          <NavLink
            to="/"
            aria-label={plateClearLabel}
            title={plateClearLabel}
            className="relative flex h-9 w-9 items-center justify-center rounded-md border border-amber-500/30 bg-amber-500/10 text-amber-700 transition-colors hover:bg-amber-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 dark:text-amber-300"
          >
            <Printer className="h-4 w-4" />
            <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-amber-500" />
          </NavLink>
        )}

        <NavLink
          to="/queue"
          aria-label={`${queueLabel}: ${pendingQueueCount}`}
          title={`${queueLabel}: ${pendingQueueCount}`}
          className={({ isActive }) =>
            `flex h-9 min-w-9 items-center justify-center gap-1.5 rounded-md border px-2 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bambu-green ${
              isActive || pendingQueueCount > 0
                ? 'border-bambu-green/30 bg-bambu-green/10 text-bambu-green'
                : 'border-bambu-dark-tertiary text-bambu-gray-light hover:bg-bambu-dark-tertiary hover:text-white'
            }`
          }
        >
          <ListOrdered className="h-4 w-4" />
          {pendingQueueCount > 0 && <span>{displayCount(pendingQueueCount)}</span>}
        </NavLink>

        {pendingUploadsCount > 0 && (
          <NavLink
            to="/archives"
            aria-label={`${archiveLabel}: ${pendingUploadsCount}`}
            title={`${archiveLabel}: ${pendingUploadsCount}`}
            className="flex h-9 min-w-9 items-center justify-center gap-1.5 rounded-md border border-sky-500/30 bg-sky-500/10 px-2 text-xs font-semibold text-sky-700 transition-colors hover:bg-sky-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:text-sky-300"
          >
            <Archive className="h-4 w-4" />
            <span>{displayCount(pendingUploadsCount)}</span>
          </NavLink>
        )}
      </div>
    </header>
  );
}
