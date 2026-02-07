# stac_uav_bc

STAC catalog for UAV imagery in British Columbia, organized by watershed. Served via API at [images.a11s.one](https://images.a11s.one) and queryable with `rstac` and QGIS (v3.42+).

## Repository Context

**Repository:** NewGraphEnvironment/stac_uav_bc
**Primary Languages:** R, Shell, Quarto

## Architecture

- `stac_create_*.qmd` - Quarto docs for creating STAC catalogs, collections, and items
- `scripts/functions.R`, `scripts/utils.R` - Shared R functions
- `scripts/cog_convert.R` - COG (Cloud Optimized GeoTIFF) conversion
- `scripts/odm_process.R` - OpenDroneMap processing pipeline
- `scripts/s3_*.R` - S3 storage sync, indexing, and mapping
- `scripts/web.R` - Web/viewer utilities
- `scripts/config/` - Server setup, STAC FastAPI, TiTiler, Certbot, registration scripts

## Dependencies

- `rstac` - STAC API queries from R
- S3-compatible object storage for imagery
- STAC FastAPI + TiTiler on server side
- OpenDroneMap for drone image processing

---

# LLM Behavioral Guidelines

<!-- Source: https://github.com/forrestchang/andrej-karpathy-skills/main/CLAUDE.md -->
<!-- Last synced: 2026-02-06 -->
<!-- These principles are hardcoded locally. We do not curl at deploy time. -->
<!-- Periodically check the source for meaningful updates. -->

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

# New Graph Environment Conventions

Core patterns for professional, efficient workflows across New Graph Environment repositories.

## Issue Creation Guidelines

### Professional Issue Writing

Write issues with clear technical focus:

- **Use normal technical language** in titles and descriptions
- **Focus on the problem and solution** approach
- **Avoid internal project codes or tracking references** in the main description
- **Add tracking links at the end** if needed (e.g., `Relates to Owner/repo#N`)

**Why:** Issues are read by consultants, clients, and collaborators. Keep them professional and focused on technical content.

**Example:**
```markdown
## Problem
The DEM processing pipeline is slow for large datasets.

## Proposed Solution
Add structured logging and performance benchmarking to identify bottlenecks.
```

### GitHub Issue Creation - Always Use Files

The `gh issue create` command with heredoc syntax fails repeatedly with EOF errors. ALWAYS use intermediate file approach:

```bash
# Write issue body to scratchpad file first
cat > /path/to/scratchpad/issue_body.md << 'EOF'
## Problem
...

## Proposed Solution
...
EOF

# Then create issue from file
gh issue create --title "Brief technical title" --body-file /path/to/scratchpad/issue_body.md
```

**Why:** Reliable, works every time, no syntax errors. Saves time and tokens.

## Commit Quality

Write clear, informative commit messages:

```
Brief description (50 chars or less)

Detailed explanation of changes and impact.
- What changed
- Why it changed
- Relevant context

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

**When to commit:**
- Logical, atomic units of work
- Working state (tests pass)
- Clear description of changes

**What to avoid:**
- "WIP" or "temp" commits in main branch
- Combining unrelated changes
- Vague messages like "fixes" or "updates"
