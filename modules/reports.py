import io
from datetime import date
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

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


def _build_report_jpg(start_date, end_date, report_metrics, customer_rows, export_rows):
    width = 1800
    margin = 64
    content_width = width - (margin * 2)
    transaction_rows = [
        row for row in export_rows
        if row["Record type"] not in {"Summary", "Customer summary"}
    ]
    row_height = 46
    customer_table_height = 48 + (len(customer_rows) * row_height)
    transaction_table_height = 48 + (max(len(transaction_rows), 1) * row_height)
    height = 64 + 72 + 38 + 42 + 2 * (112 + 16) + 44 + customer_table_height + 72 + 34 + transaction_table_height + 64

    image = Image.new("RGB", (width, height), "#F3F6F4")
    draw = ImageDraw.Draw(image)
    title_font = _report_font(38, bold=True)
    subtitle_font = _report_font(19)
    section_font = _report_font(23, bold=True)
    card_label_font = _report_font(17, bold=True)
    card_value_font = _report_font(27, bold=True)
    table_header_font = _report_font(14, bold=True)
    table_font = _report_font(14)

    draw.rounded_rectangle((margin, 36, width - margin, 144), radius=14, fill="#FFFFFF", outline="#D8E2DD", width=2)
    draw.text((margin + 28, 50), "Vishwa Rock Drills | Customer report", font=title_font, fill="#174F50")
    draw.text(
        (margin + 30, 108),
        f"{start_date.isoformat()} to {end_date.isoformat()}  |  {len(customer_rows)} selected customer(s)",
        font=subtitle_font,
        fill="#52615D",
    )

    y = 174
    metric_colors = ["#17666B", "#B85C22", "#337458", "#587FAD"]
    card_gap = 18
    card_width = (content_width - (card_gap * 3)) // 4
    for metric_index, (label, amount) in enumerate(report_metrics):
        row_index, column_index = divmod(metric_index, 4)
        left = margin + column_index * (card_width + card_gap)
        top = y + row_index * 128
        color = metric_colors[column_index]
        draw.rounded_rectangle(
            (left, top, left + card_width, top + 112),
            radius=12,
            fill="#FFFFFF",
            outline="#D8E2DD",
            width=2,
        )
        draw.rounded_rectangle((left, top, left + 8, top + 112), radius=4, fill=color)
        draw.text((left + 22, top + 18), label, font=card_label_font, fill="#52615D")
        draw.text((left + 22, top + 53), f"₹{float(amount):,.2f}", font=card_value_font, fill="#202B2A")

    y += 2 * 128 + 18
    draw.text((margin, y), "Customer summary", font=section_font, fill="#174F50")
    y += 40
    customer_headers = [
        "Customer",
        "Outstanding net",
        "Sales value",
        "Sales paid",
        "Sales pending",
        "Advances",
        "Warranty claims",
        "Total outstanding",
    ]
    customer_widths = [360, 190, 175, 150, 175, 180, 190, 188]
    x = margin
    draw.rectangle((x, y, width - margin, y + 48), fill="#17666B")
    for label, cell_width in zip(customer_headers, customer_widths):
        draw.text((x + 10, y + 15), _fit_report_text(draw, label, table_header_font, cell_width - 18), font=table_header_font, fill="#FFFFFF")
        x += cell_width
    y += 48

    customer_fields = [
        lambda row: f"{row['Customer Name']} ({row['Customer Phone']})",
        lambda row: f"₹{row['Outstanding Entries (Net)']:,.2f}",
        lambda row: f"₹{row['Sales Value']:,.2f}",
        lambda row: f"₹{row['Sales Paid']:,.2f}",
        lambda row: f"₹{row['Sales Outstanding']:,.2f}",
        lambda row: f"₹{row['Customer Advances (Credit)']:,.2f}",
        lambda row: f"₹{row['Warranty Claims (Credit)']:,.2f}",
        lambda row: f"₹{row['Total Outstanding']:,.2f}",
    ]
    for row_index, customer in enumerate(customer_rows):
        background = "#FFFFFF" if row_index % 2 == 0 else "#EAF0ED"
        draw.rectangle((margin, y, width - margin, y + row_height), fill=background)
        x = margin
        for cell_width, value_func in zip(customer_widths, customer_fields):
            value = _fit_report_text(draw, value_func(customer), table_font, cell_width - 18)
            draw.text((x + 10, y + 15), value, font=table_font, fill="#202B2A")
            x += cell_width
        y += row_height

    y += 26
    draw.text((margin, y), "Transaction details", font=section_font, fill="#174F50")
    y += 40
    detail_headers = ["Type", "Date", "Customer", "Reference", "Details", "Qty", "Amount", "Paid", "Pending / credit"]
    base_widths = [145, 112, 220, 82, 500, 56, 145, 125, 175]
    width_scale = content_width / sum(base_widths)
    detail_widths = [int(cell_width * width_scale) for cell_width in base_widths]
    detail_widths[-1] += content_width - sum(detail_widths)
    draw.rectangle((margin, y, width - margin, y + 48), fill="#355F58")
    x = margin
    for label, cell_width in zip(detail_headers, detail_widths):
        draw.text((x + 8, y + 16), _fit_report_text(draw, label, table_header_font, cell_width - 14), font=table_header_font, fill="#FFFFFF")
        x += cell_width
    y += 48

    for row_index, record in enumerate(transaction_rows):
        row_values = _report_detail_values(record)
        background = "#FFFFFF" if row_index % 2 == 0 else "#EAF0ED"
        draw.rectangle((margin, y, width - margin, y + row_height), fill=background)
        x = margin
        for cell_width, value in zip(detail_widths, row_values):
            fitted_value = _fit_report_text(draw, value, table_font, cell_width - 14)
            draw.text((x + 8, y + 15), fitted_value, font=table_font, fill="#202B2A")
            x += cell_width
        y += row_height
    if not transaction_rows:
        draw.rectangle((margin, y, width - margin, y + row_height), fill="#FFFFFF")
        draw.text((margin + 12, y + 15), "No transaction details in this date range.", font=table_font, fill="#52615D")

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue()


