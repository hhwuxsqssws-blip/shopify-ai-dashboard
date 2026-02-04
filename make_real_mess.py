# make_real_mess.py
import pandas as pd
import numpy as np
import random
from faker import Faker
from datetime import datetime, timedelta
from collections import Counter

fake = Faker()

# Simulated product catalog (name -> unit price)
PRODUCTS = {
    "Yoga Mat": 29.99,
    "Stainless Water Bottle": 15.50,
    "Running Shoes (Pro)": 89.99,
    "Dumbbell Set 20kg": 45.00,
    "Whey Protein": 35.00,
}

DIRTINESS_CATALOG = {
    "missing_value_placeholder": "Missing values represented by blanks or placeholders like N/A, NULL, -.",
    "leading_trailing_whitespace": "Values padded with extra spaces or tabs.",
    "inconsistent_case": "Mixed upper/lower/title case in text fields.",
    "inconsistent_order_id_format": "Order IDs use multiple formats (#123, ORD-123, 00123, etc.).",
    "mixed_date_formats": "Dates appear in multiple formats with/without time.",
    "outlier_date": "Dates far in the past or future.",
    "invalid_date_token": "Dates replaced by words like today/yesterday or N/A.",
    "currency_symbol_or_text": "Prices include currency symbols or text (USD, $).",
    "decimal_separator_variation": "Decimal/thousands separators vary (1 234,56).",
    "negative_or_parentheses_price": "Negative/adjustment prices shown with parentheses.",
    "quantity_non_numeric": "Quantity stored as text or mixed units.",
    "quantity_range_string": "Quantity stored as a range like 2-3.",
    "email_invalid_format": "Email is missing @ or uses ' at ' or broken values.",
    "phone_inconsistent_format": "Phone numbers use inconsistent formatting or missing separators.",
    "address_multiline_or_missing_punctuation": "Addresses include newlines or missing commas.",
    "product_name_typo_or_variant": "Product names include typos or variants.",
    "product_unknown": "Product name does not exist in catalog.",
    "country_region_mixed": "Country mixed with region/state in same field.",
    "tags_mixed_delimiters": "Tags use mixed delimiters (comma, semicolon, pipe, slash).",
    "tax_or_discount_percent_string": "Tax/discount sometimes stored as a percent string.",
    "shipping_cost_free_string": "Shipping cost stored as FREE text.",
    "swapped_fields": "Two fields swapped by mistake.",
    "total_price_mismatch": "Total price does not match components or quantity.",
    "duplicate_order_id_conflict": "Duplicate Order ID with conflicting values.",
    "header_row_inside_data": "Header-like row appears inside data.",
    "merged_columns_duplicates": "Extra near-duplicate columns from merges.",
    "inconsistent_currency": "Currency code inconsistent or missing.",
}

BLANK_TOKENS = {None, "", " ", "N/A", "na", "NULL", "null", "-"}


def flag(reasons, label):
    if reasons is not None and label not in reasons:
        reasons.append(label)


def is_blank(value):
    return value in BLANK_TOKENS


def maybe_blank(value, prob=0.05, reasons=None):
    if random.random() < prob:
        flag(reasons, "missing_value_placeholder")
        return random.choice(list(BLANK_TOKENS))
    return value


def maybe_whitespace(value, prob=0.2, reasons=None):
    if value is None:
        return value
    if random.random() < prob:
        flag(reasons, "leading_trailing_whitespace")
        return f"{random.choice(['', ' ', '  ', '\\t'])}{value}{random.choice(['', ' ', '  '])}"
    return value


def messy_case(value, prob=0.3, reasons=None):
    if value is None:
        return value
    if random.random() < prob:
        flag(reasons, "inconsistent_case")
        return random.choice([str(value).upper(), str(value).lower(), str(value).title()])
    return value


