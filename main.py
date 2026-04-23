from prefectura_fetch import fetch_prefectura
from hidro_fetch import fetch_hidro

def main():
    print("Intentando Prefectura...")
    data = fetch_prefectura()

    if data:
        import json
import os

def save_data(data):
    os.makedirs("cache", exist_ok=True)
    with open("cache/prefectura_latest.json", "w") as f:
        json.dump(data, f, indent=2)

def main():
    print("Intentando Prefectura...")
    data = fetch_prefectura()

    if data:
        save_data(data)
        print(f"OK Prefectura: {data}")
        return

    print("Prefectura falló. Intentando Hidro...")
    data = fetch_hidro()

    if data:
        save_data(data)
        print(f"OK Hidro: {data}")
        return

    print("ERROR: ninguna fuente disponible")
    return

if __name__ == "__main__":
    main()