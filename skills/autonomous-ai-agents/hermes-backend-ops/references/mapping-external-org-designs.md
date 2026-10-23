# Mapping an external hierarchical org design onto Hermes kanban

Procedure for taking an AI organization defined elsewhere (custom YAML
personas/stages, a CrewAI-style role plan, a whiteboard org chart) and
verifying it can run on Hermes — with live evidence, not assumptions.

## Procedure

1. **Read the external definitions first**, in full: personas/roles, stage
   templates, tool allowlists, review/acceptance rules, LLM bindings. Classify
   each role as decompose-only vs produce-artifacts; note who holds review
   authority and how human escalation works. Do not map from a description —
   the stage templates usually carry the real rules.
2. **Check the installed CLI before claiming capability**: `hermes kanban
   --help`, `hermes kanban create --help`, `hermes profile list`. Verbs vary
   by version; the ones you assert exist must have come out of `--help` or a
   live run, not memory.
3. **Core mapping**:
   - Stage/role → kanban task, `--assignee` = profile name. Profiles are the
     roster the orchestrator discovers via `hermes profile list`; there is no
     fixed role table, so role names become profile names.
   - Breakdown stages → parent tasks; executors → leaf tasks carrying
     `--parent` on their breakdown parent (dependency rides on the child).
   - Acceptance review + rework loop → `kanban request-review` on the
     implementer, reviewer profile issues `request-changes` (routed back to
     the original implementer) or approves with `complete`.
   - Escalate-to-human → `kanban block` (human unblocks after answering).
   - Role-permitted-tools → per-profile toolsets (e.g. an orchestrator
     profile excludes `terminal/file/code/web`).
4. **Build an inert skeleton first** (see the demo recipe in SKILL.md: root
   `--triage`, children `--parent`). Verify the chain with `list` + `stats`
   before any live run; only then promote stage by stage.
5. **Gap analysis, marked explicitly** ✅ = live-verified on this host,
   📄 = docs/`--help` only. Typical Hermes-side gaps vs strict orchestration
   frameworks: machine-checkable acceptance-condition validation of children
   output (use a custom skill or reviewer convention), fine-grained
   object/action permissions per role (kanban gates at toolset granularity;
   file-area and command-level whitelists need a plugin), and cost/request
   caps (per-task `max-runtime`/`max-retries` only, no aggregate kickoff cap).
6. **Live-run prerequisites**: one profile per persona (SOUL.md carries the
   backstory), and LLM secrets persisted in `$HERMES_HOME/.env` — workers are
   fresh processes that read that file, not the serve process's environment.

## Reference distill: task_ambi (user's CrewAI + beads system)

User's own orchestration system; definition root `<repo>/task_ambi_data/`
(`settings/global/{agents,tasks}.yaml`, `trigger/triggers.yaml`,
`beads/.beads` issue board).

- Hierarchy of stage templates: `program` (planner, routes request into
  projects) → `project` (project_lead, → workstreams) → `subrequest`
  (system_engineer / doc_lead, → leaf tasks) → `child` (architect /
  programmer / analyst / writer, produces outcomes) plus `plain`
  (non-decomposed work) and review stages `review_normal` / `review_final`
  (final one re-checks the parent's whole acceptance set).
- Authority = tools: decomposition stages hold only `propose_breakdown`
  (they cannot complete or write); only `child` holds `write_outcome` +
  `complete_issue`; review holds only `submit_review`. Enforced with a
  Casbin model (`model.conf`) + per-project `policy.csv` and vault
  read/write regions per persona.
- Stage templates impose: `- [ ] `-prefixed machine-checkable acceptance
  conditions, verbatim inheritance of outcome file names down the tree,
  `depends_on` as sibling indexes, and one-shot `propose_breakdown`.
- Mapping status on this host: parent chains ✅ (demo board built),
  request-review/request-changes loop ✅ (verbs confirmed),
  swarm/decompose ✅ (verbs confirmed). Gaps: template validation rules and
  Casbin-grained permissions — cover with worker skills / profile toolsets,
  not with board features.