def messy_order_id(i, reasons=None):
    base = 1000 + i
    styles = [
        f"#{base}",
        f"{base}",
        f"ORD-{base}",
        f"ORD{base}",
        f"{base}-01",
        f"{base:05d}",
        f" {base} ",
    ]
    order_id = random.choice(styles)
    if order_id.strip() != f"#{base}":
        flag(reasons, "inconsistent_order_id_format")
    order_id = maybe_blank(order_id, prob=0.03, reasons=reasons)
    return order_id


def messy_date(date_obj, reasons=None):
    if random.random() < 0.05:
        flag(reasons, "invalid_date_token")
        return random.choice(["today", "yesterday", "N/A", "unknown"])
    if random.random() < 0.1:
        flag(reasons, "missing_value_placeholder")
        return None
    if random.random() < 0.04:
        flag(reasons, "outlier_date")
        date_obj = date_obj + timedelta(days=random.choice([-3650, -1800, 365, 720]))

    rand = random.random()
    if rand < 0.35:
        return date_obj.strftime("%Y-%m-%d")
    if rand < 0.6:
        flag(reasons, "mixed_date_formats")
        return date_obj.strftime("%d/%m/%Y")
    if rand < 0.8:
        flag(reasons, "mixed_date_formats")
        return date_obj.strftime("%m-%d-%Y %H:%M")
    if rand < 0.93:
        flag(reasons, "mixed_date_formats")
        return date_obj.strftime("%Y/%m/%d %H:%M:%S %z").strip()
    flag(reasons, "mixed_date_formats")
    return date_obj.strftime("%Y.%m.%d")


def messy_price(price_float, reasons=None, allow_percent=False):
    if random.random() < 0.05:
        flag(reasons, "missing_value_placeholder")
        return None
    rand = random.random()
    if allow_percent and rand < 0.12:
        flag(reasons, "tax_or_discount_percent_string")
        return f"{random.choice([5, 10, 15, 20])}%"
    if rand < 0.35:
        return price_float
    if rand < 0.55:
        flag(reasons, "currency_symbol_or_text")
        return f"${price_float:,.2f}"
    if rand < 0.7:
        flag(reasons, "currency_symbol_or_text")
        return f"USD {price_float:,.2f}"
    if rand < 0.82:
        flag(reasons, "decimal_separator_variation")
        return f"{price_float:,.2f}".replace(",", " ")
    if rand < 0.92:
        flag(reasons, "decimal_separator_variation")
        return f"{price_float:,.2f}".replace(".", ",")
    flag(reasons, "negative_or_parentheses_price")
    return f"({price_float:,.2f})"


def messy_country(reasons=None):
    options = [
        "USA",
        "usa",
        "U.S.A.",
        "United States",
        "United States of America",
        "US",
        "United States, CA",
        "US-CA",
        "California, US",
        "U S A",
    ]
    choice = random.choice(options)
    if "," in choice or "-" in choice or "California" in choice:
        flag(reasons, "country_region_mixed")
    return choice


def messy_quantity(qty, reasons=None):
    options = [
        qty,
        str(qty),
        f"{qty}.0",
        f"{qty} pcs",
        f"{qty}-{qty + 1}",
        f"{qty:02d}",
    ]
    value = random.choice(options)
    if isinstance(value, str):
        flag(reasons, "quantity_non_numeric")
        if "-" in value:
            flag(reasons, "quantity_range_string")
    return value


def messy_email(reasons=None):
    if random.random() < 0.12:
        flag(reasons, "email_invalid_format")
        return random.choice([None, "", "N/A", "unknown@", "user at mail.com"])
    email = fake.email()
    if random.random() < 0.2:
        flag(reasons, "email_invalid_format")
        email = email.replace("@", " at ")
    return email.upper() if random.random() < 0.1 else email


def messy_phone(reasons=None):
    phone = fake.phone_number()
    if random.random() < 0.2:
        flag(reasons, "phone_inconsistent_format")
        phone = phone.replace("-", " ").replace("(", "").replace(")", "")
    if random.random() < 0.07:
        flag(reasons, "phone_inconsistent_format")
        phone = phone.replace(" ", "")
    return phone


