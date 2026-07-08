import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { generatePaperExport } from './paper-ui-export-core.mjs';

const args = parseArgs(process.argv.slice(2));
const projectRoot = path.resolve(import.meta.dirname, '..');
const cssPath = path.resolve(projectRoot, args.css ?? 'src/index.css');
const outDir = path.resolve(projectRoot, args.out ?? 'dist/paper-ui-export');

const cssText = await readFile(cssPath, 'utf8');
const bundle = generatePaperExport({ cssText });

if (bundle.validationErrors.length > 0) {
  for (const error of bundle.validationErrors) {
    console.error(error);
  }
  process.exit(1);
}

if (args.dryRun) {
  printSummary(bundle, outDir, true);
  process.exit(0);
}

await mkdir(path.join(outDir, 'html'), { recursive: true });
await writeJson(path.join(outDir, 'paper-ui-manifest.json'), bundle.manifest);
await writeJson(path.join(outDir, 'paper-tokens.json'), bundle.tokens);

for (const file of bundle.htmlFiles) {
  await writeFile(path.join(outDir, file.path), `${file.html}\n`, 'utf8');
}

printSummary(bundle, outDir, false);

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--dry-run') {
      parsed.dryRun = true;
    } else if (arg === '--out') {
      parsed.out = argv[index + 1];
      index += 1;
    } else if (arg === '--css') {
      parsed.css = argv[index + 1];
      index += 1;
    } else if (arg === '--help') {
      printHelp();
      process.exit(0);
    } else {
      console.error(`Unknown argument: ${arg}`);
      printHelp();
      process.exit(2);
    }
  }
  return parsed;
}

function printHelp() {
  console.log(`Usage: node scripts/export-paper-ui.mjs [--dry-run] [--out <dir>] [--css <path>]

Creates a source-derived Paper UI bundle:
  paper-ui-manifest.json
  paper-tokens.json
  html/*.html
`);
}

function printSummary(bundle, targetDir, dryRun) {
  const mode = dryRun ? 'validated' : 'written';
  console.log(`Paper UI export ${mode}`);
  console.log(`Target: ${targetDir}`);
  console.log(`Artboards: ${bundle.manifest.artboards.length}`);
  console.log(`Tokens: ${bundle.tokens.length}`);
}

async function writeJson(filePath, value) {
  await writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}
