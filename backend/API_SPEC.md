# SplitScan API Specification (v1)

This document defines the contract between the SplitScan Frontend (React Native) and the Backend (FastAPI/Python).

## Base URL
`https://api.gastosmart.com/v1` (or as configured in `EXPO_PUBLIC_API_URL`)

## Authentication
All endpoints (except `/auth/login`) expect a Bearer Token in the `Authorization` header.

---

### 1. Authentication
**POST** `/auth/login`
- **Request Body**: `{ "email": "string" }`
- **Response (200)**: `{ "id": "uuid", "name": "string", "email": "string", "token": "jwt_token" }`

---

### 2. Dashboard Summary
**GET** `/summary`
- **Response (200)**: 
```json
{
  "toReceive": 45.50,
  "toPay": 12.20,
  "recentExpenses": [
    {
      "id": "uuid",
      "title": "Cena Italiana",
      "totalAmount": 90.0,
      "personalAmount": 30.0,
      "date": "2024-03-03T14:00:00Z",
      "category": "Alimentación"
    }
  ]
}
```

---

### 3. Groups
**GET** `/groups`
- **Response (200)**: `Array<GroupObject>`

**POST** `/groups`
- **Request Body**: `{ "name": "string" }`
- **Response (201)**: `{ "id": "uuid", "name": "string", "code": "ABC12" }`

---

### 4. Expenses (OCR Data Sink)
**POST** `/expenses`
- **Description**: Receives structured data already processed by the local OCR.
- **Request Body**:
```json
{
  "title": "string",
  "totalAmount": 23.50,
  "category": "Alimentación",
  "groupId": "uuid",
  "paidBy": "uuid",
  "items": [
    {
      "description": "Pizza",
      "amount": 12.50,
      "category": "Alimentación"
    }
  ]
}
```
- **Response (201)**: `{ "id": "uuid", "status": "success" }`

---

### 5. Receipt Inference
**POST** `/receipt-inference`
- **Description**: Uploads a receipt image to the backend Donut model and returns structured line items.
- **Content-Type**: `multipart/form-data`
- **Form fields**:
  - `file`: receipt image
- **Response (200)**:
```json
{
  "engine": "donut",
  "device": "cuda",
  "model_source": "backend/models/donut_receipt_model",
  "items": [
    { "product": "Milk", "price": "1.20", "amount": 1.2 },
    { "product": "Bread", "price": "0.95", "amount": 0.95 }
  ],
  "total": 2.15
}
```

**GET** `/receipt-inference/status`
- **Response (200)**:
```json
{
  "configured_model_root": "backend/models/donut_receipt_model",
  "resolved_model_source": "backend/models/donut_receipt_model/checkpoint-399",
  "ready": false,
  "device": "auto",
  "using_checkpoint_fallback": true
}
```

---

### 6. Balances
**GET** `/groups/{id}/balances`
- **Response (200)**: 
```json
[
  { "from": "User A", "to": "User B", "amount": 15.00 }
]
```
