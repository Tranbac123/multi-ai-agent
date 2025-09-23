# Repo tree migration (Control-Plane / Data-Plane)

Dry-run:

```bash
python scripts/migrate_tree.py
```

Apply changes:

```bash
python scripts/migrate_tree.py --apply
```

After run:

- Review diffs (moved `services/*` → `apps/{data,control}-plane/*`).
- Verify each service has `observability/` and `contracts/openapi.yaml`.
- Check `.github/workflows/*` path filters updated.
- Remove legacy directories if any `*-legacy` remained.
