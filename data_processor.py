from __future__ import annotations

from dataclasses import dataclass
from typing import Any, IO

import pandas as pd

from clean_data import clean_dataframe


@dataclass(frozen=True)
class _ColumnChoices:
    order_id: tuple[str, ...]
    order_date: tuple[str, ...]
    product: tuple[str, ...]
    quantity: tuple[str, ...]
    unit_price: tuple[str, ...]
    discount: tuple[str, ...]
    tax: tuple[str, ...]
    shipping_cost: tuple[str, ...]
    total_price: tuple[str, ...]


_COLUMNS = _ColumnChoices(
    order_id=("order_id", "orderid", "id"),
    order_date=("order_date", "orderdate", "date", "created_at", "createdat"),
    product=("product", "product_name", "item", "title"),
    quantity=("quantity", "qty"),
    unit_price=("unit_price", "price", "unitprice"),
    discount=("discount",),
    tax=("tax",),
    shipping_cost=("shipping_cost", "shipping", "shippingcost"),
    total_price=("total_price", "total", "totalprice", "amount"),
)


def _first_existing_column(df: pd.DataFrame, choices: tuple[str, ...]) -> str | None:
    for name in choices:
        if name in df.columns:
            return name
    return None


def _coalesce_series(df: pd.DataFrame, choices: tuple[str, ...]) -> pd.Series | None:
    col = _first_existing_column(df, choices)
    return df[col] if col else None


def _as_number(series: pd.Series | None) -> pd.Series | None:
    if series is None:
        return None
    if pd.api.types.is_numeric_dtype(series):
        return series
    return pd.to_numeric(series, errors="coerce")


def _as_datetime(series: pd.Series | None) -> pd.Series | None:
    if series is None:
        return None
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    return pd.to_datetime(series, errors="coerce")


def load_and_process_data(data_source: str | IO[bytes] | Any):
    """
    Streamlit-friendly loader:
    - Accepts a file path, file-like object, or Streamlit UploadedFile.
    - Cleans data via clean_data.clean_dataframe.
    - Returns (kpi_data_dict, message). If failed: (None, error_message).
    """
    try:
        df_raw = pd.read_csv(data_source, dtype=str)
    except Exception as e:
        return None, f"读取 CSV 失败: {e}"

    try:
        df, _report = clean_dataframe(df_raw)
    except Exception as e:
        return None, f"清洗数据失败: {e}"

    order_id = _coalesce_series(df, _COLUMNS.order_id)
    order_date = _as_datetime(_coalesce_series(df, _COLUMNS.order_date))
    product = _coalesce_series(df, _COLUMNS.product)
    quantity = _as_number(_coalesce_series(df, _COLUMNS.quantity))
    unit_price = _as_number(_coalesce_series(df, _COLUMNS.unit_price))
    discount = _as_number(_coalesce_series(df, _COLUMNS.discount))
    tax = _as_number(_coalesce_series(df, _COLUMNS.tax))
    shipping_cost = _as_number(_coalesce_series(df, _COLUMNS.shipping_cost))
    total_price = _as_number(_coalesce_series(df, _COLUMNS.total_price))

    if order_date is None or order_date.notna().sum() == 0:
        return None, "找不到可用的日期列（如 Order Date / order_date）"
    if product is None:
        return None, "找不到可用的商品列（如 Product / product）"

    # Build Total_Sales
    total_sales = total_price
    if total_sales is None or total_sales.notna().sum() == 0:
        if quantity is not None and unit_price is not None:
            total_sales = quantity.fillna(0) * unit_price.fillna(0)
        else:
            total_sales = pd.Series([0.0] * len(df), index=df.index, dtype="float64")

    # If components exist, try to incorporate them (best-effort).
    if shipping_cost is not None:
        total_sales = total_sales + shipping_cost.fillna(0)
    if tax is not None:
        total_sales = total_sales + tax.fillna(0)
    if discount is not None:
        # If discount looks like a fraction (0-1), treat it as percent of subtotal.
        frac_like = discount.between(0, 1, inclusive="both").mean() >= 0.6
        if frac_like:
            subtotal = (quantity.fillna(0) * unit_price.fillna(0)) if (quantity is not None and unit_price is not None) else total_sales
            total_sales = total_sales - (subtotal.fillna(0) * discount.fillna(0))
        else:
            total_sales = total_sales - discount.fillna(0)

    display_df = pd.DataFrame(
        {
            "Date": order_date.dt.date,
            "Product": product.astype(str),
            "Quantity": quantity if quantity is not None else None,
            "Unit_Price": unit_price if unit_price is not None else None,
            "Total_Sales": total_sales.astype(float),
        }
    )
    if order_id is not None:
        display_df.insert(0, "Order_ID", order_id.astype(str))

    display_df = display_df.dropna(subset=["Date", "Product"])

    total_revenue = float(display_df["Total_Sales"].sum())
    if order_id is not None:
        total_orders = int(display_df["Order_ID"].nunique())
    else:
        total_orders = int(len(display_df))
    avg_order_value = float(total_revenue / total_orders) if total_orders else 0.0

    daily_sales = (
        display_df.groupby("Date", as_index=False)["Total_Sales"]
        .sum()
        .sort_values("Date", ascending=True)
        .reset_index(drop=True)
    )

    kpi_data = {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "avg_order_value": avg_order_value,
        "daily_sales": daily_sales,
        "raw_df": display_df,
    }
    return kpi_data, "OK"

