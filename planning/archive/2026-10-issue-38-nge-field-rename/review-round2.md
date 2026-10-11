# Review round 2: branch 38 (5bae813...bc64f36)

Focus: the round 1 fix, `registry_conflicts()` (bc64f36).

Reach: it runs in `main()` straight after `load_registry`, before the rebuild/additive
split and before any write, so it covers both paths. It does not run under
`--selftest`, which is correct. On the real `data/sites.csv` (85 rows, 18 codes, the 2
`published=false` rows included, 1 row with blank code and name) it returns `[]`. No
code or name carries surrounding whitespace, and every code is upper case. It strips
values the same way `registry_props` does, so whitespace cannot make it fire falsely.

## Findings

- **[bug]** scripts/item_create.py:106-119: the premise "Code and name are one-to-one in
  the atlas" is false, so the `by_name` arm can refuse a correct registry, and its
  remedy cannot clear the refusal. The BC Freshwater Atlas has two watershed groups
  named **Salmon River**: `SALM` (watershed_group_id 176) and `SALR` (id 177). I
  measured this on the same fwapg endpoint the fill script uses: 246 groups, 1
  duplicated name, 0 duplicated codes. If the registry ever holds one row in each
  group, `registry_conflicts` returns `["name 'Salmon River' has codes ['SALM', 'SALR']"]`.
  `main()` then exits REFUSED on every `--rebuild` and every additive run, so
  `catalogue_release.sh` and `dataset_publish.sh` are both blocked.
  - **The remedy does not clear it.** The message says to run
    `scripts/sites_fill-wsg_name.py --write`, but that script considers the rows
    correct.
  - **Reproduced.** I appended a SALR row and a SALM row to a copy of the registry. The
    fill script reported `19 codes, 0 row(s) to change`, and `registry_conflicts` on the
    same copy returned the refusal above. Work copy:
    `scratchpad/review/work2/sites_salmon.csv`.
  - **Likelihood.** SALR is the Salmon River that joins the Fraser north of Prince
    George, inside the Fraser region this registry already covers (CRKD, LCHL, NECR,
    MORK).
  - **This is the round 1 defect one axis over:** a guard whose correctness rests on a
    reasoned fact about a third party, here atlas name uniqueness, rather than one read
    from the atlas.
  - **The `by_code` arm is sound**, because codes are unique (0 duplicates), and it
    alone catches "one code, two names".
  - **Fix options.**
    1. Drop the `by_name` arm. This loses the stale-name case where the new code is
       lone but the old name is shared.
    2. Exempt names that the atlas itself gives to more than one code. That is a
       vendored fact, so record its date.
    3. Compare each row's (code, name) pair against the atlas's pairs. That is what the
       fill script already does, and it needs the network.

  The selftest case "a changed code beside its stale name passes" (line 265) currently
  passes only through the `by_name` arm, so it has to change with any fix.

- **[fragile]** scripts/item_create.py:97-104: a row with a name and no code passes every
  guard and publishes `fwa:watershed_group_name` with no `fwa:watershed_group_code`.
  This is the mirror of the code-without-name case that `registry_problems` refuses.
  - **Why `registry_conflicts` misses it:** it skips any row without both fields
    (`if code and name`).
  - **How it arises:** a code is cleared because it was wrong, and the name it was
    filled from stays.
  - **Measured on a copy:** `registry_problems` returns `[]` and `registry_conflicts`
    returns `[]`. `registry_props` emits `{'newgraph:region', 'fwa:watershed_group_name':
    'Bulkley River', 'uav:stream_name'}`. The item then carries an atlas name that is
    probably stale, and a CQL2 filter on `fwa:watershed_group_code` cannot find it.
  - **The fill script would blank that name, but nothing forces it to run.** For this
    case the per-row check is as cheap as the existing one:
    `name and not code` → refuse.
  - **The selftest does not catch it:** it covers blank code with blank name (line 261)
    but not blank code with a name.

## Checked and sound

- `registry_conflicts` is reached on both paths before any write, and is silent on the
  real registry, including the `published=false` rows and the blank-code row.
- The ast read of `FIELD_PREFIXES` in `catalogue_release.sh` works: `literal_eval`
  accepts a set literal, and `next()` raising on a missing or annotated assignment
  fails closed through `|| exit 1`.
- The `dataset_publish.sh` comment "refusal comes after the COG copy, before any upload"
  matches the script: `cp` at line 76, `item_create.py` at line 83, the first `aws s3`
  call at line 101.
- The fill script's strip and blank rules match `item_create.py`'s.
- The fill script refuses a code the atlas does not know, including a lower-case code,
  before it writes anything.
- `--selftest` passes on HEAD.
