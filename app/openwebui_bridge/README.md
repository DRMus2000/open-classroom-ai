# Open WebUI 0.11.2 bridge contract

The old bundle used a global Filter as its only gate.  That leaves direct
OpenAI routes and task/title calls outside the Filter.  The new integration
uses the `ClassroomRouteGuardMiddleware` in front of the bundled app and a
Pipe adapter that submits immutable snapshots to the classroom service.  The
middleware denies provider, task, embedding, audio, image, and ordinary chat
completion routes until a signed Pipe handoff is installed and tested.

This fail-closed behavior is deliberate: a package that has not completed the
exact 0.11.2 Pipe registration must remain in maintenance mode instead of
silently falling back to Open WebUI's direct upstream handlers.

The native same-origin routes also bind the verified Open WebUI session to the
classroom roster, account-import preview/commit, password reset, quota and
immutable export operations.  The portable launcher supplies a request-scoped
native account adapter and never writes teacher credentials to the classroom
database.  The launcher mounts the teacher and student classroom pages on the
same Open WebUI origin, so browser cookies are the only browser-side identity
source.
