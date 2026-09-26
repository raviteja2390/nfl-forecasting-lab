import { readFile } from 'node:fs/promises';
import { evaluate } from './evaluate.mjs';

const args = process.argv.slice(2);
if (args.length === 1 && ['--help', '-h'].includes(args[0])) {
  console.log('Usage: node forecasting/cli.mjs INPUT.json [--as-of UTC_ISO_TIMESTAMP]');
} else if (!(args.length === 1 || (args.length === 3 && args[1] === '--as-of'))) {
  console.error('Usage: node forecasting/cli.mjs INPUT.json [--as-of UTC_ISO_TIMESTAMP]');
  process.exitCode = 1;
} else {
  try {
    const input = JSON.parse(await readFile(args[0], 'utf8'));
    console.log(JSON.stringify(evaluate(input, args[2]), null, 2));
  } catch (error) {
    console.error(`Evaluation failed: ${error instanceof SyntaxError ? 'invalid JSON' : error.message}`);
    process.exitCode = 1;
  }
}
