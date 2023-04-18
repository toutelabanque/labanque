from json import load

with open('config.json') as f:
    config = load(f)

SALES_TAX_PERCENT: float = config["salesTaxPercent"]

BASE_RATES: dict[str, float | dict[str, float]] = config["baseRates"]
