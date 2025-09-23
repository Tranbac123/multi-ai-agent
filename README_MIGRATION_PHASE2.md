# Tree migration – Phase 2

Dry-run:

```bash
python scripts/migrate_tree_phase2.py
```

Apply changes:

```bash
python scripts/migrate_tree_phase2.py --apply
```

This phase:

- Reorganizes remaining services into apps/data-plane/ and apps/control-plane/
- Moves frontends (admin-portal, web-frontend) out of apps/ to root level
- Migrates service-specific contracts from /contracts/ to each service
- Updates CI workflow path filters
- Scaffolds complete service structure for all services
