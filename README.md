# Campus Sensor Monitoring & Alert Engine

## 1. Project Overview

The Campus Sensor Monitoring & Alert Engine is an enterprise-grade backend system designed for large-scale Internet of Things (IoT) campus environments. The platform ingests real-time telemetry from thousands of heterogeneous sensors, evaluates dynamic multi-tiered alert rules with sub-millisecond overhead, prevents alert storms via distributed cooldown mechanisms, and provides high-performance operational APIs for campus administrators and event organizers.

### Primary Engineering Objective
The engine is specifically optimized to process bursts of **10,000 sensor readings within one second** while simultaneously:
- Ingesting and validating incoming sensor payloads.
- Evaluating real-time threshold and sliding-window rules.
- Generating and deduplicating alerts via Redis cooldown locks.
- Persisting telemetry and alert records.
- Serving operational REST queries with low latency (P95 < 50ms).

---

## 2. Architecture

The system utilizes an asynchronous, non-blocking layered architecture built on top of FastAPI, asyncpg, SQLAlchemy 2.0, and Redis.

```
+-----------------------------------------------------------------------------------+
|                         IoT Sensors & Load Simulator                              |
+-----------------------------------------------------------------------------------+
                                          |
                                          | POST /api/v1/readings (Up to 10k/sec)
                                          v
+-----------------------------------------------------------------------------------+
|                            FastAPI Ingestion Tier                                 |
|                                                                                   |
|  [Logging & Correlation] -> [Pydantic Validation] -> [In-Memory Rule Cache]       |
|                                                            |                      |
|                  +-----------------------------------------+                      |
|                  |                                         |                      |
|                  v                                         v                      |
|  [PostgreSQL Bulk Ingest (Asyncpg)]      [Real-Time Rule Evaluation Engine]       |
+-----------------------------------------------------------------------------------+
                   |                                         |
                   v                                         v
        +----------------------+                  +---------------------+
        |  PostgreSQL Database |                  |    Redis Cluster    |
        |                      |                  |                     |
        | - users              |                  | - Sliding Windows   |
        | - sensors            |                  | - Cooldown Locks    |
        | - sensor_readings    |                  | - Sorted Sets       |
        | - alert_rules        |                  +---------------------+
        | - alerts             |
        +----------------------+
```

### Architectural Highlights
- **Repository Pattern & Service Layer**: Complete decoupling of HTTP transport, domain logic, and persistent storage.
- **In-Memory Rule Cache (`RuleCacheService`)**: Enabled rules are indexed by sensor type in memory, avoiding database reads during telemetry ingestion. The cache is automatically invalidated on any rule mutation.
- **Redis Sliding Windows (`SlidingWindowManager`)**: Aggregations (`AVG`, `MIN`, `MAX`, `COUNT`) over moving time windows (1m to 1h) are computed in Redis via pipelined sorted sets (`ZADD` / `ZRANGEBYSCORE`), eliminating costly database aggregation queries.
- **Distributed Cooldown Engine (`CooldownManager`)**: Atomic Redis `SET NX` locks prevent duplicate alerts for continuous sensor breaches.
- **Bulk Ingestion Optimization**: Multi-row batch inserts via `asyncpg` prepared statements minimize round trips and write-ahead log contention.

---

## 3. Tech Stack

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.13 | Native typing improvements, enhanced garbage collector performance |
| **Web Framework** | FastAPI 0.121 | High-performance ASGI framework with native async support |
| **Database** | PostgreSQL 16 | Relational consistency, compound indexes, JSONB support |
| **ORM** | SQLAlchemy 2.0 (Async) | Strict type checking, AsyncSession, multi-row bulk insert |
| **Migrations** | Alembic | Version-controlled database schema migrations |
| **Validation** | Pydantic V2 | Rust-accelerated JSON parsing and validation |
| **Cache / Windows** | Redis 7.2 | Microsecond in-memory sorted sets and atomic locks |
| **Authentication** | JWT (PyJWT) + bcrypt | Stateless token-based auth with cryptographic password hashing |
| **Configuration** | pydantic-settings | Type-safe environment variable parsing from `.env` |
| **Logging** | Structlog | Contextual, JSON-formatted structured logging |
| **Server** | Uvicorn | High-throughput asynchronous ASGI server |
| **Testing** | Pytest + pytest-asyncio | Hermetic async unit and integration test suite |
| **Load Testing** | Locust | Distributed multi-user load testing and stress benchmarking |

