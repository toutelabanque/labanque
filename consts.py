from json import load

with open('config.json') as f:
    config = load(f)

SALES_TAX_PERCENT = config["salesTaxPercent"]

BASE_RATES = config["baseRates"]