def messy_address(reasons=None):
    addr = fake.address()
    if random.random() < 0.25:
        flag(reasons, "address_multiline_or_missing_punctuation")
        addr = addr.replace("\n", ", ")
    if random.random() < 0.12:
        flag(reasons, "address_multiline_or_missing_punctuation")
        addr = addr.replace(",", "")
    return addr


def messy_product(name, reasons=None):
    if random.random() < 0.1:
        flag(reasons, "product_name_typo_or_variant")
        return name.replace("e", "3", 1)
    if random.random() < 0.08:
        flag(reasons, "product_name_typo_or_variant")
        return name.replace(" ", "")
    if random.random() < 0.06:
        flag(reasons, "product_unknown")
        return random.choice(["Yoga Matt", "Bottle Steel", "Runner Shoes Pro", "Protein Whey"])
    return messy_case(name, prob=0.3, reasons=reasons)


def messy_tags(reasons=None):
    tags = random.sample(["vip", "gift", "wholesale", "first-time", "backorder"], k=random.randint(0, 3))
    if not tags:
        return random.choice(["", None])
    sep = random.choice([",", ";", "|", "/", " , ", " ; "])
    if sep not in [",", ";"]:
        flag(reasons, "tags_mixed_delimiters")
    return sep.join(tags)


def messy_shipping_cost(reasons=None):
    if random.random() < 0.12:
        flag(reasons, "shipping_cost_free_string")
        return "FREE"
    return messy_price(random.choice([0, 4.99, 7.5, 9.99]), reasons=reasons)


