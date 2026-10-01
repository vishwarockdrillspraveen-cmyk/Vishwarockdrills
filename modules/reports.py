import io
import re
import zipfile
from datetime import date
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from database import (
    get_customer_advances,
    get_customer_outstanding,
    get_customers,
    get_products,
    get_sales,
    get_warranty_claims,
)


def _as_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _format_report_date(value):
    try:
        return _as_date(value).strftime("%d-%m-%Y")
    except (TypeError, ValueError):
        return str(value or "")


def _report_download_filename(customer_names, start_date, end_date):
    if len(customer_names) == 1:
        customer_part = str(customer_names[0] or "Customer")
    else:
        customer_part = "Multiple_Customers"
    customer_part = re.sub(r"[^A-Za-z0-9]+", "_", customer_part).strip("_") or "Customer"
    date_range = f"{_format_report_date(start_date)}_to_{_format_report_date(end_date)}"
    return f"{customer_part}_{date_range}.jpg"


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


def _report_font(size, bold=False):
    font_candidates = (
        [
            Path("C:/Windows/Fonts/segoeuib.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        ]
        if bold
        else [
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        ]
    )
    for font_path in font_candidates:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default(size=size)


def _fit_report_text(draw, value, font, max_width):
    text = str(value or "")
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "...", font=font) > max_width:
        text = text[:-1]
    return text + "..."


def _build_report_ledger(export_rows):
    type_order = {
        "Outstanding entry": 0,
        "Balance": 0,
        "Sale": 1,
        "Customer advance": 2,
        "Payment": 2,
        "Payment received": 3,
        "Warranty claim": 4,
    }
    transactions = []

    for record in export_rows:
        record_type = record["Record type"]
        debit = 0.0
        credit = 0.0
        reference = record.get("Reference ID", "")
        date_text = str(record.get("Date", ""))

        if record_type in {"Summary", "Customer summary"}:
            continue
        if record_type == "Outstanding entry":
            amount = float(record.get("Amount", 0) or 0)
            debit = max(amount, 0.0)
            credit = max(-amount, 0.0)
            details = record.get("Transaction details", "")
        elif record_type == "Sale":
            debit = float(record.get("Sale value", 0) or 0)
            credit = float(record.get("Amount paid", 0) or 0)
            details = record.get("Product", "")
        elif record_type == "Customer advance":
            credit = float(record.get("Amount paid", 0) or 0)
            payment_mode = record.get("Payment mode", "")
            details = payment_mode if payment_mode in {"Cash", "UPI", "Discount"} else ""
        elif record_type == "Payment received":
            credit = float(record.get("Amount paid", 0) or 0)
            details = record.get("Transaction details", "")
        elif record_type == "Warranty claim":
            credit = float(record.get("Warranty credit", 0) or 0)
            details = " | ".join(
                filter(
                    None,
                    [
                        record.get("Product"),
                        record.get("Company"),
                        f"Initial: {record.get('Initial size (mm)', '')} mm",
                        f"Current: {record.get('Current size (mm)', '')} mm",
                        f"Limit: {record.get('Warranty limit (mm)', '')} mm",
                    ],
                )
            )
        else:
            continue

        transactions.append(
            {
                "Date": date_text,
                "Customer": record.get("Customer name", ""),
                "Type": {
                    "Outstanding entry": "Balance",
                    "Customer advance": "Payment",
                }.get(record_type, record_type),
                "Reference": reference,
                "Details": details,
                "Debit": debit,
                "Credit": credit,
            }
        )

    transactions.sort(
        key=lambda row: (
            _as_date(row["Date"]),
            type_order.get(row["Type"], 99),
            row["Customer"],
            str(row["Reference"]),
        )
    )
    total_debit = sum(row["Debit"] for row in transactions)
    total_credit = sum(row["Credit"] for row in transactions)
    balance = 0.0
    for transaction in transactions:
        balance += transaction["Debit"] - transaction["Credit"]
        transaction["Balance"] = balance

    return transactions, total_debit, total_credit, balance


def _build_report_jpg(start_date, end_date, selected_customer_names, export_rows):
    width = 1800
    margin = 64
    content_width = width - (margin * 2)
    transactions, total_debit, total_credit, balance = _build_report_ledger(export_rows)
    title_font = _report_font(48, bold=True)
    subtitle_font = _report_font(29)
    header_font = _report_font(24, bold=True)
    row_font = _report_font(25)
    amount_font = _report_font(32, bold=True)
    total_font = _report_font(34, bold=True)
    header_height = 68
    row_height = 76
    totals_height = 90
    height = 208 + header_height + (max(len(transactions), 1) * row_height) + totals_height + 36
    image = Image.new("RGB", (width, height), "#F3F6F4")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((margin, 30, width - margin, 154), radius=16, fill="#FFFFFF", outline="#D8E2DD", width=2)
    title_text = ", ".join(str(name) for name in selected_customer_names)
    draw.text(
        (margin + 28, 48),
        _fit_report_text(draw, title_text, title_font, content_width - 56),
        font=title_font,
        fill="#174F50",
    )
    draw.text(
        (margin + 30, 108),
        f"Date range: {_format_report_date(start_date)} to {_format_report_date(end_date)}",
        font=subtitle_font,
        fill="#52615D",
    )

    headers = ["Date", "Transaction", "Details", "Debit", "Credit", "Balance"]
    column_widths = [175, 220, 420, 245, 245, 303]
    column_widths[-1] += content_width - sum(column_widths)
    y = 178
    draw.rectangle((margin, y, width - margin, y + header_height), fill="#17666B")
    x = margin
    for label, column_width in zip(headers, column_widths):
        draw.text((x + 12, y + 19), label, font=header_font, fill="#FFFFFF")
        x += column_width
    y += header_height

    if transactions:
        for row_index, transaction in enumerate(transactions):
            background = "#FFFFFF" if row_index % 2 == 0 else "#EAF0ED"
            draw.rectangle((margin, y, width - margin, y + row_height), fill=background)
            values = [
                _format_report_date(transaction["Date"]),
                transaction["Type"],
                transaction["Details"],
                f"{transaction['Debit']:,.2f}" if transaction["Debit"] else "-",
                f"{transaction['Credit']:,.2f}" if transaction["Credit"] else "-",
                f"{transaction['Balance']:,.2f}",
            ]
            x = margin
            for column_index, (value, column_width) in enumerate(zip(values, column_widths)):
                font = amount_font if column_index in {3, 4, 5} else row_font
                draw.text((x + 12, y + 22), _fit_report_text(draw, value, font, column_width - 24), font=font, fill="#202B2A")
                x += column_width
            y += row_height
    else:
        draw.rectangle((margin, y, width - margin, y + row_height), fill="#FFFFFF")
        draw.text((margin + 12, y + 22), "No transactions in this date range.", font=row_font, fill="#52615D")
        y += row_height

    draw.rectangle((margin, y, width - margin, y + totals_height), fill="#DDE9E3")
    footer_values = ["TOTAL", "", "", f"{total_debit:,.2f}", f"{total_credit:,.2f}", f"{balance:,.2f}"]
    x = margin
    for value, column_width in zip(footer_values, column_widths):
        draw.text((x + 12, y + 27), _fit_report_text(draw, value, total_font, column_width - 24), font=total_font, fill="#174F50")
        x += column_width

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=96, subsampling=0, optimize=True)
    return output.getvalue()


