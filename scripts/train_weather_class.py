# scripts/train_weather_class.py
import csv
import json
from collections import defaultdict, Counter

INPUT_CSV = "data/weather.csv"
OUTPUT_JSON = "lambda/model_class.json"

def parse_row(row):
    try:
        temp = float(row["Temperatura"])
        hum = float(row["Humedad"])
        pres = float(row["Presión"])
        wind = float(row["Viento"])
    except ValueError:
        return None
    label = row["Descripción"].strip().lower()
    if not label:
        return None
    return {"x": [temp, hum, pres, wind], "y": label}

def mean(xs):
    return sum(xs)/max(len(xs),1)

def var(xs, mu):
    return sum((x-mu)**2 for x in xs)/max(len(xs),1)

def main():
    data = []
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pr = parse_row(row)
            if pr: data.append(pr)

    if len(data) < 200:
        # insuficiente para un clasificador útil
        out = {"enabled": False, "reason": "insufficient_data"}
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("Classification disabled: insufficient data")
        return

    # Agrupar por clase
    by_class = defaultdict(list)
    for d in data:
        by_class[d["y"]].append(d["x"])

    classes = list(by_class.keys())
    priors = {}
    means = {}
    vars_ = {}

    total = sum(len(v) for v in by_class.values())
    for c, xs in by_class.items():
        priors[c] = len(xs)/total
        mu = [mean([x[i] for x in xs]) for i in range(4)]
        means[c] = mu
        vars_[c] = [max(var([x[i] for x in xs], mu[i]), 1e-6) for i in range(4)]

    out = {
        "enabled": True,
        "model": {
            "classes": classes,
            "priors": priors,
            "means": means,
            "vars": vars_
        },
        "features": ["temp", "hum", "pres", "wind"]
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Saved classifier with {len(classes)} classes")

if __name__ == "__main__":
    main()