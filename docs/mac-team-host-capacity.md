# Mac Team Host Capacity

This note records a capacity hypothesis for running many cnb team instances on
one high-memory Mac. It is not a benchmark result yet. Treat the numbers below
as a test target and scheduling plan until we can run the experiment on real
hardware.

## macOS Concurrency Model

macOS can run many background processes from one user account, and it can also
run processes under multiple Unix users. For cnb, that means many team
instances can coexist as tmux sessions, launchd jobs, project worktrees, and
agent CLI processes.

Do not equate this with many full GUI desktops. Multiple logged-in GUI sessions
exist, but they are the wrong scaling unit for cnb teams. GUI automation,
screen-recording permissions, browser profiles, and Accessibility permissions
become the unreliable part long before memory is exhausted.

Recommended default:

- run many teams under one service account when they share the same engine
  credentials and local trust boundary;
- use separate macOS users only when token, Keychain, browser profile, or
  customer-data isolation requires it;
- keep each team in its own project root, tmux session namespace, and board
  state;
- limit the number of GUI/browser-backed teams separately from CLI-only teams.

## Capacity Hypothesis

Observed local baseline: a 16GB Mac can keep roughly 5-10 lightweight team
instances resident when most of them are idle or only responding occasionally.
That implies an effective footprint around 1-3GB per resident team after
including shell, tmux, agent process, repo state, caches, and background noise.

For a hypothetical 512GB high-memory Mac host, reserve memory for macOS,
filesystem cache, provider CLIs, browser/tool spikes, and swap avoidance. A
reasonable planning envelope is 400-450GB of usable budget for cnb resident
teams.

| Workload class | Planning footprint | 512GB target |
|----------------|-------------------:|-------------:|
| Resident idle / low-frequency CLI team | 1-4GB | 100-200 teams |
| Mixed cnb work, some repo reads and small tests | 4-8GB | 60-100 teams |
| Active coding with dev servers and test loops | 10-20GB | 20-40 teams |
| Heavy local builds, browser automation, Xcode, or large repos | 30-60GB | 6-12 teams |

The product target should be: a 512GB host can keep about 100 team instances
resident, with 20-40 allowed to be high-intensity active at the same time. The
remaining teams should be parked, low-frequency, or hibernated.

## Current Hardware Note

The 512GB Mac Studio profile should be rechecked before purchase or test
planning. Apple Support's current Mac Studio (2025) technical specifications
page lists M3 Ultra memory as 96GB configurable to 256GB, while older discussion
and regional pages have referred to higher-memory configurations. Keep this
document framed as "512GB class host" capacity planning until the exact machine
SKU is in hand.

If the available host is 256GB instead, scale the starting target down to about
50 resident teams and 10-20 high-intensity active teams.

## Scheduler Rules

Memory alone is not the real limit. A large host needs admission control:

- cap simultaneously active teams separately from resident teams;
- cap test/build/browser jobs globally, not just per team;
- stagger package installs, test suites, and repo-wide searches;
- hibernate idle teams by stopping dev servers, browsers, and watch processes;
- keep model/API concurrency within provider limits;
- route urgent user-facing work ahead of background maintenance;
- release project leases before suspending or hibernating a team.

Suggested initial knobs:

```toml
[capacity]
resident_team_target = 100
active_team_limit = 32
global_test_job_limit = 8
global_browser_job_limit = 4
idle_hibernate_after_minutes = 60
memory_pressure_hibernate = "warn"
```

These are planning values, not current config keys.

## Benchmark Plan

Run the test in stages. Stop at the first sustained pressure point and record
the reason instead of forcing the machine into swap-heavy behavior.

1. Baseline the current 16GB machine with the existing 5-10 team setup.
2. Measure per-team RSS, child process count, open files, tmux session count,
   board latency, and Feishu route latency.
3. On the high-memory host, start 25 resident CLI-only teams and let them idle.
4. Increase to 50, 100, then 150 resident teams if memory pressure stays green.
5. At each level, activate rolling work batches of 8, 16, 32, and 48 teams.
6. Add realistic mixed work: repo search, small tests, docs edits, dev servers,
   package installs, and browser-backed tasks.
7. Record p50/p95 response time, provider throttling, memory pressure, swap,
   CPU load, and IO wait.

Stop conditions:

- macOS memory pressure stays yellow/red for more than 10 minutes;
- swap grows continuously during an idle or low-frequency phase;
- user-facing route latency exceeds 30 seconds at p95;
- API/provider throttling becomes the dominant failure mode;
- test/build queues starve interactive work.

Useful commands:

```sh
vm_stat
memory_pressure
top -l 1 -o mem
ps axo user,pid,ppid,rss,pcpu,command | sort -nrk4 | head -50
tmux list-sessions
./bin/cnb ps
./bin/cnb feishu status
```

## Expected Product Work

Before treating 100 resident teams as supported, cnb should grow a small
capacity controller:

- resource-pressure reporting in `cnb ps` or a dedicated status command;
- active/resident/hibernated team states;
- global concurrency limits for tests, builds, browser jobs, and model calls;
- per-team resource accounting;
- clear warnings when the machine can keep teams resident but cannot keep them
  all active.

This is related to the Mac wakefulness work in issue #152, but it is a separate
problem. `caffeinate` keeps the host available; capacity control decides how
many teams should actually run.

## References

- Apple Mac Studio (2025) technical specifications:
  <https://support.apple.com/en-ca/122211>
