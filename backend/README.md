# HydroGuard Avellaneda - Web App

## Cómo correrlo en Windows
1. Abrí una consola en `backend`
2. Activá el entorno virtual:
   - CMD: `.venv\Scripts\activate.bat`
3. Instalá dependencias:
   - `pip install -r requirements.txt`
4. Levantá el backend:
   - `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## Qué abrir
- En la PC: `http://localhost:8000`
- En el iPhone (misma red Wi‑Fi): `http://IP_DE_TU_PC:8000`

## Cómo ver la IP de tu PC
En otra consola:
- `ipconfig`

Buscá la IPv4 de tu adaptador Wi‑Fi, por ejemplo `192.168.1.15`
Luego abrí en el iPhone:
- `http://192.168.1.15:8000`

## Instalar en pantalla de inicio del iPhone
1. Abrí la app en Safari
2. Compartir
3. Agregar a pantalla de inicio
