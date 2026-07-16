# fastkit-testkit

Testing helpers for FastKit projects.

## Installation

```bash
pip install fastkit-testkit
```

## Clock

`FrozenClock` gives deterministic time: call it for the current instant, `tick`
to advance and `set` to jump.

## Factories

`Factory` builds dictionaries from `defaults` (values or `index -> value`
callables) with a per-instance `Sequence`. `build_batch` produces many.

## Database

`managed_database(metadata, directory)` yields a ready SQLite `Database` with the
schema created and disposes it on exit. `sqlite_url` builds the URL.

## Envelope assertions

`assert_success(envelope)` returns the data, `assert_error(envelope, code)` checks
an error and optional code, `assert_field_error(envelope, field)` finds a field
error.

## Fakes

`RecordingHook` captures event payloads for hook assertions; `FakeMailbox`
collects delivered messages.

## Testing

100% branch coverage.

```bash
pytest packages/fastkit-testkit --cov=fastkit_testkit --cov-branch
```
