# Product Learning API

A FastAPI product CRUD API backed by PostgreSQL and SQLAlchemy.

![FastAPI product API architecture](app/fastapi-product-api-architecture.png)

## Project structure

```text
app/
  main.py                    # FastAPI app and router registration
  controllers/               # HTTP endpoints
  dependencies/              # Shared FastAPI dependencies
  models/                    # SQLAlchemy models
  repositories/              # Database access
  schemas/                   # Request/response validation
  security_pack/auth.py      # Credential checks and JWT handling
  services/                  # Product business logic
  config_db/                 # Settings and database session
```

## Dependencies

Install the backend and Streamlit frontend dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
```

Configure `app/.env` with the database URL and required token settings:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/DB_NAME
ACCESS_TOKEN_SECRET_KEY=<long-random-secret>
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Keep the signing secret private. The PostgreSQL database must exist before starting the API.

## Run

```powershell
python -m uvicorn app.main:app --reload
```

Interactive API docs: [Swagger UI](http://127.0.0.1:8000/docs) · [ReDoc](http://127.0.0.1:8000/redoc)

## Authentication

`POST /api/v1/login/createtoken` accepts `username` and `password` as form fields and returns a JWT for a valid active user. Send the token with protected requests as `Authorization: Bearer <access_token>`. In Swagger UI, use **Authorize**.

Only `PUT` and `PATCH /api/v1/products/{product_id}` currently require a valid, unexpired token. Other product operations are unauthenticated.

## Endpoints

### `GET /`

Health status. No input.

Response (`200 OK`):

```json
{
  "message": "Status is OK!"
}
```

### `GET /ping`

Health check. No input.

Response (`200 OK`):

```json
{
  "message": "10 ms pong!"
}
```

### `POST /api/v1/login/createtoken`

Log in with `application/x-www-form-urlencoded` fields (not JSON):

```text
username=user01&password=your-password
```

Response (`201 Created`):

```json
{
  "access_token": "<signed-jwt>",
  "token_type": "bearer"
}
```

Invalid credentials return `401 Unauthorized`.

### Product response shape

Successful product create, read, update, and filter results use this shape:

```json
{
  "id": 1,
  "name": "Laptop",
  "description": "15-inch gaming laptop",
  "price": 1299.99,
  "stock_quantity": 12,
  "is_active": true,
  "created_at": "2026-10-01T12:00:00",
  "updated_at": "2026-10-01T12:00:00"
}
```

Product input rules: `name` is 3–20 characters; `description` is optional and up to 200 characters; `price` must be greater than 0 and less than 10000; `stock_quantity` must be 0–1000; `is_active` is a boolean (defaults to `true` on create).

### `POST /api/v1/products`

Create a product. No authentication required.

Request (`application/json`):

```json
{
  "name": "Laptop",
  "description": "15-inch gaming laptop",
  "price": 1299.99,
  "stock_quantity": 12,
  "is_active": true
}
```

Response: product response shape above (`201 Created`).

### `GET /api/v1/products`

List all products. No input or authentication required.

Response (`200 OK`):

```json
[
  {
    "id": 1,
    "name": "Laptop",
    "description": "15-inch gaming laptop",
    "price": 1299.99,
    "stock_quantity": 12,
    "is_active": true,
    "created_at": "2026-10-01T12:00:00",
    "updated_at": "2026-10-01T12:00:00"
  }
]
```

An empty product table returns `[]`.

### `GET /api/v1/products/{product_id}`

Get one product by its ID. Example input: `/api/v1/products/1`. No authentication required.

Response (`200 OK`): one product using the product response shape above.

### `PUT /api/v1/products/{product_id}`

Replace all product fields. Requires a bearer token. Send the complete product body:

```http
PUT /api/v1/products/1
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "name": "Gaming Laptop",
  "description": "Updated 15-inch gaming laptop",
  "price": 1499.99,
  "stock_quantity": 8,
  "is_active": true
}
```

Response (`200 OK`): the updated product using the product response shape above.

### `PATCH /api/v1/products/{product_id}`

Update selected product fields. Requires a bearer token. Include only fields to change:

```http
PATCH /api/v1/products/1
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "price": 1399.99,
  "stock_quantity": 10
}
```

Response (`200 OK`): the updated product using the product response shape above.

### `DELETE /api/v1/products/{product_id}`

Delete a product by ID. Example input: `/api/v1/products/1`. No authentication required.

Response: `204 No Content` with no response body.

### `GET /api/v1/products/filter`

Filter, sort, and paginate products. All parameters are optional; no authentication required.

Example input:

```http
GET /api/v1/products/filter?name_seq=lap&description_seq=gaming&min_price=500&max_price=2000&active_status=true&sort_by=price&page_size=10&page_no=1
```

| Query parameter | Purpose |
|---|---|
| `name_seq` | Partial name match (3–20 characters) |
| `description_seq` | Partial description match (3–200 characters) |
| `min_price` / `max_price` | Price range (1–9999) |
| `active_status` | Filter by active state (`true` or `false`) |
| `created_after` | Filter by creation timestamp |
| `sort_by` | `id`, `name`, `price`, `stock_quantity`, `created_at`, or `updated_at` |
| `page_size` | Results per page (5–20; default 8) |
| `page_no` | Page number (1–2000; default 1) |

Response (`200 OK`): an array of products using the product response shape above; no matches returns `[]`.

## Authentication implementation

- `app/controllers/user_controller.py`: `POST /api/v1/login/createtoken` reads OAuth2 username/password form fields and returns an access token after credential validation.
- `app/security_pack/auth.py`: checks the user is active and verifies the submitted password against its stored hash with `pwdlib`. It creates an HS256 JWT containing the user ID (`sub`) and expiration, then validates the signature and expiration on protected requests.
- `app/models/user_model.py`: defines the user record and its stored `hashed_password`.
- `app/config_db/settings.py` and `app/.env`: supply the signing secret and token lifetime.
- `app/controllers/product_controller.py`: injects `verify_token_and_get_current_user` into the PUT and PATCH handlers. That dependency reads the `Authorization: Bearer ...` header, loads the user, and rejects invalid, expired, missing, or inactive-user tokens.

The login route issues tokens; protected route dependencies validate them. The dependency does not call the login route.

## Run the Streamlit frontend

Start the FastAPI backend in one terminal from the repository root:

```powershell
python -m uvicorn app.main:app --reload
```

In a second terminal, also from the repository root, start the frontend:

```powershell
python -m streamlit run app/frontend_streamlit.py
```

Streamlit opens the frontend in your browser. It connects to `http://127.0.0.1:8000` by default; change the **FastAPI base URL** in the sidebar to use a different API address. The login token is kept for the current Streamlit session and is sent with the protected PUT and PATCH requests.

## Run with Docker (without Compose)

Build one image containing both applications:

```powershell
docker build -t product-api .
docker network create product-network
```

Run FastAPI and Streamlit as separate containers from that same image. From the repository root:

```powershell
	1. Start FastAPI container
      docker run -d --name api --network product-network -p 8000:8000 
      --env-file .\.env 
      -e "DATABASE_URL=postgresql+psycopg://postgres:8630@host.docker.internal:5432/learningFastAPIdb" 
      product-api

  2. Start Streamlit container
      docker run -d --name frontend --network product-network -p 8051:8051 -e FASTAPI_BASE_URL=http://api:8000 product-api python -m streamlit run app/frontend_streamlit.py --server.address=0.0.0.0 --server.port=8051
```

Open `http://localhost:8051` for Streamlit and `http://localhost:8000/docs` for FastAPI. The API container uses settings supplied by `app/.env`; that file is excluded from the image. PostgreSQL must be reachable from the API container. If PostgreSQL runs on the Docker host, use `host.docker.internal` instead of `localhost` in `DATABASE_URL`. The `product-network` network only needs to be created once; remove the containers with `docker stop api frontend` and `docker rm api frontend` when finished.