---

## 4. Folder Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth/          # Authentication endpoints
│   │       ├── sensors/       # Telemetry ingestion and query routes
│   │       ├── rules/         # Rule definition and lifecycle endpoints
│   │       ├── alerts/        # Alert triage, acknowledgment, and resolution
│   │       └── simulator/     # Load simulator control APIs
│   │
│   ├── core/                  # Security, logging, exceptions, responses
│   ├── config/                # Pydantic BaseSettings configuration
│   ├── database/              # Async database session and declarative base
│   ├── redis/                 # Redis client, sliding window, cooldown manager
│   ├── middleware/            # Logging and global exception handlers
│   ├── models/                # SQLAlchemy ORM declarative models
│   ├── schemas/               # Pydantic validation schemas and DTOs
│   ├── repositories/          # Data access abstraction layer
│   ├── services/              # Pure domain business logic
│   ├── workers/               # Background task workers
│   ├── utils/                 # Time and mathematics utilities
│   └── dependencies/          # FastAPI Depends() injection providers
│
├── alembic/                   # Database versioning and migration scripts
├── tests/
│   ├── unit/                  # Unit tests (security, rules, sliding window, cooldown)
│   └── integration/           # Integration tests (auth, ingestion, rules, alerts)
├── scripts/                   # CLI simulator executable
├── load_testing/              # Locust load test scripts and benchmark runner
├── docs/                      # Architectural specifications
├── docker/                    # Multi-worker production Dockerfile
├── docker-compose.yml         # Containerized development & production stack
├── pytest.ini                 # Pytest configuration
├── requirements.txt           # Pinned production dependencies
└── README.md                  # System manual
```

---

## 5. Installation & Setup

### Prerequisites
- Python 3.13 or higher
- PostgreSQL 16+
- Redis 7.0+
- Docker and Docker Compose (optional for containerized deployment)

### Local Environment Setup
1. Clone the repository and navigate to the project directory:
   ```bash
   git clone <repository-url>
   cd gdg_backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Install project dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```

---

## 6. Environment Variables

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | Runtime environment (`development`, `testing`, `production`) |
| `DEBUG` | `false` | Enables SQL echoing and debug logging |
| `HOST` | `0.0.0.0` | API bind address |
| `PORT` | `8000` | API bind port |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/campus_sensors` | Async PostgreSQL connection URI |
| `DATABASE_POOL_SIZE` | `25` | Base connection pool size |
| `DATABASE_MAX_OVERFLOW` | `50` | Maximum temporary connection pool overflow |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URI |
| `REDIS_MAX_CONNECTIONS`| `100` | Connection pool limit for Redis |
| `JWT_SECRET` | `super-secret-production-key-change-me` | Secret key for signing JWT tokens |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Lifespan of access tokens |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Lifespan of refresh tokens |
| `DEFAULT_ALERT_COOLDOWN_SECONDS` | `300` | Default suppression cooldown for rules |
| `RULE_CACHE_TTL_SECONDS` | `60` | Background cache TTL for active rules |

---

## 7. Database Migration

Database migrations are managed via Alembic:

```bash
# Upgrade database schema to latest version
alembic upgrade head

# Roll back the last migration
alembic downgrade -1

# Create a new revision after schema changes
alembic revision --autogenerate -m "describe_changes"
```

---

