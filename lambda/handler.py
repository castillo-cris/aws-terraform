import json
import math
import os

# Modelo logístico simple: y = sigmoid(b0 + sum(bi * xi))
# Coeficientes cargados desde JSON para claridad y fácil actualización
# Sin numpy ni sklearn; pura aritmética Python
def load_model():
    import pathlib
    cfg_path = pathlib.Path(__file__).with_name("model_config.json")
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("bias", 0.0), cfg.get("weights", [])
    except Exception:
        # Fallback seguro: coeficientes mínimos
        return 0.0, []

BIAS, WEIGHTS = load_model()

def sigmoid(z: float) -> float:
    # Protección numérica simple
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    else:
        ez = math.exp(z)
        return ez / (1.0 + ez)

def infer(features):
    # features: lista de números (floats/ints)
    # Longitud flexible; pesos extra se ignoran y faltantes se tratan como 0
    total = BIAS
    for i, w in enumerate(WEIGHTS):
        x = 0.0
        if i < len(features):
            v = features[i]
            # Validación básica
            if isinstance(v, (int, float)):
                x = float(v)
            else:
                # Si el valor no es numérico, se considera 0
                x = 0.0
        total += w * x
    prob = sigmoid(total)
    # Umbral fijo 0.5 para clasificación binaria
    label = 1 if prob >= 0.5 else 0
    return {"probability": prob, "label": label}

def response(status_code: int, body_dict: dict):
    body_str = json.dumps(body_dict, ensure_ascii=False)
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": body_str
    }

def lambda_handler(event, context):
    # API Gateway HTTP API (payload v2.0): el body puede ser string
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    try:
        body_raw = event.get("body", "")
        if isinstance(body_raw, str) and body_raw:
            data = json.loads(body_raw)
        elif isinstance(body_raw, dict):
            data = body_raw
        else:
            data = {}

        features = data.get("features", [])
        if not isinstance(features, list):
            return response(400, {"error": "El campo 'features' debe ser una lista de números."})

        result = infer(features)

        if log_level.upper() == "DEBUG":
            result["debug"] = {
                "bias": BIAS,
                "weights": WEIGHTS,
                "features": features
            }

        return response(200, {"ok": True, "result": result})
    except json.JSONDecodeError:
        return response(400, {"error": "Body no es JSON válido."})
    except Exception as e:
        # Log minimal en body para CloudWatch facilidad
        return response(500, {"error": "Error interno", "detail": str(e)})