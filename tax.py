sales_tax_percent = 6.25


def get_income_tax_percent(income: float):
    if income < 25:
        return 2
    elif 25 <= income < 75:
        return 3
    else:
        return 5
