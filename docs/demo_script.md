# Demo Script

1. Start stack:

```bash
docker compose up --build -d
```

2. Create auth token:

```bash
curl -X POST http://localhost:8500/auth/token -H "Content-Type: application/json" -d "{\"user_id\":\"USR-301\",\"role\":\"passenger\"}"
```

3. Execute booking workflow:

```bash
python scripts/demo_pipeline.py
```

4. Open dashboard:

- Frontend: `http://localhost:5177`
- Gateway dashboard endpoint example: `http://localhost:8500/dashboard/TRIP-DEMO-2/USR-301`

5. Verify quality status:

```bash
curl http://localhost:8500/quality/targets
```

6. Shutdown:

```bash
docker compose down
```
