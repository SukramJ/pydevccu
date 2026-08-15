# ReGa test corpus

Verbatim copies of the ReGa scripts that
[aiohomematic](https://github.com/sukramj/aiohomematic) ships in
`aiohomematic/rega_scripts/`. A client sends these files unchanged apart
from substituting its `##placeholder##` parameters, so they are the
contract the engine has to satisfy.

They are **test fixtures, not source** — do not edit them here. To
refresh, copy them over from `../aiohomematic/aiohomematic/rega_scripts/`
and fix whatever `test_every_script_is_routed_by_name` then reports.

The reason this corpus exists: the engine used to be tested with
hand-written script fragments, which every handler matched happily while
the real scripts were routed to the wrong handler entirely.
