# JUCCA - Jumia Content Compliance Assistant

JUCCA is a production-ready conversational compliance system that allows sellers to ask natural language questions about product compliance. The system interprets questions, checks policy rules derived from Excel sheets, applies deterministic compliance logic, and uses GPT4All for conversational explanations with cloud fallback capabilities.

## Features

- **Conversational Interface**: Ask compliance questions in natural language
- **Deterministic Policy Engine**: Checks against blacklisted words, restricted brands, and prohibited products
- **Local LLM (GPT4All)**: Offline-capable inference with privacy guarantees
- **Cloud Fallback**: Automatic failover to OpenAI API when overloaded
- **Response Caching**: LRU cache with TTL for improved performance
- **Streaming Responses**: Real-time response generation
- **Multi-language Support**: Works with English, French, and Arabic
- **Entity Detection**: Automatically identifies brands, products, and countries
- **Multi-turn Conversations**: Remembers context across conversation
- **Admin Dashboard**: Upload and manage policy Excel files
- **Role-based Access**: Seller, Admin, and Legal roles
- **Load Management**: Automatic load shedding and health monitoring

## Architecture

```
Frontend (Netlify/Vercel)
  └── React (Chat UI + Admin Dashboard)
        ↓ HTTPS
Backend (VPS / Render / EC2)
  └── FastAPI
        ├── Policy Decision Engine (Deterministic)
        ├── SQLite Policy Database
        ├── GPT4All Model (Local Inference)
        │     └── mistral-7b-openorca.gguf (primary)
        │     └── nous-hermes-llama2.gguf (fallback)
        │     └── orca-mini-3b.gguf (low RAM)
        └── Cloud Fallback (OpenAI API)
```

LLM **never enforces rules** — it only explains results. All compliance decisions are made by the deterministic policy engine.

## Quick Start

### Prerequisites

- Python 3.10 or higher
- 8GB RAM (16GB recommended for GPT4All)
- 10GB disk space (for models)
- Docker and Docker Compose (optional)

### 1. Clone and Setup

```bash
# Navigate to project directory
cd jucca-app

# Set up backend
cd jucca-backend

# Run setup script (installs dependencies and initializes database)
./scripts/setup.sh
```

### 2. Download GPT4All Model

```bash
# Download default model (Mistral 7B - 4GB)
python scripts/download_model.py

# Or download a specific model
python scripts/download_model.py --model nous-hermes-llama2.gguf

# List available models
python scripts/download_model.py --list
```

### 3. Configure Environment

```bash
# Edit environment configuration
cp .env.example .env
nano .env
```

Key environment variables:

```env
# LLM Configuration
GPT4ALL_MODEL=mistral-7b-openorca.gguf
GPT4ALL_MODEL_PATH=./models

# Cloud Fallback (optional)
OPENAI_API_KEY=your-openai-api-key
USE_CLOUD_FALLBACK=true

# Performance
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL=60
MAX_CONCURRENT_REQUESTS=5
```

### 4. Start Development Server

```bash
cd jucca-backend
uvicorn app.main:app --reload --port 8000
```

### 5. Access the Application

- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Docker Deployment

### Using Docker Compose

```bash
# Build and start all services
./scripts/deploy.sh deploy-local

# Start services
./scripts/deploy.sh start

# Stop services
./scripts/deploy.sh stop

# View logs
./scripts/deploy.sh logs

# Full deployment with monitoring
docker-compose up -d
```

### Docker Services

The docker-compose.yml includes:

| Service | Port | Description |
|---------|------|-------------|
| jucca-backend | 8000 | Main API server |
| prometheus | 9090 | Metrics collection |
| grafana | 3000 | Dashboard visualization |
| redis | 6379 | Caching (optional) |
| locust-master | 8089 | Load testing master |
| locust-worker | 5557 | Load testing workers |

### Access Docker Services

- **API**: http://localhost:8000
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Locust UI**: http://localhost:8089

## Default Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| Seller | seller | seller123 |

## Example Questions

Try asking these questions:

