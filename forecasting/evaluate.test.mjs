import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { evaluate, LOG_LOSS_FLOOR, timestamp } from './evaluate.mjs';

const example = JSON.parse(readFileSync(new URL('./example.json', import.meta.url), 'utf8'));
const asOf = '2026-09-26T18:00:00Z';
function fixture() { return structuredClone(example); }
function close(actual, expected) { assert.ok(Math.abs(actual - expected) < 1e-12, `${actual} != ${expected}`); }

test('scores a known probability distribution and baseline independently', () => {
  const data = fixture();
  data.forecasts = data.forecasts.slice(0, 1);
  const report = evaluate(data, asOf);
  close(report.model.brier, 0.2382);
  close(report.model.logLoss, -Math.log(0.65));
  close(report.baseline.brier, 0.4902);
  close(report.improvement.brier, 0.252);
  assert.equal(report.model.accuracy, 1);
});

test('counts ties as their own outcome and abstains on tied top probabilities', () => {
  const report = evaluate(fixture(), asOf);
  assert.equal(report.rows[2].outcome, 'tie');
  close(report.rows[2].model.brier, 1.4406);
  assert.equal(report.rows[2].model.prediction, null);
  assert.equal(report.model.classified, 2);
  assert.equal(report.model.accuracy, 0.5);
  close(report.model.coverage, 2 / 3);
  assert.equal(report.pending, 1);
});

test('excludes outcomes not yet available at the specified evaluation time', () => {
  const report = evaluate(fixture(), '2026-09-06T18:00:00Z');
  assert.equal(report.scored, 0);
  assert.equal(report.pending, 1);
  assert.equal(report.notYetIssued, 3);
  assert.equal(report.model.brier, null);
  assert.equal(report.improvement.brier, null);
});

test('rejects overlap, forecasts at kickoff, late training, and duplicate games', () => {
  const changes = [
    [data => { data.trainingDataThrough = data.evaluationStartsAt; }, /Training data/],
    [data => { data.forecasts[0].generatedAt = data.forecasts[0].kickoffAt; }, /before kickoff/],
    [data => { data.forecasts[0].generatedAt = '2026-08-30T00:00:00Z'; }, /training data extends/],
    [data => { data.forecasts[1].eventId = data.forecasts[0].eventId; }, /duplicate/],
    [data => { data.evaluationStartsAt = '2026-09-07T00:00:00Z'; }, /held-out period/],
  ];
  for (const [change, error] of changes) {
    const data = fixture(); change(data);
    assert.throws(() => evaluate(data, asOf), error);
  }
});

test('rejects malformed probabilities, scores, fields, and impossible dates', () => {
  const changes = [
    data => { data.forecasts[0].probabilities.homeWin = 1.1; },
    data => { data.forecasts[0].probabilities.homeWin = 0.60; },
    data => { data.forecasts[0].probabilities.tie = NaN; },
    data => { data.forecasts[0].result.homeScore = -1; },
    data => { data.forecasts[0].result.awayScore = 1.5; },
    data => { data.forecasts[0].result.finalizedAt = data.forecasts[0].kickoffAt; },
    data => { data.baseline.probabilities.extra = 0; },
  ];
  for (const change of changes) {
    const data = fixture(); change(data);
    assert.throws(() => evaluate(data, asOf));
  }
  assert.throws(() => timestamp('2026-02-30T00:00:00Z'), /invalid date/);
  assert.throws(() => timestamp('2026-09-26T12:00:00'), /UTC ISO/);
});

test('handles certain predictions, including confidently wrong ones', () => {
  const data = fixture();
  data.forecasts = data.forecasts.slice(0, 1);
  data.forecasts[0].probabilities = { homeWin: 1, awayWin: 0, tie: 0 };
  close(evaluate(data, asOf).model.brier, 0);
  close(evaluate(data, asOf).model.logLoss, 0);
  data.forecasts[0].probabilities = { homeWin: 0, awayWin: 1, tie: 0 };
  close(evaluate(data, asOf).model.brier, 2);
  close(evaluate(data, asOf).model.logLoss, -Math.log(LOG_LOSS_FLOOR));
});

test('empty datasets report no evidence, and input is not mutated', () => {
  const data = fixture();
  const original = structuredClone(data);
  evaluate(data, asOf);
  assert.deepEqual(data, original);
  data.forecasts = [];
  const report = evaluate(data, asOf);
  assert.equal(report.scored, 0);
  assert.equal(report.model.accuracy, null);
});

test('CLI accepts the example and rejects invalid arguments with a nonzero exit', () => {
  const cli = fileURLToPath(new URL('./cli.mjs', import.meta.url));
  const input = fileURLToPath(new URL('./example.json', import.meta.url));
  const valid = spawnSync(process.execPath, [cli, input, '--as-of', asOf], { encoding: 'utf8' });
  assert.equal(valid.status, 0, valid.stderr);
  assert.equal(JSON.parse(valid.stdout).scored, 3);
  const invalid = spawnSync(process.execPath, [cli, input, '--as-of'], { encoding: 'utf8' });
  assert.equal(invalid.status, 1);
});
