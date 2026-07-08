const SUPPORTED_TOKEN_TYPES = new Set([
  'breakpoint',
  'color',
  'container',
  'fontFamily',
  'fontSize',
  'fontWeight',
  'letterSpacing',
  'lineHeight',
  'radius',
  'spacing',
]);

const TOKEN_TYPE_ORDER = [
  'color',
  'fontFamily',
  'fontWeight',
  'fontSize',
  'lineHeight',
  'letterSpacing',
  'spacing',
  'radius',
  'container',
  'breakpoint',
];

const MAIN_NAV_ITEMS = [
  'Printers',
  'Queue',
  'Archives',
  'Inventory',
  'Projects',
  'Files',
  'Maintenance',
  'Settings',
];

const SWAPMOD_NAV_ITEMS = ['Printers', 'SwapMod Settings'];

const DEFAULT_ARTBOARDS = [
  route('main-printers', 'Printers', '/', 'Main app', 1440, 980, [
    'Printer fleet overview',
    'Real-time job and bed readiness states',
    'Operator controls remain Bambuddy-owned',
  ]),
  route('main-queue', 'Queue', '/queue', 'Main app', 1440, 1040, [
    'Queued jobs with readiness gates',
    'Dispatch and hold states',
    'Job priority and printer assignment lanes',
  ]),
  route('main-archives', 'Archives', '/archives', 'Main app', 1440, 1120, [
    'Completed and failed run history',
    'Separate records for failed attempts and reprints',
    'Cost and duration summaries',
  ]),
  route('main-stats', 'Stats', '/stats', 'Main app', 1440, 980, [
    'Farm utilization metrics',
    'Printer uptime and failure trends',
    'Material usage summaries',
  ]),
  route('main-profiles', 'Profiles', '/profiles', 'Main app', 1440, 980, [
    'Printer and slicer profile library',
    'Default-off automation settings',
    'Profile compatibility notes',
  ]),
  route('main-maintenance', 'Maintenance', '/maintenance', 'Main app', 1440, 1040, [
    'Maintenance tasks and alerts',
    'Manual review checkpoints',
    'Service history by printer',
  ]),
  route('main-projects', 'Projects', '/projects', 'Main app', 1440, 1040, [
    'Project-level print planning',
    'Related files and runs',
    'Production progress summary',
  ]),
  route('main-inventory', 'Inventory', '/inventory', 'Main app', 1440, 1120, [
    'Spool stock and usage state',
    'ERP draft write boundary',
    'Material warnings and search',
  ]),
  route('main-files', 'Files', '/files', 'Main app', 1440, 1040, [
    'Model and gcode file library',
    'Upload and restore states',
    'Trash and library actions',
  ]),
  route('main-makerworld', 'MakerWorld', '/makerworld', 'Main app', 1440, 1040, [
    'External model discovery',
    'Permission-gated access',
    'Import status and metadata',
  ]),
  route('settings-general', 'Settings General', '/settings?tab=general', 'Settings', 1440, 1120, [
    'System preferences',
    'Theme and local-first UI settings',
    'Runtime configuration review',
  ]),
  route('settings-users', 'Settings Users', '/settings?tab=users', 'Settings', 1440, 1120, [
    'Users and groups',
    'Permission-gated routes',
    'Read-only and update actions',
  ]),
  route('settings-notifications', 'Settings Notifications', '/settings?tab=notifications', 'Settings', 1440, 1120, [
    'ntfy and provider settings',
    'Failure and stock alerts',
    'Delivery test states',
  ]),
  route('settings-queue', 'Settings Queue', '/settings?tab=queue', 'Settings', 1440, 1120, [
    'Print flow preferences',
    'Default-off farm automation',
    'Manual review transitions',
  ]),
  route('settings-filament', 'Settings Filament', '/settings?tab=filament', 'Settings', 1440, 1120, [
    'Color catalog and spool mapping',
    'AMS slot behavior',
    'Material compatibility',
  ]),
  route('settings-network', 'Settings Network', '/settings?tab=network', 'Settings', 1440, 1040, [
    'LAN-first connectivity',
    'Camera token entry points',
    'Local service URLs',
  ]),
  route('settings-spoolbuddy', 'Settings SpoolBuddy', '/settings?tab=spoolbuddy', 'Settings', 1440, 1040, [
    'Kiosk configuration',
    'RFID write flows',
    'Inventory sync preferences',
  ]),
  route('settings-failure-detection', 'Settings Failure Detection', '/settings?tab=failure-detection', 'Settings', 1440, 1040, [
    'Notify-only ML inference',
    'Failure thresholds',
    'Canary criteria and logs',
  ]),
  route('spoolbuddy-dashboard', 'SpoolBuddy Dashboard', '/spoolbuddy', 'SpoolBuddy', 1280, 900, [
    'Kiosk-friendly status overview',
    'AMS and inventory shortcuts',
    'Touch-safe primary actions',
  ]),
  route('spoolbuddy-ams', 'SpoolBuddy AMS', '/spoolbuddy/ams', 'SpoolBuddy', 1280, 980, [
    'AMS bay and slot state',
    'Filament label guidance',
    'Operator mapping actions',
  ]),
  route('spoolbuddy-write-tag', 'SpoolBuddy Write Tag', '/spoolbuddy/write-tag', 'SpoolBuddy', 1280, 980, [
    'RFID write progress',
    'Validation and retry states',
    'Local device status',
  ]),
  route('spoolbuddy-inventory', 'SpoolBuddy Inventory', '/spoolbuddy/inventory', 'SpoolBuddy', 1280, 1040, [
    'Kiosk inventory search',
    'Stock status cards',
    'Material details and actions',
  ]),
  route('spoolbuddy-settings', 'SpoolBuddy Settings', '/spoolbuddy/settings', 'SpoolBuddy', 1280, 940, [
    'Kiosk preferences',
    'Device connection state',
    'Operator mode toggles',
  ]),
  route('spoolbuddy-calibration', 'SpoolBuddy Calibration', '/spoolbuddy/calibration', 'SpoolBuddy', 1280, 940, [
    'Reader calibration',
    'Step-by-step operator state',
    'Success and failure guidance',
  ]),
  route('standalone-login', 'Login', '/login', 'Standalone', 960, 720, [
    'Authentication entry',
    'Local access messaging',
    'Error and loading states',
  ]),
  route('standalone-setup', 'Setup', '/setup', 'Standalone', 960, 820, [
    'First-run configuration',
    'Auth enablement path',
    'Safe local defaults',
  ]),
  draftArtboard('swapmod-printer-card', 'Printers — SwapMod plate change', '/?swapmod=plate-change', 1440, 1040, [
    'Plate-change control lives on each connected printer card',
    'Button is enabled only when SwapMod is armed and the printer is idle',
    'In-progress card shows the live step track without leaving the page',
  ]),
  draftArtboard('swapmod-confirm', 'Printers — plate change confirmation', '/?swapmod=confirm', 1440, 980, [
    'Pressing plate change opens a confirmation gate, not an immediate motion',
    'All 10 checklist items must be ticked by the operator',
    'Server-provided confirmation phrase shown read-only; Confirm sends the step',
  ]),
  draftArtboard('swapmod-settings-failures', 'SwapMod Settings — Failure log', '/settings?tab=swapmod#failures', 1440, 1040, [
    'Accumulated swap failures: time, printer, step, reason, result',
    'MANUAL_REVIEW and jam causes kept for diagnosis',
    'Filter by printer and outcome',
  ]),
  draftArtboard('swapmod-settings-sequences', 'SwapMod Settings — Sequence & speed editor', '/settings?tab=swapmod#sequences', 1440, 1160, [
    'Edit per-action parameters like feedrate/speed of the release and load sequences',
    'Edits create a NEW reviewed version with a fresh SHA-256, never a live raw push',
    'A new version must be approved before a supervised session can select it',
  ]),
];

