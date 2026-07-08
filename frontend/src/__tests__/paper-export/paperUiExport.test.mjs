import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  buildPaperTokens,
  buildPaperUiManifest,
  generatePaperExport,
  validatePaperHtml,
} from '../../../scripts/paper-ui-export-core.mjs';

const sampleCss = `
@theme {
  --color-bambu-green: var(--accent);
}

html {
  font-size: 14.4px;
}

:root {
  --accent: #00ae42;
  --accent-light: #00c64d;
  --bg-primary: #f5f5f5;
  --bg-secondary: #ffffff;
  --text-primary: #1a1a1a;
  --border-color: #d4d4d4;
}
`;

describe('Paper UI export', () => {
  it('extracts Paper-compatible tokens from Bambuddy CSS variables', () => {
    const tokens = buildPaperTokens(sampleCss);

    expect(tokens).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: 'color', name: '--accent', value: '#00ae42' }),
        expect.objectContaining({ type: 'color', name: '--bg-primary', value: '#f5f5f5' }),
        expect.objectContaining({ type: 'color', name: '--color-bambu-green', value: 'var(--accent)' }),
        expect.objectContaining({ type: 'fontFamily', name: '--font-family-sans', value: 'Inter, system-ui, sans-serif' }),
        expect.objectContaining({ type: 'fontSize', name: '--font-size-base', value: '14.4px' }),
        expect.objectContaining({ type: 'radius', name: '--radius-card', value: '8px' }),
      ]),
    );
  });

  it('builds a full-project route manifest instead of a WP-specific manifest', () => {
    const manifest = buildPaperUiManifest();
    const paths = manifest.artboards.map((artboard) => artboard.path);

    expect(paths).toEqual(
      expect.arrayContaining([
        '/',
        '/queue',
        '/archives',
        '/inventory',
        '/settings?tab=general',
        '/settings?tab=users',
        '/spoolbuddy',
        '/spoolbuddy/inventory',
      ]),
    );
    // Real-screen artboards mirror App.tsx routes; proposed design drafts do not.
    const realArtboards = manifest.artboards.filter((artboard) => !artboard.proposed);
    expect(realArtboards.every((artboard) => artboard.source === 'frontend/src/App.tsx')).toBe(true);

    const proposed = manifest.artboards.filter((artboard) => artboard.proposed);
    expect(proposed.length).toBeGreaterThan(0);
    expect(proposed.every((artboard) => artboard.section === 'Farm / SwapMod')).toBe(true);
    expect(proposed.every((artboard) => artboard.source === 'design-draft:swapmod-console')).toBe(true);
    expect(proposed.map((artboard) => artboard.path)).toEqual(
      expect.arrayContaining(['/swapmod', '/swapmod/cycle', '/swapmod/gates', '/swapmod/evidence']),
    );
  });

  it('keeps every manifest artboard aligned with real App.tsx routes and settings tabs', async () => {
    const frontendRoot = path.resolve(import.meta.dirname, '../../..');
    const appSource = await readFile(path.join(frontendRoot, 'src/App.tsx'), 'utf8');
    const settingsSource = await readFile(path.join(frontendRoot, 'src/pages/SettingsPage.tsx'), 'utf8');

    const routePaths = [...appSource.matchAll(/<Route\s+path="([^"]+)"/g)].map((match) =>
      match[1].replace(/^\//, ''),
    );
    const hasIndexRoute = /<Route\s+index\b/.test(appSource);
    const validTabsSource = settingsSource.match(/const validTabs = \[([^\]]+)\]/)?.[1] ?? '';
    const validTabs = [...validTabsSource.matchAll(/'([^']+)'/g)].map((match) => match[1]);

    expect(routePaths.length).toBeGreaterThan(0);
    expect(validTabs.length).toBeGreaterThan(0);

    for (const artboard of buildPaperUiManifest().artboards) {
      if (artboard.proposed) continue; // design drafts have no App.tsx route yet
      const [pathname, query] = artboard.path.split('?');
      const routePath = pathname.replace(/^\//, '');

      if (routePath === '') {
        expect(hasIndexRoute, `index route for artboard ${artboard.slug}`).toBe(true);
      } else {
        expect(routePaths, `App.tsx route for artboard ${artboard.slug} (${artboard.path})`).toContain(routePath);
      }

      if (query) {
        const tab = new URLSearchParams(query).get('tab');
        expect(validTabs, `SettingsPage tab for artboard ${artboard.slug} (${artboard.path})`).toContain(tab);
      }
    }
  });

  it('generates editable inline-style HTML without screenshots or class selectors', () => {
    const bundle = generatePaperExport({ cssText: sampleCss });

    expect(bundle.tokens.length).toBeGreaterThan(0);
    expect(bundle.htmlFiles.length).toBe(bundle.manifest.artboards.length);

    for (const htmlFile of bundle.htmlFiles) {
      expect(htmlFile.html).toContain('layer-name=');
      expect(htmlFile.html).toContain('display:flex');
      expect(htmlFile.html).not.toMatch(/\bclass=/i);
      expect(htmlFile.html).not.toMatch(/<style\b/i);
      expect(htmlFile.html).not.toMatch(/screenshot|capture/i);
      expect(validatePaperHtml(htmlFile.html)).toEqual([]);
    }
  });

  it('rejects Paper HTML that would become non-editable or screenshot-based', () => {
    const errors = validatePaperHtml(`
      <style>.card { color: red; }</style>
      <div class="card" style="display:grid;margin:8px">
        <table><tr><td>bad</td></tr></table>
        <img layer-name="Route Screenshot" src="screen.png" />
      </div>
    `);

    expect(errors).toEqual(
      expect.arrayContaining([
        expect.stringContaining('class'),
        expect.stringContaining('style tag'),
        expect.stringContaining('display:grid'),
        expect.stringContaining('margin'),
        expect.stringContaining('table'),
        expect.stringContaining('screenshot'),
      ]),
    );
  });
});