def _report_detail_values(record):
    record_type = record["Record type"]
    if record_type == "Customer advance":
        details = " | ".join(filter(None, [record.get("Paid to"), record.get("Company"), record.get("Payment mode"), record.get("Transaction details")]))
        return [record_type, record.get("Date"), record.get("Customer name"), record.get("Reference ID"), details, "", "", record.get("Amount paid"), ""]
    if record_type == "Payment received":
        return [record_type, record.get("Date"), record.get("Customer name"), record.get("Reference ID"), record.get("Transaction details"), "", "", record.get("Amount paid"), ""]
    if record_type == "Outstanding entry":
        return [record_type, record.get("Date"), record.get("Customer name"), record.get("Reference ID"), record.get("Transaction details"), "", record.get("Amount"), "", ""]
    if record_type == "Sale":
        details = " | ".join(filter(None, [record.get("Product"), record.get("Company"), f"Unit price: {record.get('Unit price', '')}"]))
        return [record_type, record.get("Date"), record.get("Customer name"), record.get("Reference ID"), details, record.get("Quantity"), record.get("Sale value"), record.get("Amount paid"), record.get("Amount pending")]
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
    return [record_type, record.get("Date"), record.get("Customer name"), record.get("Reference ID"), details, "", "", "", record.get("Warranty credit")]


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

    report_jpg = _build_report_jpg(
        start_date,
        end_date,
        report_metrics,
        customer_summary_rows,
        export_rows,
    )
    st.download_button(
        "Download full report (JPG)",
        data=report_jpg,
        file_name=f"customer_report_{start_date.isoformat()}_to_{end_date.isoformat()}.jpg",
        mime="image/jpeg",
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