function route(slug, label, path, section, width, height, highlights) {
  return {
    slug,
    label,
    path,
    section,
    source: 'frontend/src/App.tsx',
    viewport: { width, height },
    highlights,
  };
}

// Proposed screens that do not yet exist as App.tsx routes. They are design
// drafts seeded into Paper for iteration before the React console is built, so
// they are exempt from the route-parity check (source is not App.tsx).
function draftArtboard(slug, label, path, width, height, highlights) {
  return {
    slug,
    label,
    path,
    section: 'Farm / SwapMod',
    source: 'design-draft:swapmod-console',
    proposed: true,
    viewport: { width, height },
    highlights,
  };
}

export function buildPaperUiManifest() {
  const artboards = DEFAULT_ARTBOARDS.map((artboard, index) => ({
    ...artboard,
    htmlFile: `html/${String(index + 1).padStart(2, '0')}-${artboard.slug}.html`,
    artboardStyles: {
      width: `${artboard.viewport.width}px`,
      height: `${artboard.viewport.height}px`,
      backgroundColor: 'var(--bg-primary)',
      display: 'flex',
      flexDirection: 'column',
      padding: '0px',
      overflow: 'hidden',
    },
  }));

  return {
    schemaVersion: 1,
    format: 'paper-inline-html',
    generatedFrom: ['frontend/src/App.tsx', 'frontend/src/index.css'],
    artboards,
  };
}

export function buildPaperTokens(cssText) {
  const fromCss = extractCssVariableTokens(cssText);
  const defaults = buildDefaultTokens(cssText);
  const byName = new Map();

  for (const token of [...fromCss, ...defaults]) {
    if (!SUPPORTED_TOKEN_TYPES.has(token.type)) continue;
    if (!/^--[a-zA-Z0-9_-]+$/.test(token.name)) continue;
    if (!byName.has(token.name)) byName.set(token.name, token);
  }

  return [...byName.values()].sort(compareTokens);
}

function extractCssVariableTokens(cssText) {
  const tokens = [];
  const seen = new Set();
  const variablePattern = /(--[a-zA-Z0-9_-]+)\s*:\s*([^;{}]+);/g;
  let match;

  while ((match = variablePattern.exec(cssText)) !== null) {
    const [, name, rawValue] = match;
    if (seen.has(name)) continue;

    const value = rawValue.trim();
    const type = classifyToken(name, value);
    if (!type) continue;

    seen.add(name);
    tokens.push({
      type,
      name,
      value: type === 'fontWeight' && /^\d+$/.test(value) ? Number(value) : value,
      description: `Imported from Bambuddy CSS variable ${name}.`,
    });
  }

  return tokens;
}

function buildDefaultTokens(cssText) {
  const baseFontSize = cssText.match(/html\s*{[^}]*font-size\s*:\s*([^;]+);/m)?.[1]?.trim() ?? '14.4px';

  return [
    token('fontFamily', '--font-family-sans', 'Inter, system-ui, sans-serif', 'Bambuddy default UI font stack.'),
    token('fontWeight', '--font-weight-regular', 400, 'Regular text weight.'),
    token('fontWeight', '--font-weight-medium', 500, 'Medium emphasis weight.'),
    token('fontWeight', '--font-weight-semibold', 600, 'Section heading weight.'),
    token('fontWeight', '--font-weight-bold', 700, 'Strong heading weight.'),
    token('fontSize', '--font-size-xs', '12px', 'Dense label text.'),
    token('fontSize', '--font-size-sm', '13px', 'Secondary UI text.'),
    token('fontSize', '--font-size-base', baseFontSize, 'Bambuddy base text size.'),
    token('fontSize', '--font-size-lg', '18px', 'Section heading text.'),
    token('fontSize', '--font-size-xl', '24px', 'Page title text.'),
    token('lineHeight', '--line-height-tight', '1.25', 'Compact heading line height.'),
    token('lineHeight', '--line-height-normal', '1.5', 'Default body line height.'),
    token('letterSpacing', '--letter-spacing-normal', '0px', 'Default letter spacing.'),
    token('spacing', '--spacing-1', '4px', 'Smallest UI gap.'),
    token('spacing', '--spacing-2', '8px', 'Compact UI gap.'),
    token('spacing', '--spacing-3', '12px', 'Default control gap.'),
    token('spacing', '--spacing-4', '16px', 'Card and panel padding.'),
    token('spacing', '--spacing-6', '24px', 'Section spacing.'),
    token('spacing', '--spacing-8', '32px', 'Page spacing.'),
    token('radius', '--radius-control', '6px', 'Buttons and inputs.'),
    token('radius', '--radius-card', '8px', 'Cards and repeated panels.'),
    token('container', '--container-page', '1440px', 'Desktop Paper artboard width.'),
    token('breakpoint', '--breakpoint-mobile', '390px', 'Mobile verification width.'),
    token('breakpoint', '--breakpoint-desktop', '1440px', 'Desktop verification width.'),
  ];
}

