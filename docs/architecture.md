# Campus Sensor Monitoring & Alert Engine - Architecture Documentation

## 1. High-Level Architecture

The Campus Sensor Monitoring & Alert Engine is an enterprise-grade, distributed IoT ingestion and real-time analytics backend designed for high-throughput, low-latency workloads. It processes streaming sensor telemetry, evaluates multi-criteria threshold and time-window alert rules, suppresses duplicate alert storms, and provides responsive operational APIs for campus organizers.

```
                           +-------------------------------------+
                           |   IoT Sensors & Campus Simulator   |
                           +-------------------------------------+
                                              |
                                              | POST /api/v1/readings (Batches up to 10k/sec)
                                              v
+------------------------------------------------------------------------------------+
|                                 FASTAPI INGESTION PODS                            |
|                                                                                    |
|  +--------------------+    +----------------------+    +------------------------+  |
|  | Logging & Tracking | -> |  Pydantic Validation | -> | In-Memory Rule Cache   |  |
|  |   Middleware       |    |     (Zero-Copy)      |    | (O(1) Sensor-Type Map) |  |
|  +--------------------+    +----------------------+    +------------------------+  |
|                                       |                                            |
|                  +--------------------+---------------------+                      |
|                  |                                          |                      |
|                  v                                          v                      |
|  +-------------------------------+         +------------------------------------+  |
|  |   Bulk Ingestion Engine       |         |   Real-Time Rule Engine            |  |
|  | (Asyncpg Multi-Row Prepared)  |         | (Thresholds + Sliding Windows)     |  |
|  +-------------------------------+         +------------------------------------+  |
+------------------------------------------------------------------------------------+
                   |                                          |
                   v                                          v
      +-------------------------+               +----------------------------+
      |  PostgreSQL Database    |               |  Redis In-Memory Engine    |
      |                         |               |                            |
      | - sensors               |               | - Sorted Sets (ZADD/RANGE) |
      | - sensor_readings       |               | - Window Aggregations      |
      | - alert_rules           |               | - Atomic Cooldown Locks    |
      | - alerts                |               +----------------------------+
      | - users                 |
      +-------------------------+
```

---

## 2. Folder Structure

The project follows a clean, decoupled Enterprise Layered Architecture adhering strictly to SOLID principles, the Repository Pattern, and Dependency Injection:

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth/          # Authentication endpoints (register, login, refresh, me)
│   │       ├── sensors/       # Telemetry ingestion and sensor metadata routes
│   │       ├── rules/         # Rule definition and lifecycle endpoints
│   │       ├── alerts/        # Alert triage, acknowledgment, and resolution
│   │       └── simulator/     # Load simulator control APIs
│   │
│   ├── core/                  # App constants, security, logging, exceptions, responses
│   ├── config/                # Pydantic BaseSettings configuration
│   ├── database/              # Async SQLAlchemy engine, session maker, base models
│   ├── redis/                 # Connection pools, sliding window storage, cooldown locks
│   ├── middleware/            # Correlation ID, latency tracking, global error handling
│   ├── models/                # SQLAlchemy ORM declarative models
│   ├── schemas/               # Pydantic V2 input/output data transfer objects
│   ├── repositories/          # Isolated data access layer
│   ├── services/              # Pure business logic and domain orchestration
│   ├── workers/               # Async background processing and alert dispatching
│   ├── utils/                 # Utility math, datetime, and window helpers
│   └── dependencies/          # FastAPI Depends() injection providers
│
├── alembic/                   # Database versioning and migration scripts
├── tests/                     # Unit and integration test suites
├── scripts/                   # CLI tools and simulator scripts
├── load_testing/              # Locust benchmarks and performance verification
├── docs/                      # Technical specifications and architecture designs
├── docker/                    # Multi-stage production Dockerfile
├── README.md                  # Comprehensive operational manual
├── docker-compose.yml         # Containerized production stack
└── requirements.txt           # Pinned production dependencies
```

---

## 3. Request Lifecycle

1. **Client Request**: An HTTP request reaches Uvicorn ASGI workers.
2. **Logging Middleware**:
   - Generates or extracts `X-Request-ID`.
   - Binds correlation variables (`request_id`, `client_ip`, `path`, `method`) to `structlog` contextvars.
   - Starts high-resolution monotonic timer (`time.perf_counter()`).
3. **Routing & Authentication**:
   - URL matches API router.
   - Dependencies execute (`get_db`, `get_redis`, `get_current_user`, `require_organizer`).
   - Bearer JWT validated against signature and expiration.
4. **Validation Layer**:
   - Pydantic V2 models validate payloads, types, and constraints.
   - Malformed payloads trigger HTTP 422 with structured JSON error envelopes.
5. **Service & Repository Execution**:
   - Routes delegate exclusively to Service Layer classes.
   - Services coordinate Repositories and external caches inside an async transaction context.
6. **Response Generation**:
   - Consistent envelope `{ "success": true, "message": "...", "data": {...} }` returned.
   - Header `X-Response-Time` and `X-Request-ID` attached.
   - Structlog records request completion with HTTP status and elapsed duration in milliseconds.

---

## 4. Sensor Ingestion Flow (Burst Optimization)

To comfortably sustain bursts of **10,000 readings within 1 second**:

```
[ POST /api/v1/readings ]
           |
           v
[ 1. Validate Payload (Fast Pydantic V2) ]
           |
           v
[ 2. Check In-Memory Known Sensors Set ]
   - Unknown sensors: execute ON CONFLICT DO NOTHING insert
   - Known sensors: zero DB overhead
           |
           v
