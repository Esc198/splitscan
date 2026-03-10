# SplitScan

Proyecto reorganizado en dos bloques claros:

- `frontend/`: app Expo/React Native
- `backend/`: API FastAPI, base de datos y tooling de modelos

## Estructura

```text
SplitScan/
|- frontend/
|  |- src/
|  |- android/
|  |- scripts/
|  |- package.json
|  `- .env
|- backend/
|  |- app/
|  |- configs/
|  |- models/
|  |- dataset/
|  |- training/
|  |- tools/
|  |- utils/
|  |- data/
|  |- API_SPEC.md
|  `- requirements.txt
`- README.md
```

## Frontend

1. Ve a `frontend/`.
2. Revisa `frontend/.env` o copia `frontend/.env.example`.
3. Ejecuta:
   `npm install`
4. Arranca la app:
   `npm run start`

También tienes:

- `npm run android`
- `npm run android:clean`
- `npm run ios`
- `npm run lint`

## Backend

1. Instala dependencias:
   `python -m pip install -r backend/requirements.txt`
2. Arranca la API:
   `python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`

Configuración útil:

- `frontend/.env.example`
- `backend/.env.example`
- `backend/README.md`
- `backend/API_SPEC.md`