```
• Can I sell Nike shoes in Nigeria?
• What about used electronics?
• Can I list fake products?
• Is Apple iPhone allowed?
• Can I sell alcohol?
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /token | Login and get JWT token |
| POST | /register | Create new user |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /ask | Ask compliance question |
| POST | /ask/stream | Streaming compliance response |
| GET | /status | Service status |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /admin/upload-policy | Upload policy Excel |
| GET | /admin/policy-stats | Get policy statistics |
| DELETE | /admin/cache | Clear LLM cache |

### Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Basic health check |
| GET | /health/detailed | Detailed health with components |
| GET | /metrics | Prometheus metrics |

## GPT4All Models

### Available Models

| Model | Size | RAM | Description |
|-------|------|-----|-------------|
| mistral-7b-openorca.gguf | 4GB | 8GB+ | Best balance of speed and quality |
| nous-hermes-llama2.gguf | 4GB | 8GB+ | Strong reasoning capabilities |
| orca-mini-3b.gguf | 2GB | 4GB+ | Lower RAM requirements |
| llama-2-7b-chat.gguf | 4GB | 8GB+ | Good for conversations |

### Model Fallback Hierarchy

1. **mistral-7b-openorca.gguf** (Primary)
2. **nous-hermes-llama2.gguf** (Fallback 1)
3. **orca-mini-3b.gguf** (Fallback 2 - Low RAM)
4. **OpenAI API** (Cloud Fallback)

## Performance Features

### Response Caching

- LRU cache with configurable TTL (default: 60 minutes)
- Cache hit rate monitoring via /metrics
- Clear cache via /admin/cache endpoint

### Load Management

- Max concurrent requests: 5 (configurable)
- Automatic load shedding when overloaded
- Cloud fallback when local model is at capacity
- Request queuing and timeout handling

### Streaming Responses

```python
# Example streaming response
import requests

response = requests.post(
    "http://localhost:8000/ask/stream",
    json={"question": "Can I sell Nike shoes?"},
    stream=True
)

for line in response.iter_lines():
    if line:
        data = json.loads(line)
        if data["type"] == "content":
            print(data["chunk"], end="", flush=True)
```

## Monitoring and Observability

### Prometheus Metrics

Access metrics at `/metrics`:

- `jucca_requests_total` - Total requests count
- `jucca_request_duration_seconds` - Request latency histogram
- `jucca_cache_size` - Current cache size
- `jucca_load_active_requests` - Active request count
- `jucca_model_loaded` - Model load status

### Grafana Dashboards

Pre-built dashboard includes:

- Request rate and latency percentiles
- Compliance decision distribution
- Cache hit/miss rates
- System load and capacity
- Brand detection statistics

## Load Testing

### Run Load Test

```bash
# Normal load test (50 users, 60 seconds)
./scripts/deploy.sh load-test 50 5 60

# Stress test (100 users, 120 seconds)
./scripts/deploy.sh load-test 100 10 120

# Spike test (200 users sudden spike)
./scripts/deploy.sh load-test 200 50 30
```

### Locust Configuration

Load testing scenarios defined in `load_testing/locustfile.py`:

| User Class | Description | Spawn Weight |
|------------|-------------|--------------|
| JUCCAUser | Typical user behavior | 10 |
| JUCCAStressUser | High concurrency | 5 |
| JUCCASpikeUser | Burst traffic | 2 |

## Policy File Format

The system expects an Excel file with the following sheets:

### Blacklisted Words

| Column | Description |
|--------|-------------|
| Keyword | The prohibited word |
| Severity | high, medium, low |
| Scope | global, regional |
| Description | Additional notes |

### Restricted Brands

| Column | Description |
|--------|-------------|
| Brand | Brand name |
| Category | Product category |
| Country | Country code (optional) |
| Status | restricted, prohibited |
| Condition | Authorization requirements |

### Prohibited Categories

| Column | Description |
|--------|-------------|
| Keyword | Product keyword |
| Category | Product category |
| Country | Country code (optional) |
| Status | prohibited, restricted |
| Notes | Additional information |

## Environment Variables

### Backend Configuration

```env
# Database
DATABASE_URL=sqlite:///./jucca.db