[ 3. Bulk Insert into PostgreSQL (sensor_readings) ]
   - Prepared statement via asyncpg executing multi-row values list
           |
           v
[ 4. Pipeline Redis Sliding Window Update ]
   - ZADD key score member
   - ZREMRANGEBYSCORE key 0 cutoff
   - EXPIRE key 3660
           |
           v
[ 5. Evaluate Rules against In-Memory Rule Cache ]
   - Threshold evaluation in CPU memory (< 1ms)
   - Window evaluation via Redis ZRANGEBYSCORE
           |
           v
[ 6. Filter Duplicates via Atomic Cooldown Lock ]
   - SET alert:cooldown:{rule_id}:{sensor_id} 1 EX cooldown NX
           |
           v
[ 7. Bulk Insert Triggered Alerts (PostgreSQL) ]
           |
           v
[ 8. Return HTTP 200 Ingestion Summary ]
```

---

## 5. Rule Evaluation Engine

### 5.1 Threshold Rules
- **Operators**: `>`, `>=`, `<`, `<=`, `==`, `!=`
- Evaluated directly on the incoming scalar reading value.
- Rules are pre-indexed in memory by `sensor_type`, ensuring O(1) candidate lookup.

### 5.2 Time Window Rules
- **Aggregations**: `AVG`, `MIN`, `MAX`, `COUNT`
- **Windows**: `1m` (60s), `5m` (300s), `10m` (600s), `30m` (1800s), `1h` (3600s)
- Evaluated against historical points retrieved from the Redis sliding window buffer:
  - `start_time = now - window_seconds`
  - Values extracted from Redis sorted sets: `ZRANGEBYSCORE key min max`
  - Aggregation computed and evaluated against rule operator and threshold.

---

## 6. Redis Sliding Window Design

- **Key Schema**: `sw:{sensor_id}:{sensor_type}`
- **Data Structure**: Redis Sorted Set (`ZSET`)
- **Score**: Unix timestamp as floating-point epoch seconds.
- **Member**: `{timestamp}:{value}:{uuid_suffix}`
  - The UUID suffix guarantees member uniqueness even when identical values are recorded at the exact same millisecond.
- **Eviction & Retention**:
  - Retention limit: 3,600 seconds (1 hour).
  - Every batch update runs `ZREMRANGEBYSCORE key 0 (now - 3600)` and sets a 3,660-second TTL.
  - Automatically bounds memory consumption without unbounded key growth.

---

## 7. Duplicate Alert Prevention (Cooldown Engine)

To prevent alert flooding when a sensor remains anomalous for sustained durations:
- **Key Schema**: `alert:cooldown:{rule_id}:{sensor_id}`
- **Operation**: `SET key "1" EX {cooldown_seconds} NX`
- **Semantics**:
  - If Redis returns `True` (lock acquired): This is a fresh alert. Persist alert and notify.
  - If Redis returns `False` (lock exists): The sensor is within its suppression cooldown window. The alert is dropped from generation.

---

## 8. Database Design & Indexing Strategy

### Tables
1. `users`: Stores authentication identities and RBAC roles.
2. `sensors`: Registry of physical and virtual sensors, types, locations, and metadata.
3. `sensor_readings`: High-volume telemetry log.
4. `alert_rules`: Defined threshold and window rules.
5. `alerts`: Active and historical triggered alert events with state transition tracking.

### Indexing Rationale
- `ix_sensor_readings_sensor_id` & `ix_sensor_readings_sensor_type`: Fast point queries.
- `ix_readings_sensor_timestamp` on `(sensor_id, timestamp DESC)`: Enables fast queries for historical graphs.
- `ix_readings_type_timestamp` on `(sensor_type, timestamp DESC)`: Aggregations across campus sensor types.
- `ix_alerts_status_created_at` on `(status, created_at DESC)`: Operational alert dashboard pagination and filtering.
- `ix_rules_type_enabled` on `(sensor_type, enabled)`: Efficient index scan for rule caching.

---

## 9. Horizontal Scaling and High Availability

### 9.1 Stateless API Tier
FastAPI application instances run inside containerized pods behind an L7 load balancer (e.g. AWS ALB, NGINX, Cloudflare). All session state resides in Redis and PostgreSQL, allowing linear horizontal scaling (`replica: 5-50`).

### 9.2 Redis High Availability
Deploy Redis in Sentinel or Cluster mode with primary-replica replication:
- In-memory sliding windows partitioned across shards by hash tag `{sensor_id}`.

### 9.3 PostgreSQL Tuning for 10k+ Writes/Sec
- `synchronous_commit = off`: Eliminates disk flush wait per transaction for time-series readings.
- `wal_buffers = 16MB`, `shared_buffers = 256MB+`.
- Connection pooling via asyncpg + PgBouncer for transaction connection reuse.

---

## 10. Production Roadmap & Architectural Enhancements

### 10.1 Apache Kafka / Redpanda Integration
For scaling past 50,000 to 500,000 readings/second:
- Route telemetry directly to Kafka topic `sensor.readings.raw`.
- Decouples HTTP ingress from disk write throughput.
- Consumer worker groups read partitioned streams and perform parallel database bulk inserts and window processing.

### 10.2 RabbitMQ Integration
For decoupled alert notifications:
- Published alerts sent to RabbitMQ exchange `alerts.topic`.
- Dedicated workers handle webhook delivery, SMS gateways, and email alerts without degrading core API performance.

### 10.3 TimescaleDB Migration
Converting `sensor_readings` to a TimescaleDB hypertable:
- 1-day time partitioning.
- Native columnar compression (90%+ storage savings).
- Continuous aggregates for 1-minute, 5-minute, and 1-hour pre-computed telemetry views.