## 8. Running the Application

### Running Locally with Uvicorn
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Running with Docker Compose
The included `docker-compose.yml` provisions PostgreSQL (with write-optimized parameters), Redis, and a 4-worker FastAPI container:

```bash
# Start all services in the background
docker compose up -d --build

# Inspect service logs
docker compose logs -f api

# Stop all services and preserve data volumes
docker compose down
```

---

## 9. Authentication & Authorization

The system enforces JSON Web Token (JWT) authentication with Role-Based Access Control (RBAC).

### Roles
- `organizer`: Full permissions. Can create/modify rules, triage/resolve alerts, and operate the sensor load simulator.
- `viewer`: Read-only access to sensors and alerts. Cannot mutate rules or trigger simulations.

### Authentication Endpoints
- `POST /api/v1/auth/register`: Register new account (`email`, `password`, `full_name`, `role`).
- `POST /api/v1/auth/login`: Authenticate and receive `access_token` and `refresh_token`.
- `POST /api/v1/auth/refresh`: Exchange a valid refresh token for a new token pair.
- `GET /api/v1/auth/me`: Inspect current authenticated identity.

---

## 10. Sensor Ingestion Specification

### Telemetry Payload Format
Incoming readings support both snake_case and camelCase attributes:
```json
{
    "sensorId": "library-floor-2",
    "type": "temperature",
    "value": 34.5,
    "timestamp": "2026-10-12T10:30:00Z"
}
```

### Extensible Sensor Types
Supported standard types include:
- `temperature`
- `humidity`
- `occupancy`
- `air_quality`
- `noise`
- `light`

The schema is dynamic: any arbitrary new sensor type string (e.g., `water_pressure`, `co2_level`) is accepted and indexed automatically without requiring database migrations.

### Ingestion API
`POST /api/v1/readings` accepts either a single reading object or an array of up to 10,000 readings:

```bash
curl -X POST http://localhost:8000/api/v1/readings \
  -H "Content-Type: application/json" \
  -d '[
    {"sensorId": "hall-a-temp", "type": "temperature", "value": 36.2, "timestamp": "2026-10-12T10:30:00Z"},
    {"sensorId": "hall-a-hum", "type": "humidity", "value": 18.0, "timestamp": "2026-10-12T10:30:00Z"}
  ]'
```

Response:
```json
{
    "success": true,
    "message": "Readings processed successfully",
    "data": {
        "total_received": 2,
        "ingested_count": 2,
        "failed_count": 0,
        "alerts_triggered": 1,
        "duration_ms": 14.25
    }
}
```

---

## 11. Rule Engine Specification

Organizers can define two categories of alert rules:

### 1. Threshold Rules
Evaluated instantly against individual sensor values.
- Supported operators: `>`, `>=`, `<`, `<=`, `==`, `!=`
- Example: `temperature > 35.0`

### 2. Time Window Rules
Evaluated against rolling aggregate calculations maintained in Redis.
- Supported aggregations: `AVG`, `MIN`, `MAX`, `COUNT`
- Supported windows: `1m` (60s), `5m` (300s), `10m` (600s), `30m` (1800s), `1h` (3600s)
- Example: `Average temperature over last 10 minutes > 35.0`

### Rule Management Endpoints
- `POST /api/v1/rules`: Create rule (Organizer only).
- `GET /api/v1/rules`: List rules (supports `sensor_type` and `enabled` query filters).
- `GET /api/v1/rules/{id}`: Retrieve rule details.
- `PUT /api/v1/rules/{id}`: Update rule configuration.
- `DELETE /api/v1/rules/{id}`: Delete rule.
- `PATCH /api/v1/rules/{id}/enable`: Enable rule.
- `PATCH /api/v1/rules/{id}/disable`: Disable rule.

---

## 12. Alert Management & Lifecycle

