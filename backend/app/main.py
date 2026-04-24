import json
import os

from prefectura_fetch import fetch_prefectura
from hidro_fetch import fetch_hidro


def save_data(data):
    os.makedirs("cache", exist_ok=True)

    with open("cache/prefectura_latest.json", "w") as f:
        json.dump(data, f, indent=2)


def main():
    print("Intentando Prefectura...")
    data = fetch_prefectura()

    if not data:
        print("Prefectura falló. Intentando Hidro...")
        data = fetch_hidro()

    if not data:
        print("ERROR: ninguna fuente disponible")
        return

    save_data(data)
    print(f"OK final: {data}")


if __name__ == "__main__":
    main()
