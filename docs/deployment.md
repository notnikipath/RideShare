# Deployment

## Requirements

- Docker
- Docker Compose
- Python 3.11 for local lint and tests

## Start

```bash
cd D:\Шарага\Кинжа10\Task_25_RideShare
docker compose up --build -d
```

## Stop

```bash
docker compose down
```

## Validate

```bash
python -m ruff check .
python -m pytest -q
docker compose config
```

## Ports

- `8500` API gateway
- `5177` frontend
- `8501-8508` backend services
- `55435` PostgreSQL
- `6383` Redis
- `5672` RabbitMQ AMQP
- `15672` RabbitMQ management UI
