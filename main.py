import json
import os

from hidro_fetch import fetch_hidro
from prefectura_fetch import fetch_prefectura


def save_data(data):
    os.makedirs("cache", exist_ok=True)

    with open("cache/prefectura_latest.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    print("=== HydroGuard Update ===")

    # 1️⃣ SHN como fuente principal
    print("Intentando SHN (hidro)...")
    data = fetch_hidro()

    if data:
        print(f"OK SHN: {data}")
    else:
        # 2️⃣ Prefectura como fallback
        print("SHN falló → intentando Prefectura...")
        data = fetch_prefectura()

        if data:
            print(f"OK Prefectura: {data}")

    # 3️⃣ Validación final
    if not data:
        print("ERROR: ninguna fuente disponible")
        return

    # 4️⃣ Guardado
    save_data(data)
    print("✔ JSON actualizado correctamente")


if __name__ == "__main__":
    main()
