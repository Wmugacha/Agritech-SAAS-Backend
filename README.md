# Agritech SaaS Backend API

An enterprise-grade, multi-tenant SaaS backend architecture designed for agricultural cooperatives, agribusinesses, and agronomists to manage farm operations, track crop lifecycle timelines, record agronomic interventions, and execute high-performance predictive soil spectroscopy analytics. Built with Python, Django, Django REST Framework, Celery, and Redis, containerized with Docker, and engineered for high availability and enterprise scale.

[**Live Deployment Link**](http://51.20.119.5:8001/api/docs/) | [**API Documentation (Swagger UI)**](http://51.20.119.5:8001/api/docs/)

---

## Key Features

### 1. Multi-Tenancy Architecture & RBAC

- **Strict Tenant Isolation:** Middleware-enforced tenant isolation (`OrganizationMiddleware`) guarantees that queries, soil analyses, farms, and records are scoped strictly to the authenticated user's active organization.
- **Tenant Provisioning Workflow:** Seamless self-service registration (`POST /api/accounts/register/`) and organization instantiation (`POST /api/organizations/create/`) automatically grants workspace `OWNER` privileges and provisions a default `FREE` subscription tier.
- **Role-Based Access Control (RBAC):** Granular permission enforcement distinguishing workspace `OWNER`, `ORG_ADMIN`, `AGRONOMIST`, and `VIEWER` roles across agronomy and prediction endpoints.

### 2. Machine Learning Soil Spectroscopy & Resampling Pipeline

At the core of the platform is an asynchronous machine learning inference engine that predicts **Soil Organic Matter (SOM)** percentages directly from raw diffuse reflectance infrared Fourier transform spectroscopy (DRIFTS / FTIR) readings.

- **1D Linear Interpolation & Spectral Resampling:** In real-world spectrometer workflows, laboratory instruments output varying wavelength resolutions (from 1,500 to 80,000+ data points). An automated preprocessing engine (`scipy.interpolate.interp1d`) dynamically cleans target columns and resamples arbitrary input spectra to the exact standard 2,380 features ($3999.053 - 600.0723\text{ cm}^{-1}$) required by the production model.
- **Single & Multi-Row Batch Processing:** Supports single-sample JSON payloads as well as multi-row batch CSV uploads (hundreds of soil samples analyzed in parallel in a single Celery task).
- **Asynchronous Execution:** Prediction requests offload feature matrices to **Redis**. Celery background workers run Partial Least Squares Regression (PLSR) inference, persisting outputs (`SOM` percentage, sample counts, model version) directly to the tenant's database schema.
- **High-Performance Query Optimization:** Incorporates global DRF pagination (`PageNumberPagination`) and ORM column deferral (`.defer('spectra')`) to ensure listing hundreds of historical soil jobs completes in under 100ms without memory bloat.

### 3. Farm, Field & Crop Lifecycle Engine

- **Agronomy Hierarchy:** Models organizations $\rightarrow$ farms $\rightarrow$ field blocks with geospatial coordinates (latitude/longitude) and acreage specifications.
- **Crop Season Timelines:** Tracks multi-season planting schedules, planned harvest windows, and target harvest yields (e.g., Maize and Bean companion farming systems).
- **Intervention & Activity Logs:** Event-driven logging for agricultural treatments including fertilizer applications (e.g., Urea nitrogen tracking), soil sampling, weeding, and harvesting costs.

### 4. B2B Subscriptions & Stripe Billing Integration

- **Plan Enforcement:** Feature-gated quotas managed at the organization level (`FREE` tier limited to 10 prediction jobs; `PRO` tier with expanded limits).
- **Checkout Sessions & Webhooks:** Integrated Stripe Checkout workflows with automated signature verification handling `checkout.session.completed`, `customer.subscription.updated`, and `customer.subscription.deleted`.
- **Local Webhook Testing:** Embedded `stripe-cli` container orchestrates secure, zero-tunnel local event testing.

### 5. High-Scale Benchmark Seeding Engine

- **Bulk Database Seeder:** High-performance custom Django management command (`populate_db`) supporting `--users` (default: 2,000) and `--batch-size` (default: 1,000).
- Uses optimized `bulk_create` operations across Users, Organizations, Subscriptions, Memberships, Farms, Fields, Seasons, and Prediction Jobs to seed hundreds of thousands of relational records in seconds for load benchmarking.

---

## System Architecture & Tech Stack

```text
                           [ Client / Frontend ]
                                     │ (HTTPS / Bearer JWT)
                                     ▼
                             [ AWS EC2 Linux ]
                                     │
                             [ Docker Compose ]
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
  [ Web (Gunicorn) ]        [ Celery Worker ]             [ Redis 7 ]
  Django 4.2 / DRF          Model Inference Task         Broker & Cache
  Spectral Preprocessing     PLSR SOM Prediction
        │                            │
        └────────────────────────────┘
                      │
                      ▼
        [ External Managed PostgreSQL ]
            Supabase Cloud Database
```

- **Backend Framework:** Python 3.8 / 3.11, Django 4.2.27, Django REST Framework (DRF), SimpleJWT
- **Scientific Computing & ML:** NumPy, Pandas, SciPy (`scipy.interpolate.interp1d`), Scikit-Learn (`PLSRegression`), Joblib
- **Task Queue & Caching:** Celery 5.x, Redis 7 (Standalone)
- **Database & ORM:** PostgreSQL (Supabase via `dj-database-url`), Django ORM
- **Billing & Monetization:** Stripe Python SDK, Stripe CLI
- **API Documentation:** drf-spectacular (OpenAPI 3.0 / Swagger UI)
- **Containerization & Cloud:** Docker, Docker Compose, AWS EC2, Gunicorn, WhiteNoise

---

## API Endpoints Overview

| Area                 | Method        | Endpoint                            | Description                                                    |
| :------------------- | :------------ | :---------------------------------- | :------------------------------------------------------------- |
| **Auth & Accounts**  | `POST`        | `/api/accounts/register/`           | Register new user; returns profile and JWT tokens              |
|                      | `POST`        | `/api/auth/login/`                  | Obtain JWT access and refresh tokens                           |
|                      | `POST`        | `/api/auth/refresh/`                | Refresh JWT access token                                       |
|                      | `GET`         | `/api/accounts/me/`                 | Inspect authenticated user profile                             |
| **Organizations**    | `POST`        | `/api/organizations/create/`        | Provision new tenant workspace (grants `OWNER` + `FREE` plan)  |
|                      | `GET`         | `/api/organizations/my_role/`       | Check active tenant membership role                            |
| **Agronomy & Farms** | `GET`, `POST` | `/api/agronomy/farms/`              | List and register agricultural farms                           |
|                      | `GET`, `POST` | `/api/agronomy/fields/`             | Manage geospatial field plots and crop designations            |
|                      | `GET`, `POST` | `/api/agronomy/seasons/`            | Track crop planting, timelines, and target yield               |
|                      | `GET`, `POST` | `/api/agronomy/activities/`         | Log agronomic interventions and input costs                    |
| **Soil Sampling**    | `GET`, `POST` | `/api/samples/`                     | Record field NPK, pH, and soil sample coordinates              |
| **Predictive ML**    | `POST`        | `/api/predict/`                     | Upload CSV or JSON spectra; triggers async PLSR inference      |
|                      | `GET`         | `/api/predict/`                     | Paginated history of organization prediction jobs              |
|                      | `GET`         | `/api/predict/{id}/`                | Fetch status and predicted `SOM` values for a specific job     |
|                      | `GET`         | `/api/predict/analytics/dashboard/` | Aggregated soil health metrics, average SOM, and status totals |
| **Subscriptions**    | `POST`        | `/api/subscriptions/checkout/`      | Generate Stripe checkout session for PRO upgrade               |
|                      | `GET`         | `/api/subscriptions/current/`       | View current tier status and remaining prediction quota        |
|                      | `POST`        | `/api/subscriptions/webhook/`       | Handle automated Stripe subscription lifecycle events          |

---

## Getting Started (Local Development)

### Prerequisites

- Docker and Docker Compose installed on your host machine.
- External or local PostgreSQL database (e.g. Supabase).
- Stripe account (for billing webhooks).

### 1. Clone the Repository

```bash
git clone https://github.com/Wmugacha/Agritech-SAAS-Backend.git
cd Agritech-SAAS-Backend
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory and populate it with your configuration:

```env
# Django Configuration
DJANGO_SECRET_KEY=your_django_secret_key
DJANGO_DEBUG=1
ALLOWED_HOSTS=*

# Database Connection (Supabase or PostgreSQL)
DATABASE_URL=postgresql://postgres:your_password@your_db_host:5432/postgres

# Redis & Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Stripe Payments
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...

# Frontend Integration
FRONTEND_URL=http://localhost:3000
```

### 3. Docker Compose Orchestration

Ensure your external Docker network exists (if configured):

```bash
docker network create portfolio-network
```

Build and launch the full containerized stack:

```bash
docker-compose up --build
```

The services will initialize:

- **Django Web Application (Gunicorn):** `http://localhost:8000` (or host port `8001`)
- **Celery Inference Worker:** Consumes from Redis queue `celery`
- **Redis Server:** Running on port `6379`
- **Stripe CLI:** Forwarding events to `/api/subscriptions/webhook/`

### 4. Migrations & Seeding Benchmark Data

Run database migrations:

```bash
docker-compose exec web python backend/core_saas/manage.py migrate
```

Create an administrative superuser:

```bash
docker-compose exec web python backend/core_saas/manage.py createsuperuser
```

_(Optional)_ Seed high-volume synthetic benchmark data:

```bash
# Seed 500 users with complete multi-tenant records
docker-compose exec web python backend/core_saas/manage.py populate_db --users 500 --batch-size 250
```

Interactive OpenAPI / Swagger documentation is accessible at:

```text
http://localhost:8000/api/docs/
```

---

## Machine Learning Pipeline & Validation

### Model Training & Evaluation

The repository includes dedicated model training and validation utilities:

- **`train_model.py`**: Loads mid-infrared soil absorbance data, partitions training and test sets, fits a 10-component Partial Least Squares Regression (`PLSRegression`), and exports the serialized model artifact (`soil_model.pkl`).
- **`test_model.py`**: Compares live API batch prediction outputs against ground-truth analytical laboratory SOM values, computes $R^2$ and RMSE metrics, and outputs regression scatter plots (`accuracy_chart.png`).

---

## Webhook Integration & Testing

This infrastructure tests production-grade webhook callbacks securely within local boundaries without resorting to manual external networking tunnels.

The background `stripe-cli` container communicates directly with your testing dashboard, continuously transmitting webhook payloads over internal virtual networks into your handling controller:

```bash
# Manually trigger a mock successful subscription event for verification
docker-compose exec stripe-cli stripe trigger checkout.session.completed
```

---

## CI/CD Keep-Alive Workflows

To optimize free-tier computing allowances across external storage platforms, a scheduled automated continuous integration job runs via GitHub Actions every Sunday and Thursday at midnight UTC. This worker executes lightweight queries to maintain system activity:

```yaml
# Located at .github/workflows/keep_alive.yml
on:
  schedule:
    - cron: "0 0 * * 0,4"
```

This action issues secure, authenticated database pings against core data indices, keeping the managed resources ready for interaction without manual overhead.

---

## 👥 Contributors & Contact

- **Wilfred Mugacha** - Software Engineer & Backend Developer
- Project Repository: [https://github.com/Wmugacha/Agritech-SAAS-Backend](https://github.com/Wmugacha/Agritech-SAAS-Backend)

```

```
