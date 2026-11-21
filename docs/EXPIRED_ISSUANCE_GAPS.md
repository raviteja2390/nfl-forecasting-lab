# Expired issuance and collection health

A missing forecast whose 24-hour issue deadline has passed is recorded as an
`issuanceGaps` entry in the immutable cycle report, not retried as new issuance.
The persistent forecast coverage report retains missed games and model versions;
its independent, deduplicated coverage alert remains enabled. A successful
collection does not mean complete forecast coverage.

The gate uses the scheduled kickoff minus 24 hours and, for missing player
shadows, never extends the original saved team forecast's deadline. Exact-boundary
attempts still pass through the publishers' existing start and finish checks.
No forecast is backdated, regenerated, or filled retrospectively. Frozen model
artifacts and inference code are unchanged.

Source fetch failures, integrity errors, storage failures, and pre-deadline
schedule mismatches still fail collection. This change neither approves disputed
kickoff times nor suppresses HTTP 403 errors. Historical gaps cannot be repaired
by a successful later collection.
