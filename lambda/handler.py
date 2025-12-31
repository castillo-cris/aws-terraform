# lambda/handler.py
import json
import math
import os
from pathlib import Path

BASE = Path(__file__).parent

def load_json(name):
    p = BASE / name
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

MODEL_TEMP = load_json("model_temp.json") or {}
MODEL_CLASS = load_json("model_class.json") or {"enabled": False}

def predict_temperature(city, temp, hum, pres, wind):
    # Busca modelo de la ciudad, si no, usa default
    per_city = MODEL_TEMP.get("per_city", {})
    mdl = per_city.get(city, MODEL_TEMP.get("default", {"weights":[0,0,0,0], "bias":20.0}))
    w = mdl.get("weights", [0,0,0,0])
    b = mdl.get("bias", 20.0)
    y = w[0]*temp + w[1]*hum + w[2]*pres + w[3]*wind + b
    return y

def gaussian_logprob(x, mu, var):
    # log N(x | mu, var)
    return -0.5*math.log(2*math.pi*var) - 0.5*((x-mu)**2/var)

def classify_weather(temp, hum, pres, wind):
    if not MODEL_CLASS.get("enabled", False):
        return {"enabled": False, "prediction": None, "probs": None}
    model = MODEL_CLASS["model"]
    classes = model["classes"]
    priors = model["priors"]
    means = model["means"]
    vars_ = model["vars"]

    scores = {}
    feats = [temp, hum, pres, wind]
    for c in classes:
        score = math.log(max(priors.get(c, 1e-6), 1e-6))
        mu = means[c]
        var = vars_[c]
        for i in range(4):
            score += gaussian_logprob(feats[i], mu[i], var[i])
        scores[c] = score
    # Normalize to probabilities (softmax on log-scores)
    maxs = max(scores.values())
    exps = {c: math.exp(scores[c] - maxs) for c in scores}
    Z = sum(exps.values())
    probs = {c: exps[c]/Z for c in exps}
    pred = max(probs, key=probs.get)
    return {"enabled": True, "prediction": pred, "probs": probs}

def response(status_code: int, body: dict):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False)
    }

def lambda_handler(event, context):
    try:
        body_raw = event.get("body", "")
        if isinstance(body_raw, str) and body_raw:
            data = json.loads(body_raw)
        elif isinstance(body_raw, dict):
            data = body_raw
        else:
            data = {}

        # Input esperado:
        # { "city": "Bogota", "features": { "temp": 17.14, "hum": 66, "pres": 1014, "wind": 2.24 } }
        city = str(data.get("city", "")).strip()
        feats = data.get("features", {})
        try:
            temp = float(feats.get("temp"))
            hum = float(feats.get("hum"))
            pres = float(feats.get("pres"))
            wind = float(feats.get("wind"))
        except (TypeError, ValueError):
            return response(400, {"error": "features debe incluir temp, hum, pres, wind numéricos"})

        temp_next = predict_temperature(city or "default", temp, hum, pres, wind)
        cls = classify_weather(temp, hum, pres, wind)

        out = {
            "ok": True,
            "result": {
                "prediction": {
                    "temperature_next": temp_next
                },
                "classification": cls if cls.get("enabled") else {"enabled": False}
            }
        }
        if os.environ.get("LOG_LEVEL", "INFO").upper() == "DEBUG":
            out["debug"] = {
                "city": city,
                "features": {"temp": temp, "hum": hum, "pres": pres, "wind": wind}
            }
        return response(200, out)
    except json.JSONDecodeError:
        return response(400, {"error": "Body no es JSON válido"})
    except Exception as e:
        return response(500, {"error": "Error interno", "detail": str(e)})