def _build_customer_reports_zip(start_date, end_date, selected_phones, customer_names, export_rows):
    customer_reports = io.BytesIO()
    used_filenames = set()
    with zipfile.ZipFile(customer_reports, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for phone in selected_phones:
            customer_name = customer_names[phone]
            customer_rows = [row for row in export_rows if str(row.get("Customer phone", "")) == phone]
            report_jpg = _build_report_jpg(start_date, end_date, [customer_name], customer_rows)
            filename = _report_download_filename([customer_name], start_date, end_date)
            if filename.lower() in used_filenames:
                filename = _report_download_filename([f"{customer_name}_{phone}"], start_date, end_date)
            used_filenames.add(filename.lower())
            archive.writestr(filename, report_jpg)
    return customer_reports.getvalue()


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
    all_customers_option = "__all_customers__"
    today = date.today()
    default_start = today.replace(day=1)

    customer_col, start_col, end_col = st.columns([2, 1, 1])
    with customer_col:
        customer_selection = st.selectbox(
            "Customer",
            options=[all_customers_option, *customer_labels],
            format_func=lambda phone: "All customers" if phone == all_customers_option else customer_labels[phone],
            key="customer_report_customer",
        )
    selected_phones = list(customer_labels) if customer_selection == all_customers_option else [customer_selection]
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
    products_by_id = {str(row[0]): row for row in get_products()}
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

    st.caption(f"Reporting period: {_format_report_date(start_date)} to {_format_report_date(end_date)}")
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
    total_outstanding = sum(row["Total Outstanding"] for row in customer_summary_rows)
    report_metrics = [
        ("Total outstanding", total_outstanding),
        ("Outstanding entries (net)", outstanding_total),
        ("Sales value", sales_total),
        ("Sales paid", sales_paid_total),
        ("Sales pending", sales_pending),
        ("Customer advances", advance_total),
        ("Payments received (ledger)", payment_total),
        ("Warranty claims", warranty_total),
    ]
    for offset in range(0, len(report_metrics), 4):
        metric_columns = st.columns(4)
        for column, (label, amount) in zip(metric_columns, report_metrics[offset:offset + 4]):
            with column:
                st.metric(label, f"₹{amount:,.2f}")

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
        product = products_by_id.get(str(row[3]))
        sold_by_name = str(product[3] or "").strip() if product else ""
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
                "Product": sold_by_name or row[4],
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

    customer_reports = _build_customer_reports_zip(
        start_date,
        end_date,
        selected_phones,
        customer_names,
        export_rows,
    )
    st.download_button(
        "Download customer reports (ZIP)",
        data=customer_reports,
        file_name=f"customer_reports_{_format_report_date(start_date)}_to_{_format_report_date(end_date)}.zip",
        mime="application/zip",
        icon=":material/download:",
        type="primary",
    )

    activity_rows = [
        {
            "Type": "Customer advance",
            "Date": _format_report_date(row[5]),
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
            "Date": _format_report_date(row[3]),
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
                    "Date": _format_report_date(row[3]),
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
                    "Date": _format_report_date(row[6]),
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
                    "Date": _format_report_date(row[9]),
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