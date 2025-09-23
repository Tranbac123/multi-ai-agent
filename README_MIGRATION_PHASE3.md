# Tree migration – Phase 3

Dry-run:

```bash
python scripts/migrate_tree_phase3.py
```

Apply changes:

```bash
python scripts/migrate_tree_phase3.py --apply
```

This phase:

- Renames agents/tools/memory to agents-service/tools-service/memory-service
- Moves configs into per-service Helm values
- Organizes monitoring at platform level
- Moves service-specific contracts from /contracts to each service
- Updates CI workflow path filters
- Ensures complete observability scaffolding for all services