function token(type, name, value, description) {
  return { type, name, value, description };
}

function classifyToken(name, value) {
  const lowerName = name.toLowerCase();
  const lowerValue = value.toLowerCase();

  if (lowerName.includes('font-family')) return 'fontFamily';
  if (lowerName.includes('font-size')) return 'fontSize';
  if (lowerName.includes('font-weight')) return 'fontWeight';
  if (lowerName.includes('line-height')) return 'lineHeight';
  if (lowerName.includes('letter-spacing')) return 'letterSpacing';
  if (lowerName.includes('spacing')) return 'spacing';
  if (lowerName.includes('radius')) return 'radius';
  if (lowerName.includes('breakpoint')) return 'breakpoint';
  if (lowerName.includes('container')) return 'container';

  const colorName =
    lowerName.startsWith('--accent') ||
    lowerName.startsWith('--bg-') ||
    lowerName.startsWith('--text-') ||
    lowerName.startsWith('--border') ||
    lowerName.startsWith('--status') ||
    lowerName.includes('color') ||
    lowerName.includes('bambu');
  const colorValue =
    /^#[0-9a-f]{3,8}$/i.test(value) ||
    /^(rgb|rgba|hsl|hsla|oklch|oklab)\(/i.test(value) ||
    lowerValue === 'transparent' ||
    /^var\(--(accent|bg-|text-|border|status|color-|bambu)/i.test(value);

  if (colorName || colorValue) return 'color';
  return null;
}

function compareTokens(a, b) {
  const typeDiff = TOKEN_TYPE_ORDER.indexOf(a.type) - TOKEN_TYPE_ORDER.indexOf(b.type);
  if (typeDiff !== 0) return typeDiff;
  return a.name.localeCompare(b.name);
}

export function generatePaperExport({ cssText }) {
  const manifest = buildPaperUiManifest();
  const tokens = buildPaperTokens(cssText);
  const htmlFiles = manifest.artboards.map((artboard) => {
    const html = renderPaperHtml(artboard, manifest);
    return {
      path: artboard.htmlFile,
      slug: artboard.slug,
      label: artboard.label,
      html,
      validationErrors: validatePaperHtml(html),
    };
  });

  const validationErrors = htmlFiles.flatMap((file) =>
    file.validationErrors.map((message) => `${file.path}: ${message}`),
  );

  return {
    manifest,
    tokens,
    htmlFiles,
    validationErrors,
  };
}

export function validatePaperHtml(html) {
  const errors = [];

  if (/<style\b/i.test(html)) errors.push('Paper HTML must not include a style tag; use inline styles.');
  if (/\bclass\s*=/i.test(html)) errors.push('Paper HTML must not include class attributes.');
  if (/display\s*:\s*grid/i.test(html)) errors.push('Paper HTML must not use display:grid.');
  if (/display\s*:\s*inline(?!-)/i.test(html)) errors.push('Paper HTML must not use display:inline.');
  if (/\bmargin(?:-[a-z]+)?\s*:/i.test(html)) errors.push('Paper HTML must not use margin; use padding and gap.');
  if (/<\/?(table|thead|tbody|tr|td|th)\b/i.test(html)) errors.push('Paper HTML must not use table elements.');
  if (/screenshot|screen\s*capture|capture\b/i.test(html)) {
    errors.push('Paper HTML must not be screenshot-based.');
  }

  return errors;
}

function renderPaperHtml(artboard, manifest) {
  if (artboard.section === 'Farm / SwapMod') return renderSwapModScreen(artboard);
  if (artboard.section === 'SpoolBuddy') return renderSpoolBuddyScreen(artboard);
  if (artboard.section === 'Standalone') return renderStandaloneScreen(artboard);
  return renderMainAppScreen(artboard, manifest);
}

function renderMainAppScreen(artboard, manifest) {
  const title = escapeHtml(artboard.label);
  const path = escapeHtml(artboard.path);
  const navItems = MAIN_NAV_ITEMS.map((item) => navRow(item, artboard.label)).join('');
  const settingsTabs =
    artboard.section === 'Settings'
      ? `<div layer-name="Settings tabs" style="display:flex;flex-direction:row;gap:8px;align-items:center;flex-wrap:wrap;width:100%;box-sizing:border-box;">${[
          'General',
          'Users',
          'Notifications',
          'Queue',
          'Filament',
          'Network',
          'SpoolBuddy',
          'Failure Detection',
        ]
          .map((tab) => pill(tab, artboard.label.includes(tab)))
          .join('')}</div>`
      : '';

  return `
<section layer-name="${escapeAttr(artboard.label)} Screen" style="box-sizing:border-box;width:100%;min-height:100%;background-color:var(--bg-primary);color:var(--text-primary);font-family:var(--font-family-sans);display:flex;flex-direction:row;padding:0px;gap:0px;overflow:hidden;">
  <aside layer-name="Primary navigation" style="box-sizing:border-box;width:248px;flex-shrink:0;background-color:var(--bg-secondary);border-right:1px solid var(--border-color);display:flex;flex-direction:column;padding:24px 18px;gap:18px;">
    <div layer-name="Bambuddy brand" style="box-sizing:border-box;display:flex;flex-direction:column;gap:4px;padding:0px 4px;">
      <div style="font-size:20px;line-height:1.25;font-weight:700;color:var(--text-primary);">Bambuddy</div>
      <div style="font-size:12px;line-height:1.4;font-weight:500;color:var(--text-muted);">LAN-first farm control</div>
    </div>
    <nav layer-name="Main nav items" style="box-sizing:border-box;display:flex;flex-direction:column;gap:6px;width:100%;">${navItems}</nav>
    <div layer-name="Safety status" style="box-sizing:border-box;display:flex;flex-direction:column;gap:8px;padding:14px;border:1px solid var(--border-color);border-radius:var(--radius-card);background-color:var(--bg-primary);">
      <div style="font-size:12px;line-height:1.4;font-weight:600;color:var(--text-secondary);">Authority</div>
      <div style="font-size:13px;line-height:1.5;color:var(--text-primary);">Printer commands stay inside Bambuddy.</div>
    </div>
  </aside>
  <main layer-name="${escapeAttr(artboard.label)} content" style="box-sizing:border-box;flex:1;min-width:0;display:flex;flex-direction:column;padding:32px;gap:24px;overflow:hidden;">
    <header layer-name="Page header" style="box-sizing:border-box;display:flex;flex-direction:row;align-items:flex-start;justify-content:space-between;gap:24px;width:100%;">
      <div style="box-sizing:border-box;display:flex;flex-direction:column;gap:8px;">
        <div style="font-size:12px;line-height:1.4;font-weight:600;color:var(--accent);">${path}</div>
        <h1 style="font-size:28px;line-height:1.25;font-weight:700;color:var(--text-primary);padding:0px;">${title}</h1>
        <p style="font-size:14px;line-height:1.5;color:var(--text-secondary);padding:0px;max-width:680px;">Editable Paper layer generated from the Bambuddy route inventory and design tokens.</p>
      </div>
      <div layer-name="Route state chips" style="box-sizing:border-box;display:flex;flex-direction:row;gap:8px;align-items:center;flex-shrink:0;">
        ${pill(artboard.section, true)}
        ${pill('Default UI', false)}
      </div>
    </header>
    ${settingsTabs}
    ${summaryCards(artboard)}
    ${routeHighlights(artboard)}
    ${operatorRows(artboard)}
  </main>
</section>`.trim();
}

function renderSpoolBuddyScreen(artboard) {
  return `
<section layer-name="${escapeAttr(artboard.label)} Screen" style="box-sizing:border-box;width:100%;min-height:100%;background-color:var(--bg-primary);color:var(--text-primary);font-family:var(--font-family-sans);display:flex;flex-direction:column;padding:32px;gap:24px;overflow:hidden;">
  <header layer-name="Kiosk header" style="box-sizing:border-box;width:100%;display:flex;flex-direction:row;align-items:center;justify-content:space-between;gap:24px;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);padding:20px 24px;">
    <div style="box-sizing:border-box;display:flex;flex-direction:column;gap:4px;">
      <div style="font-size:12px;line-height:1.4;font-weight:600;color:var(--accent);">${escapeHtml(artboard.path)}</div>
      <h1 style="font-size:28px;line-height:1.25;font-weight:700;color:var(--text-primary);padding:0px;">${escapeHtml(artboard.label)}</h1>
    </div>
    <div style="box-sizing:border-box;display:flex;flex-direction:row;gap:10px;align-items:center;">
      ${pill('Kiosk', true)}
      ${pill('Touch layout', false)}
    </div>
  </header>
  <div layer-name="Kiosk action area" style="box-sizing:border-box;display:flex;flex-direction:row;gap:20px;align-items:stretch;width:100%;flex:1;min-height:0;">
    <section layer-name="Primary action panel" style="box-sizing:border-box;flex:1;display:flex;flex-direction:column;gap:18px;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);padding:24px;">
      ${routeHighlights(artboard)}
    </section>
    <aside layer-name="Device status rail" style="box-sizing:border-box;width:340px;flex-shrink:0;display:flex;flex-direction:column;gap:14px;">
      ${statusTile('Reader', 'Ready', 'var(--status-ok)')}
      ${statusTile('Inventory sync', 'Draft-safe', 'var(--status-warning)')}
      ${statusTile('Operator mode', 'Manual', 'var(--accent)')}
    </aside>
  </div>
</section>`.trim();
}

function renderStandaloneScreen(artboard) {
  return `
<section layer-name="${escapeAttr(artboard.label)} Screen" style="box-sizing:border-box;width:100%;min-height:100%;background-color:var(--bg-primary);color:var(--text-primary);font-family:var(--font-family-sans);display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px;gap:24px;overflow:hidden;">
  <main layer-name="${escapeAttr(artboard.label)} panel" style="box-sizing:border-box;width:520px;display:flex;flex-direction:column;gap:20px;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);padding:32px;">
    <div style="box-sizing:border-box;display:flex;flex-direction:column;gap:8px;">
      <div style="font-size:12px;line-height:1.4;font-weight:600;color:var(--accent);">${escapeHtml(artboard.path)}</div>
      <h1 style="font-size:28px;line-height:1.25;font-weight:700;color:var(--text-primary);padding:0px;">${escapeHtml(artboard.label)}</h1>
      <p style="font-size:14px;line-height:1.5;color:var(--text-secondary);padding:0px;">Local-first access flow represented as editable Paper layers.</p>
    </div>
    ${routeHighlights(artboard)}
    <div layer-name="Form controls" style="box-sizing:border-box;display:flex;flex-direction:column;gap:12px;width:100%;">
      <div style="box-sizing:border-box;height:44px;border:1px solid var(--border-color);border-radius:var(--radius-control);background-color:var(--bg-primary);display:flex;align-items:center;padding:0px 14px;color:var(--text-muted);font-size:14px;">Primary field</div>
      <div style="box-sizing:border-box;height:44px;border-radius:var(--radius-control);background-color:var(--accent);display:flex;align-items:center;justify-content:center;padding:0px 14px;color:#ffffff;font-size:14px;font-weight:700;">Continue</div>
    </div>
  </main>
</section>`.trim();
}

function renderSwapModScreen(artboard) {
  const title = escapeHtml(artboard.label);
  const path = escapeHtml(artboard.path);
  const navItems = SWAPMOD_NAV_ITEMS.map((item) => navRow(item, artboard.label)).join('');

  return `
<section layer-name="${escapeAttr(artboard.label)} Screen" style="box-sizing:border-box;width:100%;min-height:100%;background-color:var(--bg-primary);color:var(--text-primary);font-family:var(--font-family-sans);display:flex;flex-direction:row;padding:0px;gap:0px;overflow:hidden;">
  <aside layer-name="SwapMod navigation" style="box-sizing:border-box;width:248px;flex-shrink:0;background-color:var(--bg-secondary);border-right:1px solid var(--border-color);display:flex;flex-direction:column;padding:24px 18px;gap:18px;">
    <div layer-name="SwapMod brand" style="box-sizing:border-box;display:flex;flex-direction:column;gap:4px;padding:0px 4px;">
      <div style="font-size:20px;line-height:1.25;font-weight:700;color:var(--text-primary);">SwapMod Console</div>
      <div style="font-size:12px;line-height:1.4;font-weight:500;color:var(--text-muted);">Supervised plate-change control</div>
    </div>
    <nav layer-name="SwapMod nav items" style="box-sizing:border-box;display:flex;flex-direction:column;gap:6px;width:100%;">${navItems}</nav>
    <div layer-name="Actuation authority" style="box-sizing:border-box;display:flex;flex-direction:column;gap:8px;padding:14px;border:1px solid var(--status-warning);border-radius:var(--radius-card);background-color:var(--bg-primary);">
      <div style="font-size:12px;line-height:1.4;font-weight:600;color:var(--status-warning);">Actuation gate</div>
      <div style="font-size:13px;line-height:1.5;color:var(--text-primary);">Every motion needs the per-step confirmation phrase and full checklist. Flags stay default-off outside a supervised window.</div>
    </div>
  </aside>
  <main layer-name="${escapeAttr(artboard.label)} content" style="box-sizing:border-box;flex:1;min-width:0;display:flex;flex-direction:column;padding:32px;gap:24px;overflow:hidden;">
    <header layer-name="Page header" style="box-sizing:border-box;display:flex;flex-direction:row;align-items:flex-start;justify-content:space-between;gap:24px;width:100%;">
      <div style="box-sizing:border-box;display:flex;flex-direction:column;gap:8px;">
        <div style="font-size:12px;line-height:1.4;font-weight:600;color:var(--accent);">${path}</div>
        <h1 style="font-size:28px;line-height:1.25;font-weight:700;color:var(--text-primary);padding:0px;">${title}</h1>
        <p style="font-size:14px;line-height:1.5;color:var(--text-secondary);padding:0px;max-width:680px;">Proposed SwapMod operator console — design draft for Paper iteration before the React build.</p>
      </div>
      <div layer-name="Draft chips" style="box-sizing:border-box;display:flex;flex-direction:row;gap:8px;align-items:center;flex-shrink:0;">
        ${pill('Farm / SwapMod', true)}
        ${pill('Design draft', false)}
      </div>
    </header>
    ${swapModBody(artboard)}
    ${routeHighlights(artboard)}
  </main>
</section>`.trim();
}

function swapModBody(artboard) {
  if (artboard.slug === 'swapmod-printer-card') return printerCardBody();
  if (artboard.slug === 'swapmod-confirm') return confirmModalBody();
  if (artboard.slug === 'swapmod-settings-failures') return failureLogBody();
  if (artboard.slug === 'swapmod-settings-sequences') return sequenceEditorBody();
  return '';
}

function printerCardBody() {
  return `<section layer-name="Printer grid" style="box-sizing:border-box;display:flex;flex-direction:row;flex-wrap:wrap;gap:16px;width:100%;align-items:stretch;">
  ${printerCard('A1 Mini — canary', 'IDLE', 'armed')}
  ${printerCard('X1C — bay 2', 'RUNNING', 'busy')}
  ${printerCard('P1S — bay 3', 'IDLE', 'disarmed')}
</section>`;
}

function printerCard(name, state, swap) {
  const stateColor = state === 'RUNNING' ? 'var(--accent)' : 'var(--status-ok)';
  let control;
  if (swap === 'armed') {
    control = `<div layer-name="Plate change control" style="box-sizing:border-box;display:flex;flex-direction:column;gap:10px;width:100%;">
      ${swapModButton('Plate change (SwapMod)', 'primary')}
      <div layer-name="Inline step track" style="box-sizing:border-box;display:flex;flex-direction:row;flex-wrap:wrap;gap:6px;align-items:center;width:100%;">${[
        ['RELEASE', true],
        ['VERIFY', false],
        ['LOAD', false],
        ['VERIFY', false],
        ['READY', false],
      ]
        .map(([label, active]) => pill(label, active))
        .join('')}</div>
      <div style="font-size:12px;line-height:1.4;color:var(--text-muted);">SwapMod armed · idle · press to start a supervised swap</div>
    </div>`;
  } else if (swap === 'busy') {
    control = `<div layer-name="Plate change disabled" style="box-sizing:border-box;display:flex;flex-direction:column;gap:8px;width:100%;">
      ${swapModButton('Plate change unavailable', 'muted')}
      <div style="font-size:12px;line-height:1.4;color:var(--text-muted);">Printer is printing — swap is blocked until the job finishes.</div>
    </div>`;
  } else {
    control = `<div layer-name="Plate change disarmed" style="box-sizing:border-box;display:flex;flex-direction:column;gap:8px;width:100%;">
      ${swapModButton('Plate change unavailable', 'muted')}
      <div style="font-size:12px;line-height:1.4;color:var(--text-muted);">SwapMod flags default-off — arm for a supervised window to enable.</div>
    </div>`;
  }
  return `
<article layer-name="${escapeAttr(name)} card" style="box-sizing:border-box;width:420px;flex:1;min-width:360px;display:flex;flex-direction:column;gap:14px;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);padding:20px;">
  <div layer-name="Card header" style="box-sizing:border-box;display:flex;flex-direction:row;align-items:center;justify-content:space-between;gap:12px;width:100%;">
    <div style="font-size:16px;line-height:1.3;font-weight:700;color:var(--text-primary);">${escapeHtml(name)}</div>
    ${pill(state, state !== 'RUNNING')}
  </div>
  <div layer-name="Camera placeholder" style="box-sizing:border-box;width:100%;height:150px;border-radius:var(--radius-control);background-color:var(--bg-primary);border:1px solid var(--border-color);display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:13px;">Live view</div>
  <div style="box-sizing:border-box;display:flex;flex-direction:row;gap:10px;align-items:center;">
    <div style="box-sizing:border-box;width:10px;height:10px;border-radius:999px;background-color:${stateColor};flex-shrink:0;"></div>
    <div style="font-size:13px;line-height:1.4;color:var(--text-secondary);">Bed ${state === 'RUNNING' ? 'in use' : 'clear'} · AMS ready</div>
  </div>
  ${control}
</article>`.trim();
}

function confirmModalBody() {
  const items = [
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
  return `<section layer-name="Confirmation overlay" style="box-sizing:border-box;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;width:100%;padding:8px;">
  <div layer-name="Confirm modal" style="box-sizing:border-box;width:720px;max-width:100%;display:flex;flex-direction:column;gap:16px;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);padding:24px;">
    <div style="box-sizing:border-box;display:flex;flex-direction:column;gap:6px;">
      <div style="font-size:12px;line-height:1.4;font-weight:600;color:var(--status-warning);">A1 Mini — canary · supervised actuation</div>
      <div style="font-size:20px;line-height:1.25;font-weight:700;color:var(--text-primary);">Confirm plate change — RELEASE_PLATE</div>
      <div style="font-size:14px;line-height:1.5;color:var(--text-secondary);">Tick every item after physically checking it. Nothing moves until you confirm.</div>
    </div>
    <div layer-name="Checklist" style="box-sizing:border-box;display:flex;flex-direction:column;gap:10px;width:100%;">${items
      .map((item) => swapModCheckRow(item))
      .join('')}</div>
    <div layer-name="Phrase preview" style="box-sizing:border-box;display:flex;flex-direction:column;gap:6px;background-color:var(--bg-primary);border:1px solid var(--border-color);border-radius:var(--radius-control);padding:12px;">
      <div style="font-size:12px;line-height:1.4;font-weight:600;color:var(--text-muted);">Confirmation phrase (from server, read-only)</div>
      <div style="font-size:13px;line-height:1.5;font-weight:600;color:var(--text-primary);">CONFIRM_A1_MINI_DIRECT_PLATE_CHANGE 1 &lt;cycle&gt; RELEASE_PLATE &lt;sha256&gt;</div>
    </div>
    <div layer-name="Confirm actions" style="box-sizing:border-box;display:flex;flex-direction:row;gap:12px;align-items:center;width:100%;">
      ${swapModButton('Confirm & send RELEASE_PLATE', 'primary')}
      ${swapModButton('Cancel', 'muted')}
    </div>
  </div>
</section>`;
}

function swapModButton(label, tone) {
  const background =
    tone === 'primary'
      ? 'var(--accent)'
      : tone === 'ok'
        ? 'var(--status-ok)'
        : tone === 'danger'
          ? 'var(--status-error)'
          : 'var(--bg-primary)';
  const color = tone === 'muted' ? 'var(--text-secondary)' : '#ffffff';
  const border = tone === 'muted' ? 'var(--border-color)' : background;
  return `<div layer-name="${escapeAttr(label)} button" style="box-sizing:border-box;display:flex;align-items:center;justify-content:center;min-height:44px;border-radius:var(--radius-control);padding:0px 18px;background-color:${background};border:1px solid ${border};color:${color};font-size:14px;line-height:1.4;font-weight:700;white-space:nowrap;">${escapeHtml(label)}</div>`;
}

function swapModCheckRow(label) {
  return `
<div layer-name="Check ${escapeAttr(label)}" style="box-sizing:border-box;display:flex;flex-direction:row;gap:12px;align-items:center;width:100%;min-height:32px;">
  <div style="box-sizing:border-box;width:22px;height:22px;border-radius:var(--radius-control);background-color:var(--bg-primary);border:1px solid var(--border-color);flex-shrink:0;"></div>
  <div style="font-size:14px;line-height:1.5;color:var(--text-primary);">${escapeHtml(label)}</div>
</div>`.trim();
}

function failureLogBody() {
  const rows = [
    ['2026-07-03 06:11', 'A1 Mini', 'RELEASE_PLATE', 'Plate jammed mid-eject at front hook', 'MANUAL_REVIEW'],
    ['2026-07-03 07:27', 'A1 Mini', 'RELEASE_PLATE', 'v02-01 retry-hop still failed — bed sag', 'MANUAL_REVIEW'],
    ['2026-07-06 05:13', 'A1 Mini', 'RELEASE_PLATE', 'Failure cause not observed', 'MANUAL_REVIEW'],
    ['2026-07-06 16:38', 'A1 Mini', 'VERIFY_RELEASED', 'Injected verify-fail (S6 drill)', 'MANUAL_REVIEW'],
  ];
  return `<section layer-name="Failure filters" style="box-sizing:border-box;display:flex;flex-direction:row;gap:10px;align-items:center;width:100%;">
  ${pill('All printers', true)}
  ${pill('A1 Mini', false)}
  ${pill('MANUAL_REVIEW only', false)}
</section>
<section layer-name="Failure log" style="box-sizing:border-box;display:flex;flex-direction:column;gap:0px;width:100%;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);overflow:hidden;">
  <div layer-name="Failure header" style="box-sizing:border-box;display:flex;flex-direction:row;gap:16px;align-items:center;padding:14px 16px;background-color:var(--bg-primary);border-bottom:1px solid var(--border-color);">
    <div style="width:130px;flex-shrink:0;font-size:12px;font-weight:700;color:var(--text-muted);">Time</div>
    <div style="width:96px;flex-shrink:0;font-size:12px;font-weight:700;color:var(--text-muted);">Printer</div>
    <div style="width:150px;flex-shrink:0;font-size:12px;font-weight:700;color:var(--text-muted);">Step</div>
    <div style="flex:1;min-width:0;font-size:12px;font-weight:700;color:var(--text-muted);">Reason</div>
    <div style="width:150px;flex-shrink:0;font-size:12px;font-weight:700;color:var(--text-muted);">Result</div>
  </div>
  ${rows.map((row, index) => failureRow(row, index === rows.length - 1)).join('')}
</section>`;
}

function failureRow([time, printer, step, reason, result], last) {
  return `
<div layer-name="Failure ${escapeAttr(time)}" style="box-sizing:border-box;display:flex;flex-direction:row;gap:16px;align-items:center;min-height:52px;padding:12px 16px;border-bottom:${last ? '0px solid transparent' : '1px solid var(--border-color)'};">
  <div style="width:130px;flex-shrink:0;font-size:13px;color:var(--text-secondary);">${escapeHtml(time)}</div>
  <div style="width:96px;flex-shrink:0;font-size:13px;font-weight:600;color:var(--text-primary);">${escapeHtml(printer)}</div>
  <div style="width:150px;flex-shrink:0;font-size:13px;color:var(--text-secondary);">${escapeHtml(step)}</div>
  <div style="flex:1;min-width:0;font-size:14px;line-height:1.5;color:var(--text-primary);">${escapeHtml(reason)}</div>
  <div style="width:150px;flex-shrink:0;display:flex;justify-content:flex-start;">${pill(result, false)}</div>
</div>`.trim();
}

function sequenceEditorBody() {
  const actions = [
    ['Park extruder', 'X-14', 'F5000'],
    ['Move plate to ejecting position', 'Y182', 'F10000'],
    ['Lift the plate', 'Y120', 'F500'],
    ['Jump over the front hook', 'Y115', 'F500'],
    ['Pull the new plate', 'Y180', 'F2000'],
  ];
  return `<section layer-name="Version banner" style="box-sizing:border-box;display:flex;flex-direction:row;align-items:center;justify-content:space-between;gap:16px;width:100%;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);padding:16px 18px;">
  <div style="box-sizing:border-box;display:flex;flex-direction:column;gap:4px;">
    <div style="font-size:13px;line-height:1.4;font-weight:700;color:var(--text-primary);">Release sequence — a1mini-swapmod-release-v02-00</div>
    <div style="font-size:12px;line-height:1.4;color:var(--text-muted);">sha256 c7990354… · reviewed · used by supervised sessions</div>
  </div>
  ${pill('Reviewed', true)}
</section>
<section layer-name="Sequence editor" style="box-sizing:border-box;display:flex;flex-direction:column;gap:0px;width:100%;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);overflow:hidden;">
  <div layer-name="Editor header" style="box-sizing:border-box;display:flex;flex-direction:row;gap:16px;align-items:center;padding:14px 16px;background-color:var(--bg-primary);border-bottom:1px solid var(--border-color);">
    <div style="flex:1;min-width:0;font-size:12px;font-weight:700;color:var(--text-muted);">Action</div>
    <div style="width:120px;flex-shrink:0;font-size:12px;font-weight:700;color:var(--text-muted);">Target</div>
    <div style="width:150px;flex-shrink:0;font-size:12px;font-weight:700;color:var(--text-muted);">Speed (feedrate)</div>
  </div>
  ${actions.map((row, index) => sequenceRow(row, index === actions.length - 1)).join('')}
</section>
<section layer-name="Editor actions" style="box-sizing:border-box;display:flex;flex-direction:column;gap:12px;width:100%;background-color:var(--bg-secondary);border:1px solid var(--status-warning);border-radius:var(--radius-card);padding:18px;">
  <div style="font-size:13px;line-height:1.5;color:var(--text-primary);">Saving does not push G-code to a printer. It writes a NEW version (fresh SHA-256) that must be approved before a supervised session can select it. The current reviewed version stays in use until then.</div>
  <div style="box-sizing:border-box;display:flex;flex-direction:row;gap:12px;align-items:center;width:100%;">
    ${swapModButton('Save as new version (needs review)', 'primary')}
    ${swapModButton('Discard changes', 'muted')}
  </div>
</section>`;
}

function sequenceRow([action, target, speed], last) {
  return `
<div layer-name="Action ${escapeAttr(action)}" style="box-sizing:border-box;display:flex;flex-direction:row;gap:16px;align-items:center;min-height:56px;padding:10px 16px;border-bottom:${last ? '0px solid transparent' : '1px solid var(--border-color)'};">
  <div style="flex:1;min-width:0;font-size:14px;line-height:1.5;color:var(--text-primary);">${escapeHtml(action)}</div>
  <div style="width:120px;flex-shrink:0;font-size:14px;font-weight:600;color:var(--text-secondary);">${escapeHtml(target)}</div>
  <div style="width:150px;flex-shrink:0;">${editableField(speed)}</div>
</div>`.trim();
}

function editableField(value) {
  return `<div layer-name="Field ${escapeAttr(value)}" style="box-sizing:border-box;display:flex;align-items:center;min-height:36px;border:1px solid var(--accent);border-radius:var(--radius-control);padding:0px 12px;background-color:var(--bg-primary);color:var(--text-primary);font-size:14px;font-weight:700;">${escapeHtml(value)}</div>`;
}

function navRow(label, activeLabel) {
  const active = activeLabel.toLowerCase().includes(label.toLowerCase());
  return `
<div layer-name="Nav ${escapeAttr(label)}" style="box-sizing:border-box;height:40px;width:100%;display:flex;flex-direction:row;align-items:center;gap:10px;border-radius:var(--radius-control);padding:0px 12px;background-color:${active ? 'var(--accent)' : 'transparent'};color:${active ? '#ffffff' : 'var(--text-secondary)'};">
  <div style="box-sizing:border-box;width:10px;height:10px;border-radius:3px;background-color:${active ? '#ffffff' : 'var(--border-color)'};flex-shrink:0;"></div>
  <div style="font-size:14px;line-height:1.4;font-weight:${active ? '700' : '500'};">${escapeHtml(label)}</div>
</div>`.trim();
}

function summaryCards(artboard) {
  const cards = [
    ['Route', artboard.path],
    ['Surface', artboard.section],
    ['Source', artboard.source],
  ];

  return `<section layer-name="Summary cards" style="box-sizing:border-box;display:flex;flex-direction:row;gap:16px;width:100%;">${cards
    .map(
      ([label, value]) => `
<article layer-name="${escapeAttr(label)} card" style="box-sizing:border-box;flex:1;min-width:0;display:flex;flex-direction:column;gap:8px;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);padding:18px;">
  <div style="font-size:12px;line-height:1.4;font-weight:600;color:var(--text-muted);">${escapeHtml(label)}</div>
  <div style="font-size:18px;line-height:1.3;font-weight:700;color:var(--text-primary);">${escapeHtml(value)}</div>
</article>`.trim(),
    )
    .join('')}</section>`;
}

function routeHighlights(artboard) {
  return `<section layer-name="Editable route highlights" style="box-sizing:border-box;display:flex;flex-direction:column;gap:12px;width:100%;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);padding:18px;">
  <div style="font-size:13px;line-height:1.4;font-weight:700;color:var(--text-primary);">Expected UI states</div>
  <div style="box-sizing:border-box;display:flex;flex-direction:column;gap:10px;">${artboard.highlights
    .map((item, index) => highlightRow(index + 1, item))
    .join('')}</div>
</section>`;
}

function highlightRow(index, text) {
  return `
<div layer-name="State ${index}" style="box-sizing:border-box;display:flex;flex-direction:row;gap:12px;align-items:center;width:100%;min-height:36px;">
  <div style="box-sizing:border-box;width:28px;height:28px;border-radius:var(--radius-control);background-color:var(--bg-primary);border:1px solid var(--border-color);display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:12px;font-weight:700;flex-shrink:0;">${index}</div>
  <div style="font-size:14px;line-height:1.5;color:var(--text-primary);">${escapeHtml(text)}</div>
</div>`.trim();
}

function operatorRows(artboard) {
  const rows = [
    ['Baseline', 'Uses existing Bambuddy UI structure', 'Ready'],
    ['Paper mode', 'Editable HTML layers with inline styles', 'Export'],
    ['Safety', 'No printer authority moves outside Bambuddy', 'Locked'],
  ];

  return `<section layer-name="Operational rows" style="box-sizing:border-box;display:flex;flex-direction:column;gap:0px;width:100%;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);overflow:hidden;">
  <div layer-name="Rows header" style="box-sizing:border-box;display:flex;flex-direction:row;gap:16px;align-items:center;padding:14px 16px;background-color:var(--bg-primary);border-bottom:1px solid var(--border-color);">
    <div style="width:160px;flex-shrink:0;font-size:12px;font-weight:700;color:var(--text-muted);">Area</div>
    <div style="flex:1;min-width:0;font-size:12px;font-weight:700;color:var(--text-muted);">Detail</div>
    <div style="width:120px;flex-shrink:0;font-size:12px;font-weight:700;color:var(--text-muted);">State</div>
  </div>
  ${rows.map((row, index) => operatorRow(row, index, artboard)).join('')}
</section>`;
}

function operatorRow([area, detail, state], index, artboard) {
  return `
<div layer-name="${escapeAttr(artboard.slug)} row ${index + 1}" style="box-sizing:border-box;display:flex;flex-direction:row;gap:16px;align-items:center;min-height:52px;padding:0px 16px;border-bottom:${index === 2 ? '0px solid transparent' : '1px solid var(--border-color)'};">
  <div style="width:160px;flex-shrink:0;font-size:14px;font-weight:600;color:var(--text-primary);">${escapeHtml(area)}</div>
  <div style="flex:1;min-width:0;font-size:14px;line-height:1.5;color:var(--text-secondary);">${escapeHtml(detail)}</div>
  <div style="width:120px;flex-shrink:0;display:flex;justify-content:flex-start;">${pill(state, state === 'Ready' || state === 'Export')}</div>
</div>`.trim();
}

function pill(label, active) {
  return `<div layer-name="${escapeAttr(label)} chip" style="box-sizing:border-box;display:flex;align-items:center;justify-content:center;min-height:28px;border-radius:999px;padding:0px 10px;background-color:${active ? 'var(--accent)' : 'var(--bg-primary)'};border:1px solid ${active ? 'var(--accent)' : 'var(--border-color)'};color:${active ? '#ffffff' : 'var(--text-secondary)'};font-size:12px;line-height:1.4;font-weight:700;white-space:nowrap;">${escapeHtml(label)}</div>`;
}

function statusTile(label, value, color) {
  return `
<div layer-name="${escapeAttr(label)} status" style="box-sizing:border-box;display:flex;flex-direction:column;gap:8px;background-color:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-card);padding:18px;">
  <div style="font-size:12px;line-height:1.4;font-weight:700;color:var(--text-muted);">${escapeHtml(label)}</div>
  <div style="box-sizing:border-box;display:flex;flex-direction:row;gap:10px;align-items:center;">
    <div style="box-sizing:border-box;width:10px;height:10px;border-radius:999px;background-color:${color};flex-shrink:0;"></div>
    <div style="font-size:18px;line-height:1.3;font-weight:700;color:var(--text-primary);">${escapeHtml(value)}</div>
  </div>
</div>`.trim();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll('\n', ' ');
}
