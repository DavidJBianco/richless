# SIGINT race evidence

The release promotion run 35013487890 on hosted macOS/Python 3.13 failed during
formatted-follow interruption. Both saved terminal transcripts show an uncaught
KeyboardInterrupt at the supervisor's `while True` boundary, outside its narrow
try/except around `wait()`.

The deterministic before/after reproducer sends SIGINT at that exact boundary
using a trace hook. It fails before the fix and passes afterward. The supervisor
now installs a callable SIGINT handler for its entire session; exec resets that
handler in the native pager, which continues to own terminal interrupts. This is
an implementation race, not evidence against replacement-file compatibility.
Required follow behavior is retained; no assertion was weakened or skipped.
