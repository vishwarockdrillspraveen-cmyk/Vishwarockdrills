from datetime import date

import streamlit as st

from database import (
    get_customer_advances,
    get_customer_outstanding,
    get_customers,
    get_sales,
    get_warranty_claims,
)


def _as_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _within_range(value, start_date, end_date):
    try:
        record_date = _as_date(value)
    except (TypeError, ValueError):
        return False
    return start_date <= record_date <= end_date


def _render_section(title, rows, empty_message):
    st.subheader(title)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.caption(empty_message)


def customer_reports_page():
    st.header("Reports", icon=":material/summarize:")
    st.caption("Review customer activity across a selected date range.")

    customers = get_customers()
    if not customers:
        st.info("Add customers before generating reports.")
        return

    customer_labels = {
        str(row[0]): f"{row[1]} ({row[0]})"
        for row in customers
    }
    today = date.today()
    default_start = today.replace(day=1)

    customer_col, start_col, end_col = st.columns([2, 1, 1])
    with customer_col:
        selected_phones = st.multiselect(
            "Customers",
            options=list(customer_labels),
            format_func=lambda phone: customer_labels[phone],
            placeholder="Select one or more customers",
            key="customer_report_customers",
        )
    with start_col:
        start_date = st.date_input("From date", value=default_start, key="customer_report_start")
    with end_col:
        end_date = st.date_input("To date", value=today, key="customer_report_end")

    if not selected_phones:
        st.info("Select at least one customer to view the report.")
        return
    if start_date > end_date:
        st.error("From date must be on or before To date.")
        return

    selected_phone_set = set(selected_phones)
    customer_advances = [
        row for row in get_customer_advances()
        if str(row[1]) in selected_phone_set and _within_range(row[5], start_date, end_date)
    ]
    outstanding_entries = [
        row for row in get_customer_outstanding()
        if str(row[1]) in selected_phone_set and _within_range(row[3], start_date, end_date)
    ]
    payments = [
        row for row in outstanding_entries
        if str(row[5] or "").startswith("Payment:")
    ]
    manual_outstanding = [
        row for row in outstanding_entries
        if not str(row[5] or "").startswith("Payment:")
    ]
    sales = [
        row for row in get_sales()
        if str(row[1]) in selected_phone_set and _within_range(row[6], start_date, end_date)
    ]
    warranty_claims = [
        row for row in get_warranty_claims()
        if str(row[10] or "") in selected_phone_set and _within_range(row[9], start_date, end_date)
    ]

    advance_total = sum(float(row[6] or 0) for row in customer_advances)
    payment_total = sum(abs(float(row[4] or 0)) for row in payments)
    outstanding_total = sum(float(row[4] or 0) for row in manual_outstanding)
    sales_total = sum(float(row[7] or 0) * int(row[13] or 1) for row in sales)
    sales_pending = sum(float(row[9] or 0) for row in sales)
    warranty_total = sum(float(row[8] or 0) for row in warranty_claims)

    st.caption(f"Reporting period: {start_date.isoformat()} to {end_date.isoformat()}")
    summary_rows = [
        ("Customer advances", advance_total),
        ("Payments received", payment_total),
        ("Outstanding entries", outstanding_total),
        ("Sales value", sales_total),
        ("Sales pending", sales_pending),
        ("Warranty claims", warranty_total),
    ]
    for offset in range(0, len(summary_rows), 3):
        metric_cols = st.columns(3)
        for column, (label, amount) in zip(metric_cols, summary_rows[offset:offset + 3]):
            with column:
                st.metric(label, f"₹{amount:,.2f}")

    activity_rows = [
        {
            "Type": "Customer advance",
            "Date": row[5],
            "Customer": row[2],
            "Phone": row[1],
            "Paid to": row[4],
            "Company": row[3] or "-",
            "Amount": float(row[6] or 0),
            "Payment mode": row[7],
            "Details": row[8] or row[9] or "-",
        }
        for row in customer_advances
    ]
    activity_rows.extend(
        {
            "Type": "Payment received",
            "Date": row[3],
            "Customer": row[2],
            "Phone": row[1],
            "Paid to": "Business",
            "Company": "-",
            "Amount": abs(float(row[4] or 0)),
            "Payment mode": "-",
            "Details": row[5] or "-",
        }
        for row in payments
    )
    activity_rows.sort(key=lambda row: row["Date"], reverse=True)
    _render_section("Advances and payments", activity_rows, "No advances or payments in this date range.")

    _render_section(
        "Outstanding entries",
        [
            {
                "Entry ID": row[0],
                "Date": row[3],
                "Customer": row[2],
                "Phone": row[1],
                "Outstanding amount": float(row[4] or 0),
                "Remarks": row[5] or "-",
            }
            for row in manual_outstanding
        ],
        "No outstanding entries in this date range.",
    )

    _render_section(
        "Sales",
        [
            {
                "Sale ID": row[0],
                "Date": row[6],
                "Customer": row[2],
                "Phone": row[1],
                "Product": row[4],
                "Company": row[5],
                "Quantity": int(row[13] or 1),
                "Unit price": float(row[7] or 0),
                "Sale value": float(row[7] or 0) * int(row[13] or 1),
                "Paid": float(row[8] or 0),
                "Pending": float(row[9] or 0),
            }
            for row in sales
        ],
        "No sales in this date range.",
    )

    _render_section(
        "Warranty claims",
        [
            {
                "Claim ID": row[0],
                "Date": row[9],
                "Customer": row[11] or "Not recorded",
                "Phone": row[10] or "Not recorded",
                "Product": row[2],
                "Company": row[3],
                "Initial mm": float(row[4] or 0),
                "Current mm": float(row[5] or 0),
                "Warranty credit": float(row[8] or 0),
            }
            for row in warranty_claims
        ],
        "No warranty claims in this date range.",
    )