# LLM Configuration
GPT4ALL_MODEL=mistral-7b-openorca.gguf
GPT4ALL_MODEL_PATH=./models

# Cloud Fallback
OPENAI_API_KEY=
USE_CLOUD_FALLBACK=true
CLOUD_MODEL=gpt-3.5-turbo

# Performance
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL=60
STREAMING_ENABLED=true
MAX_CONCURRENT_REQUESTS=5
REQUEST_TIMEOUT_SECONDS=60

# Model Settings
MAX_TOKENS=300
TEMPERATURE=0.7
TOP_P=0.9

# Security
SECRET_KEY=your-secret-key-change-in-production
```

## Troubleshooting

### Model Download Fails

```bash
# Check disk space
df -BG .

# Try manual download
wget -O models/mistral-7b-openorca.gguf \
    "https://gpt4all.io/models/gguf/mistral-7b-openorca.gguf"
```

### Out of Memory

- Use smaller model: `orca-mini-3b.gguf`
- Reduce `MAX_CONCURRENT_REQUESTS`
- Enable swap space

### High Latency

- Enable response caching: `LLM_CACHE_ENABLED=true`
- Use smaller model for testing
- Check system resources: `htop`, `nvtop`

## Deployment

### Render Deployment

JUCCA can be deployed to Render using a Web Service. Follow these steps:

#### 1. Create a New Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" and select "Web Service"
3. Connect your GitHub repository
4. Configure the service:

| Setting | Value |
|---------|-------|
| Name | jucca-backend |
| Root Directory | jucca-backend |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

#### 2. Environment Variables

Add the following environment variables in the Render dashboard:

| Variable | Value | Description |
|----------|-------|-------------|
| `PYTHONPATH` | `/opt/render/project/src/jucca-backend` | **Critical** - Must point to jucca-backend directory |
| `GPT4ALL_MODEL_PATH` | `./models` | Path to store downloaded models |
| `GPT4ALL_MODEL` | `mistral-7b-openorca.gguf` | Default model (optional) |
| `USE_CLOUD_FALLBACK` | `true` | Enable OpenAI fallback (optional) |
| `OPENAI_API_KEY` | Your OpenAI API key | For cloud fallback |
| `SECRET_KEY` | `your-secure-random-key` | For JWT authentication |

**⚠️ Important**: The `PYTHONPATH` environment variable is critical. It must include the `jucca-backend` directory so Python can find the `app` module.

#### 3. Start Command with Correct PYTHONPATH

The start command on Render should be:

```bash
PYTHONPATH=/opt/render/project/src/jucca-backend:$PYTHONPATH uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Or set PYTHONPATH as an environment variable in Render dashboard:
- Key: `PYTHONPATH`
- Value: `/opt/render/project/src/jucca-backend`

#### 4. Alternative: Flatten Directory Structure

If you prefer to not use PYTHONPATH, restructure your repository:

```
repository-root/
├── app/                    (move contents from jucca-backend/app here)
├── requirements.txt        (copy from jucca-backend/)
├── Dockerfile              (copy from jucca-backend/)
└── scripts/                (copy from jucca-backend/scripts/)
```

Then configure Render with:
- Root Directory: (leave empty - repository root)
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Production Deployment

```bash
# Backup database
./scripts/deploy.sh backup

# Deploy to production
./scripts/deploy.sh deploy-prod
```

### Environment Considerations

- **Minimum**: 8GB RAM, 20GB storage
- **Recommended**: 16GB RAM, 50GB storage
- **GPU**: Optional, improves inference speed

### Docker Deployment

#### Using Docker Compose

```bash
# Build and start all services
./scripts/deploy.sh deploy-local

# Start services
./scripts/deploy.sh start

# Stop services
./scripts/deploy.sh stop

# View logs
./scripts/deploy.sh logs

# Full deployment with monitoring
docker-compose up -d
```

## License

MIT License
