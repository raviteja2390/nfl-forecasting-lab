/** Standalone, dependency-free scoring of three-outcome game forecasts. */
export const OUTCOMES = ['homeWin', 'awayWin', 'tie'];
export const LOG_LOSS_FLOOR = 1e-15;

function object(value, path, required, optional = []) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${path}: expected an object`);
  }
  for (const key of required) {
    if (!Object.hasOwn(value, key)) throw new Error(`${path}.${key}: required`);
  }
  if (Object.keys(value).some(key => !required.includes(key) && !optional.includes(key))) {
    throw new Error(`${path}: unexpected field`);
  }
}

function label(value, path) {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${path}: expected a nonempty string`);
}

export function timestamp(value, path = 'timestamp') {
  // Require explicit UTC to avoid machine-dependent timezone interpretation.
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)) {
    throw new Error(`${path}: expected a UTC ISO timestamp`);
  }
  const time = Date.parse(value);
  if (!Number.isFinite(time) || new Date(time).toISOString().replace('.000Z', 'Z') !== value.replace('.000Z', 'Z')) {
    throw new Error(`${path}: invalid date`);
  }
  return time;
}

function probabilities(value, path) {
  object(value, path, OUTCOMES);
  for (const outcome of OUTCOMES) {
    const p = value[outcome];
    if (typeof p !== 'number' || !Number.isFinite(p) || p < 0 || p > 1) {
      throw new Error(`${path}.${outcome}: probability must be between 0 and 1`);
    }
  }
  const total = OUTCOMES.reduce((sum, outcome) => sum + value[outcome], 0);
  if (Math.abs(total - 1) > 1e-10) throw new Error(`${path}: probabilities must sum to 1`);
}

function score(distribution, outcome) {
  const highest = Math.max(...OUTCOMES.map(key => distribution[key]));
  const leaders = OUTCOMES.filter(key => distribution[key] === highest);
  // Equal top probabilities are an abstention, not an arbitrary home-team pick.
  const prediction = leaders.length === 1 ? leaders[0] : null;
  return {
    brier: OUTCOMES.reduce((sum, key) => sum + (distribution[key] - Number(key === outcome)) ** 2, 0),
    logLoss: -Math.log(Math.max(LOG_LOSS_FLOOR, distribution[outcome])),
    prediction,
    correct: prediction === null ? null : prediction === outcome,
  };
}

function aggregate(rows) {
  if (!rows.length) return { brier: null, logLoss: null, accuracy: null, classified: 0, coverage: null };
  const classified = rows.filter(row => row.correct !== null);
  return {
    brier: rows.reduce((sum, row) => sum + row.brier, 0) / rows.length,
    logLoss: rows.reduce((sum, row) => sum + row.logLoss, 0) / rows.length,
    accuracy: classified.length ? classified.filter(row => row.correct).length / classified.length : null,
    classified: classified.length,
    coverage: classified.length / rows.length,
  };
}

export function evaluate(dataset, asOf = new Date().toISOString()) {
  const asOfTime = timestamp(asOf, 'asOf');
  object(dataset, 'dataset', ['schemaVersion', 'modelVersion', 'trainingDataThrough', 'evaluationStartsAt', 'baseline', 'forecasts']);
  if (dataset.schemaVersion !== 1) throw new Error('dataset.schemaVersion: only version 1 is supported');
  label(dataset.modelVersion, 'dataset.modelVersion');
  const trainingEnd = timestamp(dataset.trainingDataThrough, 'dataset.trainingDataThrough');
  const evaluationStart = timestamp(dataset.evaluationStartsAt, 'dataset.evaluationStartsAt');
  if (trainingEnd >= evaluationStart) throw new Error('Training data must end before the evaluation period');
  object(dataset.baseline, 'dataset.baseline', ['name', 'probabilities']);
  label(dataset.baseline.name, 'dataset.baseline.name');
  probabilities(dataset.baseline.probabilities, 'dataset.baseline.probabilities');
  if (!Array.isArray(dataset.forecasts)) throw new Error('dataset.forecasts: expected an array');

  const eventIds = new Set();
  const rows = [];
  let pending = 0;
  let notYetIssued = 0;
  for (const [index, forecast] of dataset.forecasts.entries()) {
    const path = `forecasts[${index}]`;
    object(forecast, path, ['eventId', 'kickoffAt', 'generatedAt', 'probabilities'], ['result']);
    label(forecast.eventId, `${path}.eventId`);
    if (eventIds.has(forecast.eventId)) throw new Error(`${path}: duplicate eventId`);
    eventIds.add(forecast.eventId);
    const kickoff = timestamp(forecast.kickoffAt, `${path}.kickoffAt`);
    const generated = timestamp(forecast.generatedAt, `${path}.generatedAt`);
    if (kickoff < evaluationStart) throw new Error(`${path}: game is outside the held-out period`);
    if (generated >= kickoff) throw new Error(`${path}: forecast must be generated before kickoff`);
    if (generated < trainingEnd) throw new Error(`${path}: training data extends beyond forecast generation`);
    probabilities(forecast.probabilities, `${path}.probabilities`);

    let finalTime = null;
    if (forecast.result != null) {
      object(forecast.result, `${path}.result`, ['homeScore', 'awayScore', 'finalizedAt']);
      for (const side of ['homeScore', 'awayScore']) {
        if (!Number.isSafeInteger(forecast.result[side]) || forecast.result[side] < 0) {
          throw new Error(`${path}.result.${side}: expected a nonnegative integer`);
        }
      }
      finalTime = timestamp(forecast.result.finalizedAt, `${path}.result.finalizedAt`);
      if (finalTime <= kickoff) throw new Error(`${path}: final result must be recorded after kickoff`);
    }

    if (generated > asOfTime) { notYetIssued++; continue; }
    if (finalTime === null || finalTime > asOfTime) { pending++; continue; }
    const { homeScore, awayScore } = forecast.result;
    const outcome = homeScore === awayScore ? 'tie' : homeScore > awayScore ? 'homeWin' : 'awayWin';
    rows.push({
      eventId: forecast.eventId,
      outcome,
      model: score(forecast.probabilities, outcome),
      baseline: score(dataset.baseline.probabilities, outcome),
    });
  }
  const model = aggregate(rows.map(row => row.model));
  const baseline = aggregate(rows.map(row => row.baseline));
  return {
    schemaVersion: 1,
    asOf,
    modelVersion: dataset.modelVersion,
    baselineName: dataset.baseline.name,
    trainingDataThrough: dataset.trainingDataThrough,
    evaluationStartsAt: dataset.evaluationStartsAt,
    total: dataset.forecasts.length,
    scored: rows.length,
    pending,
    notYetIssued,
    model,
    baseline,
    // Positive values mean a lower average loss than this baseline on this sample.
    improvement: {
      brier: rows.length ? baseline.brier - model.brier : null,
      logLoss: rows.length ? baseline.logLoss - model.logLoss : null,
    },
    logLossFloor: LOG_LOSS_FLOOR,
    rows,
  };
}
