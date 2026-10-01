import csv
import io
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
    outstanding_total = sum(float(row[4] or 0) for row in outstanding_entries)
    sales_total = sum(float(row[7] or 0) * int(row[13] or 1) for row in sales)
    sales_paid_total = sum(float(row[8] or 0) for row in sales)
    sales_pending = sum(float(row[9] or 0) for row in sales)
    warranty_total = sum(float(row[8] or 0) for row in warranty_claims)

    st.caption(f"Reporting period: {start_date.isoformat()} to {end_date.isoformat()}")
    summary_rows = [
        ("Customer advances", advance_total),
        ("Payments received (ledger)", payment_total),
        ("Outstanding entries (net)", outstanding_total),
        ("Sales value", sales_total),
        ("Sales paid", sales_paid_total),
        ("Sales pending", sales_pending),
        ("Warranty claims", warranty_total),
    ]

    customer_names = {str(row[0]): row[1] for row in customers}
    customer_summary = {
        phone: {
            "Customer Phone": phone,
            "Customer Name": customer_names.get(phone, ""),
            "Outstanding Entries (Net)": 0.0,
            "Sales Value": 0.0,
            "Sales Paid": 0.0,
            "Sales Outstanding": 0.0,
            "Payments Received (Ledger)": 0.0,
            "Customer Advances (Credit)": 0.0,
            "Warranty Claims (Credit)": 0.0,
            "Total Outstanding": 0.0,
        }
        for phone in selected_phones
    }
    for row in outstanding_entries:
        customer_summary[str(row[1])]["Outstanding Entries (Net)"] += float(row[4] or 0)
    for row in payments:
        customer_summary[str(row[1])]["Payments Received (Ledger)"] += abs(float(row[4] or 0))
    for row in customer_advances:
        customer_summary[str(row[1])]["Customer Advances (Credit)"] += float(row[6] or 0)
    for row in sales:
        customer = customer_summary[str(row[1])]
        quantity = int(row[13] or 1)
        customer["Sales Value"] += float(row[7] or 0) * quantity
        customer["Sales Paid"] += float(row[8] or 0)
        customer["Sales Outstanding"] += float(row[9] or 0)
    for row in warranty_claims:
        customer_summary[str(row[10])]["Warranty Claims (Credit)"] += float(row[8] or 0)
    for customer in customer_summary.values():
        customer["Total Outstanding"] = (
            customer["Outstanding Entries (Net)"]
            + customer["Sales Outstanding"]
            - customer["Customer Advances (Credit)"]
            - customer["Warranty Claims (Credit)"]
        )

    customer_summary_rows = sorted(
        customer_summary.values(),
        key=lambda row: row["Total Outstanding"],
        reverse=True,
    )
    st.subheader("Consolidated customer report")
    st.dataframe(customer_summary_rows, width="stretch", hide_index=True)

    export_columns = [
        "Record type",
        "Category",
        "From date",
        "To date",
        "Date",
        "Customer name",
        "Customer phone",
        "Reference ID",
        "Product",
        "Company",
        "Quantity",
        "Unit price",
        "Sale value",
        "Amount paid",
        "Amount pending",
        "Outstanding entries (net)",
        "Sales paid",
        "Sales outstanding",
        "Payments received (ledger)",
        "Customer advances (credit)",
        "Warranty claims (credit)",
        "Total outstanding",
        "Amount",
        "Payment mode",
        "Paid to",
        "Transaction details",
        "Initial size (mm)",
        "Current size (mm)",
        "Warranty limit (mm)",
        "Warranty credit",
    ]
    export_rows = []
    for category, amount in summary_rows:
        export_rows.append(
            {
                "Record type": "Summary",
                "Category": category,
                "From date": start_date.isoformat(),
                "To date": end_date.isoformat(),
                "Amount": amount,
            }
        )
    for row in customer_summary_rows:
        export_rows.append(
            {
                "Record type": "Customer summary",
                "Category": "Consolidated customer report",
                "From date": start_date.isoformat(),
                "To date": end_date.isoformat(),
                "Customer name": row["Customer Name"],
                "Customer phone": row["Customer Phone"],
                "Outstanding entries (net)": row["Outstanding Entries (Net)"],
                "Sales value": row["Sales Value"],
                "Sales paid": row["Sales Paid"],
                "Sales outstanding": row["Sales Outstanding"],
                "Payments received (ledger)": row["Payments Received (Ledger)"],
                "Customer advances (credit)": row["Customer Advances (Credit)"],
                "Warranty claims (credit)": row["Warranty Claims (Credit)"],
                "Total outstanding": row["Total Outstanding"],
            }
        )

    for row in customer_advances:
        export_rows.append(
            {
                "Record type": "Customer advance",
                "Category": "Advances and payments",
                "From date": start_date.isoformat(),
                "To date": end_date.isoformat(),
                "Date": row[5],
                "Customer name": row[2],
                "Customer phone": row[1],
                "Reference ID": row[0],
                "Company": row[3] or "",
                "Amount paid": float(row[6] or 0),
                "Payment mode": row[7],
                "Paid to": row[4],
                "Transaction details": row[8] or row[9] or "",
            }
        )
    for row in payments:
        export_rows.append(
            {
                "Record type": "Payment received",
                "Category": "Advances and payments",
                "From date": start_date.isoformat(),
                "To date": end_date.isoformat(),
                "Date": row[3],
                "Customer name": row[2],
                "Customer phone": row[1],
                "Reference ID": row[0],
                "Amount paid": abs(float(row[4] or 0)),
                "Paid to": "Business",
                "Transaction details": row[5] or "",
            }
        )
    for row in manual_outstanding:
        export_rows.append(
            {
                "Record type": "Outstanding entry",
                "Category": "Outstanding entries",
                "From date": start_date.isoformat(),
                "To date": end_date.isoformat(),
                "Date": row[3],
                "Customer name": row[2],
                "Customer phone": row[1],
                "Reference ID": row[0],
                "Amount": float(row[4] or 0),
                "Transaction details": row[5] or "",
            }
        )
    for row in sales:
        quantity = int(row[13] or 1)
        export_rows.append(
            {
                "Record type": "Sale",
                "Category": "Sales",
                "From date": start_date.isoformat(),
                "To date": end_date.isoformat(),
                "Date": row[6],
                "Customer name": row[2],
                "Customer phone": row[1],
                "Reference ID": row[0],
                "Product": row[4],
                "Company": row[5],
                "Quantity": quantity,
                "Unit price": float(row[7] or 0),
                "Sale value": float(row[7] or 0) * quantity,
                "Amount paid": float(row[8] or 0),
                "Amount pending": float(row[9] or 0),
            }
        )
    for row in warranty_claims:
        export_rows.append(
            {
                "Record type": "Warranty claim",
                "Category": "Warranty claims",
                "From date": start_date.isoformat(),
                "To date": end_date.isoformat(),
                "Date": row[9],
                "Customer name": row[11] or "Not recorded",
                "Customer phone": row[10] or "Not recorded",
                "Reference ID": row[0],
                "Product": row[2],
                "Company": row[3],
                "Initial size (mm)": float(row[4] or 0),
                "Current size (mm)": float(row[5] or 0),
                "Warranty limit (mm)": float(row[7] or 0),
                "Warranty credit": float(row[8] or 0),
            }
        )

    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=export_columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(export_rows)
    st.download_button(
        "Download full report (CSV)",
        data="\ufeff" + csv_buffer.getvalue(),
        file_name=f"customer_report_{start_date.isoformat()}_to_{end_date.isoformat()}.csv",
        mime="text/csv",
        icon=":material/download:",
        type="primary",
    )

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
    with st.expander("Transaction details", expanded=False):
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
                    "Amount pending": float(row[9] or 0),
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