def generate_nightmare_data(num_rows=300):
    print("Injecting real-world mess into data...")

    data = []
    row_reasons_list = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)

    for i in range(num_rows):
        reasons = []
        product_name = random.choice(list(PRODUCTS.keys()))
        base_price = PRODUCTS[product_name]
        quantity = random.randint(1, 10)
        real_date = fake.date_between(start_date=start_date, end_date=end_date)

        customer_name = fake.name()
        if random.random() < 0.15:
            parts = customer_name.split(" ")
            if len(parts) >= 2:
                customer_name = f"{parts[-1]}, {' '.join(parts[:-1])}"

        unit_price = messy_price(base_price, reasons=reasons)
        discount = messy_price(round(base_price * quantity * random.choice([0, 0.05, 0.1, 0.15]), 2), reasons=reasons, allow_percent=True)
        tax = messy_price(round(base_price * quantity * random.choice([0.06, 0.07, 0.08]), 2), reasons=reasons, allow_percent=True)
        shipping = messy_shipping_cost(reasons=reasons)

        total_price = messy_price(base_price * quantity, reasons=reasons)

        row = {
            "Order ID": messy_order_id(i, reasons=reasons),
            "Order Date": messy_date(real_date, reasons=reasons),
            "Customer Name": maybe_blank(customer_name, prob=0.03, reasons=reasons),
            "Customer ID": maybe_blank(
                random.choice([f"CUST-{random.randint(100, 999)}", f"{random.randint(10000, 99999)}"]),
                prob=0.1,
                reasons=reasons,
            ),
            "Email": maybe_blank(messy_email(reasons=reasons), prob=0.06, reasons=reasons),
            "Phone": maybe_blank(messy_phone(reasons=reasons), prob=0.12, reasons=reasons),
            "Address": maybe_blank(messy_address(reasons=reasons), prob=0.12, reasons=reasons),
            "Product": messy_product(product_name, reasons=reasons),
            "Quantity": messy_quantity(quantity, reasons=reasons),
            "Unit Price": unit_price,
            "Discount": discount,
            "Tax": tax,
            "Shipping Cost": shipping,
            "Total Price": total_price,
            "Currency": random.choice(["USD", "usd", "US$", "EUR", "", None]),
            "Payment Status": random.choice(
                ["Paid", "paid", "PAID", "Unpaid", "Refunded", "Partially Refunded", "Chargeback"]
            ),
            "Fulfillment Status": random.choice(["fulfilled", "partial", "unfulfilled", "cancelled", "FULFILLED"]),
            "Shipping Country": messy_country(reasons=reasons),
            "Shipping Method": random.choice(["Standard", "Express", "Pickup", "International", "Local Delivery"]),
            "Order Tags": messy_tags(reasons=reasons),
            "Notes": random.choice(
                ["", None, "Call before delivery", "Leave at door", "Fragile, handle with care", "!!!"]
            ),
        }

        if row["Currency"] not in ["USD", "usd", "US$"]:
            flag(reasons, "inconsistent_currency")

        if random.random() < 0.05:
            flag(reasons, "swapped_fields")
            row["Shipping Country"], row["Product"] = row["Product"], row["Shipping Country"]

        if random.random() < 0.08:
            flag(reasons, "total_price_mismatch")
            row["Total Price"] = row["Quantity"]

        if random.random() < 0.015:
            flag(reasons, "header_row_inside_data")
            for k in list(row.keys()):
                row[k] = k

        for k in list(row.keys()):
            row[k] = maybe_whitespace(row[k], prob=0.2, reasons=reasons)

        data.append(row)
        row_reasons_list.append(reasons)

    for idx in random.sample(range(len(data)), k=min(10, len(data))):
        dup = dict(data[idx])
        dup_reasons = list(row_reasons_list[idx])
        flag(dup_reasons, "duplicate_order_id_conflict")
        dup["Payment Status"] = random.choice(["Paid", "Refunded", "Partially Refunded", "Unpaid"])
        dup["Order Date"] = messy_date(fake.date_between(start_date=start_date, end_date=end_date), reasons=dup_reasons)
        data.append(dup)
        row_reasons_list.append(dup_reasons)

    df = pd.DataFrame(data)

    added_merge_cols = False
    if random.random() < 0.7:
        df["OrderId"] = df["Order ID"].where(df.index % 3 == 0, None)
        added_merge_cols = True
    if random.random() < 0.7:
        df["OrderDate"] = df["Order Date"].where(df.index % 4 == 0, None)
        added_merge_cols = True
    if random.random() < 0.7:
        df["Total"] = df["Total Price"].where(df.index % 5 == 0, None)
        added_merge_cols = True
    if added_merge_cols:
        for reasons in row_reasons_list:
            flag(reasons, "merged_columns_duplicates")

    filename = "shopify_dirty_data.csv"
    df.to_csv(filename, index=False)

    # Reasons report
    reasons_rows = []
    for idx, reasons in enumerate(row_reasons_list):
        order_id = df.iloc[idx].get("Order ID")
        reasons_rows.append(
            {
                "row_index": idx,
                "order_id": order_id,
                "dirty_reasons": ";".join(sorted(set(reasons))),
            }
        )

    reasons_df = pd.DataFrame(reasons_rows)
    reasons_df.to_csv("dirty_reasons.csv", index=False)

    counts = Counter()
    for reasons in row_reasons_list:
        counts.update(set(reasons))

    with open("dirty_report.txt", "w", encoding="utf-8") as f:
        f.write("Dirtiness catalog (why this data is messy):\n")
        for key, desc in DIRTINESS_CATALOG.items():
            f.write(f"- {key}: {desc}\n")
        f.write("\nApplied counts in this run:\n")
        for key, _ in sorted(DIRTINESS_CATALOG.items()):
            f.write(f"- {key}: {counts.get(key, 0)} rows\n")

    print(f"Dirty data generated: {filename}")
    print("Reasons written to: dirty_report.txt and dirty_reasons.csv")


if __name__ == "__main__":
    generate_nightmare_data()
