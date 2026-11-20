# Temporary filming transition

Activated by `../beast-action-guide-20261115/filming-auto-advance.json`, `enabled: true`.
Set `enabled` to `false` before the next console start to restore release-evidence transitions.
Stop any active session before changing this option.

Only S2-S5 are affected. The owned Unity player log is unique to each console run.
The first `[SBS TEXT]` entry with the current state and `tone=Release` starts a
two-second monotonic timer. Later tracking loss does not reset that timer.
The next server update after the deadline advances one stage. Each new screw
needs a new rendered release tone. A logical MOVE CLEAR cue with Attention does
not arm the timer. Normal release-based advancement is disabled in this mode.
This tone log alone does not prove ring or outline visibility; check eye-display
coverage and the actual Unity image before recording.
S0/S1 and the final S6 confirmation remain manual. No calibration or Unity build changes.

This is staged filming behavior, not fastening verification. Server output labels
every trigger and transition `[FILMING TIMER]` with `fastening_verified=false`.
Camera failure or a stopped process cannot advance until processing resumes.
Original recording takes and the production state filter are untouched.