### Alert State Machine
```
[ Trigger Event ] -> (OPEN) -> [ Acknowledge ] -> (ACKNOWLEDGED) -> [ Resolve ] -> (RESOLVED)
```

### Duplicate Prevention (Cooldown Mechanism)
To eliminate alert fatigue during prolonged outages, each rule enforces a configurable `cooldown_seconds` (default: 300s). An atomic Redis lock (`SET alert:cooldown:{rule_id}:{sensor_id} 1 EX {cooldown} NX`) suppresses repeated alerts from the same sensor until the cooldown period expires.

### Alert Management Endpoints
- `GET /api/v1/alerts`: Paginated search with filtering (`status`, `severity`, `sensor_id`, `rule_id`, date range).
- `GET /api/v1/alerts/{id}`: Get single alert record.
- `PATCH /api/v1/alerts/{id}/acknowledge`: Mark alert as `ACKNOWLEDGED`.
- `PATCH /api/v1/alerts/{id}/resolve`: Mark alert as `RESOLVED`.
- `DELETE /api/v1/alerts/{id}`: Delete alert record.

---

## 13. Sensor Simulator

The simulator provides both a programmatic API and a standalone CLI tool to stress-test the ingestion engine under realistic campus conditions.

### API Trigger
```bash
curl -X POST http://localhost:8000/api/v1/simulator/start \
  -H "Authorization: Bearer <ORGANIZER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "number_of_sensors": 1000,
    "duration_seconds": 60,
    "batch_size": 500,
    "frequency_per_second": 20
  }'
```

### CLI Simulator
Run the simulator directly against local or remote instances:
```bash
python scripts/simulate.py --sensors 1000 --duration 60 --batch-size 500 --frequency 20
```

---

## 14. Load Testing & Benchmarks

### Primary Goal Benchmark (10,000 readings in 1 second)
Run the dedicated burst benchmark harness:
```bash
python load_testing/benchmark_burst.py
```

### Locust Load Testing
```bash
# Start Locust web interface on http://localhost:8089
locust -f load_testing/locustfile.py --host http://localhost:8000

# Headless execution (100 users, 20 spawn rate, 60 seconds duration)
locust -f load_testing/locustfile.py --host http://localhost:8000 --headless -u 100 -r 20 --run-time 60s
```

Detailed metrics and analysis are documented in [load_testing/PERFORMANCE_REPORT.md](load_testing/PERFORMANCE_REPORT.md).

---

## 15. Performance, Trade-offs & Scalability

### Architectural Trade-offs
1. **In-Memory Rule Caching vs Distributed State**:
   - *Choice*: Rules are cached in-memory within worker processes with instant invalidation on mutation.
   - *Trade-off*: Minimizes DB queries to zero during bursts. Memory usage per pod is negligible (< 2 MB for 10,000 rules).
2. **Redis Sorted Sets for Sliding Windows**:
   - *Choice*: Redis `ZSET` with score pruning.
   - *Trade-off*: Higher memory utilization than fixed time-bucket counters, but delivers exact, continuous sliding-window granularity with exact aggregations.
3. **Synchronous Bulk Persistence vs Asynchronous Queues**:
   - *Choice*: Direct asyncpg bulk insert during the HTTP request lifecycle.
   - *Trade-off*: Guarantees write durability and immediate consistency before returning HTTP 200, achieving > 12,000 readings/sec per node without message loss.

### Future Scalability Roadmap
1. **Message Broker Layer (Apache Kafka / Redpanda)**:
   For ingestion exceeding 100,000 readings/sec, place a Kafka topic before the database writer pool to decouple ingestion latency from disk write IOPS.
2. **TimescaleDB Hypertables**:
   Migrate `sensor_readings` to TimescaleDB to enable automatic chunked time partitioning, compression, and automated rollup policies.
3. **Redis Cluster Sharding**:
   Shard sliding windows across Redis nodes by partitioning keys using `{sensor_id}` hash tags.
