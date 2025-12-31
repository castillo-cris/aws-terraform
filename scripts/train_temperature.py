# scripts/train_temperature.py
import csv
import json
import math
from collections import defaultdict
from datetime import datetime

# Espera columnas: Ciudad,Temperatura,Humedad,Presión,Viento,Descripción,FechaHora
INPUT_CSV = "data/weather.csv"
OUTPUT_JSON = "lambda/model_temp.json"

def parse_row(row):
    city = row["Ciudad"].strip()
    try:
        temp = float(row["Temperatura"])
        hum = float(row["Humedad"])
        pres = float(row["Presión"])
        wind = float(row["Viento"])
    except ValueError:
        return None
    # FechaHora en formato dd/MM/yyyy HH:mm:ss
    try:
        ts = datetime.strptime(row["FechaHora"], "%d/%m/%Y %H:%M:%S")
    except Exception:
        ts = None
    return {
        "city": city, "temp": temp, "hum": hum, "pres": pres, "wind": wind, "ts": ts
    }

def train_city_linear(points):
    # X = [temp_t, hum_t, pres_t, wind_t, 1], y = temp_{t+1}
    # Ajuste por mínimos cuadrados cerrados sin librerías: (X^T X)^-1 X^T y (5x5)
    X = []
    y = []
    for i in range(len(points) - 1):
        x_i = [
            points[i]["temp"],
            points[i]["hum"],
            points[i]["pres"],
            points[i]["wind"],
            1.0
        ]
        X.append(x_i)
        y.append(points[i + 1]["temp"])
    if len(X) < 10:
        # muy pocos datos: fallback
        avg = sum(p["temp"] for p in points) / max(len(points), 1)
        return {"weights": [0,0,0,0], "bias": avg, "method": "avg_fallback"}

    # Compute XtX (5x5) y XtY (5)
    XtX = [[0.0]*5 for _ in range(5)]
    XtY = [0.0]*5
    for i in range(len(X)):
        xi = X[i]
        yi = y[i]
        for r in range(5):
            XtY[r] += xi[r] * yi
            for c in range(5):
                XtX[r][c] += xi[r] * xi[c]

    # Inversa de 5x5 por Gauss-Jordan (simple y sin dependencias)
    def invert_5x5(A):
        n = 5
        M = [row[:] for row in A]
        I = [[float(r==c) for c in range(n)] for r in range(n)]
        for col in range(n):
            # pivot
            pivot = col
            for r in range(col, n):
                if abs(M[r][col]) > abs(M[pivot][col]):
                    pivot = r
            if abs(M[pivot][col]) < 1e-12:
                return None
            # swap
            M[col], M[pivot] = M[pivot], M[col]
            I[col], I[pivot] = I[pivot], I[col]
            # normalize
            pv = M[col][col]
            for c in range(n):
                M[col][c] /= pv
                I[col][c] /= pv
            # eliminate
            for r in range(n):
                if r == col: continue
                f = M[r][col]
                for c in range(n):
                    M[r][c] -= f * M[col][c]
                    I[r][c] -= f * I[col][c]
        return I

    inv = invert_5x5(XtX)
    if inv is None:
        avg = sum(p["temp"] for p in points) / max(len(points), 1)
        return {"weights": [0,0,0,0], "bias": avg, "method": "avg_fallback"}

    # beta = inv(XtX) * XtY -> tamaño 5
    beta = [sum(inv[r][c] * XtY[c] for c in range(5)) for r in range(5)]
    w = beta[:4]
    b = beta[4]
    return {"weights": w, "bias": b, "method": "linear"}

def main():
    by_city = defaultdict(list)
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pr = parse_row(row)
            if pr:
                by_city[pr["city"]].append(pr)
    # ordenar por timestamp
    for city in by_city:
        by_city[city].sort(key=lambda p: (p["ts"] is None, p["ts"]))

    models = {}
    for city, pts in by_city.items():
        mdl = train_city_linear(pts)
        models[city] = mdl

    out = {
        "task": "temperature_next",
        "features": ["temp_t", "hum_t", "pres_t", "wind_t"],
        "per_city": models,
        "default": {"weights": [0,0,0,0], "bias": 20.0, "method": "default"}
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Saved {OUTPUT_JSON} with {len(models)} city models")

if __name__ == "__main__":
    main()