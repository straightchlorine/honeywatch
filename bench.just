set positional-arguments

# Performance bench for the sessions list: a git worktree and a prod-shaped Postgres
# per release, numbers written to files. The checkout hosting bench/ is never the
# tree under test. Each script in bench/ documents its usage at the top.

# Add a worktree: `just bench worktree add v0.8.2`, `just bench worktree list`.
worktree *args:
    ./bench/worktrees.sh "$@"

# Create the bench Postgres container.
up *args:
    ./bench/bench.sh up "$@"

# Load honeywatch-prod-data.gz into it.
restore *args:
    ./bench/bench.sh restore "$@"

# Migrate with a release's schema: `BENCH_API_DIR=../honeywatch-wt/0.8.2 just bench prepare`.
prepare *args:
    ./bench/bench.sh prepare "$@"

# Restart Postgres to empty shared_buffers.
restart *args:
    ./bench/bench.sh restart "$@"

# Caps, row counts, alembic version.
status *args:
    ./bench/bench.sh status "$@"

# Print the exports measure.py and alembic need.
env *args:
    ./bench/bench.sh env "$@"

# psql into the bench database.
psql *args:
    ./bench/bench.sh psql "$@"

# Remove the container and its data.
down *args:
    ./bench/bench.sh down "$@"

# Measure a worktree: `just bench measure ../honeywatch-wt/0.8.5 --variant baseline --scenario layout`.
measure repo *args:
    #!/usr/bin/env bash
    set -euo pipefail
    root="$PWD"
    target="$(cd "$1" && pwd)"
    shift
    eval "$("$root/bench/bench.sh" env)"
    export PYTHONPATH="$target/api"
    uv run --project "$target/api" python "$root/bench/measure.py" --repo "$target" "$@"

# Show results.csv as a table: `just bench report --rank wall`, `--scenario route`, `--md --append`.
report *args:
    python3 ./bench/summarize.py "$@"
