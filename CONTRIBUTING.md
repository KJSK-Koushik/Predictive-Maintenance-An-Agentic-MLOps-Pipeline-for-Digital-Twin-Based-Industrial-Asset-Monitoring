# Contributing

## Phase control

Before changing the repository:

1. Read the source-of-truth documents linked from `README.md`.
1. Confirm the active phase and state in `docs/PROJECT_STATUS.md`.
1. Verify that the proposed change is within that phase.
1. Add or update tests and documentation with the change.

Do not begin a later phase, even when its work appears small or convenient.

## Security

- Never commit credentials, tokens, service-role keys, database passwords,
  private URLs, or copied local environment files.
- Never commit NASA C-MAPSS data, generated features, models, or reports.
- Use placeholders only in `.env.example`.
- Report suspected secret exposure immediately and rotate the credential before
  relying on history rewriting.

## Quality checks

Run the commands documented in `README.md` before opening a pull request. Local
success is necessary but does not substitute for a successful GitHub Actions
run.

## Pull requests

A pull request should identify:

- the approved phase;
- the acceptance criterion it satisfies;
- test and security evidence;
- documentation and ADR impact;
- known limitations and deferred work; and
- whether any cloud integration was real, emulated, or mocked.

Deployment and model promotion are separate approved operations. A code pull
request must not silently deploy or promote a model.
