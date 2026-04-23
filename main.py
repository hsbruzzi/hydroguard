from prefectura_fetch import fetch_prefectura
from hidro_fetch import fetch_hidro

def main():
    print("Intentando Prefectura...")
    data = fetch_prefectura()

    if data:
        print(f"OK Prefectura: {data}")
        return

    print("Prefectura falló. Intentando Hidro...")
    data = fetch_hidro()

    if data:
        print(f"OK Hidro: {data}")
        return

    print("ERROR: ninguna fuente disponible")
    # 👉 NO fallamos el job
    return

if __name__ == "__main__":
    main()