# Backend API

FastAPI service for persistence, group logic, balances, and Donut-based receipt inference.

## Requirements

- Python 3.10+

## Structure

- `app/`: modular application code
- `models/`: trained Donut artifacts and exported ONNX files
- `configs/`: workflow configuration
- `dataset/`, `training/`, `tools/`, `utils/`: ML data and utilities
- `data/`: runtime SQLite database and local metadata

## Startup

From the repository root:

1. Install dependencies:
   `python -m pip install -r backend/requirements.txt`
2. Run the server:
   `python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`

From inside `backend/`, the equivalent command is:

`python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000`

Backend startup loads environment variables from `backend/.env` first and then from the repository root `.env` if it exists.

## Environment Variables

- `DATABASE_PATH`: optional SQLite path
  - Default: `backend/data/gastosmart.db`
- `CORS_ORIGINS`: comma-separated allowed origins
- `DONUT_MODEL_DIR`: trained Donut model directory
  - Default: `backend/models/donut_receipt_model`
- `DONUT_CONFIG_PATH`: Donut YAML config path
  - Default: `backend/configs/donut_config.yaml`
- `DONUT_DEVICE`: `auto`, `cpu`, or `cuda`
- `DONUT_PRELOAD_MODEL`: preload Donut at backend startup when set to `true`
- `BACKEND_LOG_LEVEL`: logger level

## Main Endpoints

The backend exposes routes under `/api`:

- `POST /api/auth/login`
- `POST /api/auth/register`
- `GET /api/summary?userId=<id>`
- `GET /api/groups`
- `GET /api/groups/{id}`
- `POST /api/groups`
- `GET /api/groups/{id}/expenses`
- `GET /api/groups/{id}/balances`
- `POST /api/expenses`
- `GET /api/expenses`
- `POST /api/receipt-inference`
- `GET /api/receipt-inference/status`

## Receipt Inference

`POST /api/receipt-inference` expects `multipart/form-data` with a `file` field containing the receipt image.

Example response:

```json
{
  "engine": "donut",
  "device": "cuda",
  "model_source": "C:/.../backend/models/donut_receipt_model",
  "items": [
    { "product": "Milk", "price": "1.20", "amount": 1.2 },
    { "product": "Bread", "price": "0.95", "amount": 0.95 }
  ],
  "total": 2.15
}
```

If the model root does not contain a final exported model yet, the backend falls back to the newest valid `checkpoint-*` directory.

## Useful Endpoints

- `GET /health`
- `GET /docs`
- `GET /openapi.json`

## Related Docs

- `ARCHITECTURE.md`
- `API_SPEC.md`
