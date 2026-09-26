import csv
import io
import streamlit as st
from datetime import datetime, timedelta

from database import (
    add_sale,
    delete_sale,
    get_customers,
    get_product_sale_price,
    get_product_warranty_details,
    get_products,
    get_sales,
    update_sale,
    validate_date_value,
)


def _safe_date_input(label, value=None):
    try:
        return st.date_input(label, value=value) if value is not None else st.date_input(label)
    except Exception:
        st.error(f"{label} must be a valid date.")
        return None


def _format_customer(customer_row):
    return f"{customer_row[1]} ({customer_row[0]})"


def _format_product_row(row):
    return f"{row[2]} ({row[1]}) - ID: {row[0]}"


def _get_customer_phone_from_label(label, customers):
    for customer in customers:
        if _format_customer(customer) == label:
            return customer[0]
    return ""


def _get_product_row_from_label(label, product_rows):
    for row in product_rows:
        if _format_product_row(row) == label:
            return row
    return None


def sales_page():
    st.header("Sales Management")

    if "sales_action" not in st.session_state:
        st.session_state.sales_action = "Add Sale"

    menu_options = ["Add Sale", "Edit Sale", "Delete Sale"]
    action_col, content_col = st.columns([1.5, 4])

    with action_col:
        st.markdown("#### Sales")
        for option in menu_options:
            if st.button(option, key=f"sales_action_{option}", use_container_width=True):
                st.session_state.sales_action = option

    with content_col:
        sales_rows = get_sales()
        st.markdown("### Stored Sales")
        if sales_rows:
            sales_display_rows = [
                {
                    "Sale ID": row[0],
                    "Customer Phone": row[1],
                    "Customer Name": row[2],
                    "Product ID": row[3],
                    "Product": row[4],
                    "Company": row[5],
                    "Date": row[6],
                    "Sale Price": float(row[7] or 0),
                    "Quantity": int(row[13] if len(row) > 13 else 1),
                    "Total Value": float((row[7] or 0) * (row[13] if len(row) > 13 else 1)),
                    "Paid": float(row[8] or 0),
                    "Pending": float(row[9] or 0),
                }
                for row in sales_rows
            ]
            st.dataframe(
                sales_display_rows,
                use_container_width=True,
                hide_index=True,
            )

            csv_buffer = io.StringIO()
            fieldnames = [
                "Sale ID",
                "Customer Phone",
                "Customer Name",
                "Product ID",
                "Product",
                "Company",
                "Date",
                "Sale Price",
                "Quantity",
                "Total Value",
                "Paid",
                "Pending",
            ]
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sales_display_rows)

            st.download_button(
                label="Download Sales CSV",
                data=csv_buffer.getvalue(),
                file_name="sales_details.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("No sales stored in backend yet.")

        st.markdown("---")
        selected_action = st.session_state.sales_action

        if selected_action == "Add Sale":
            st.subheader("Add Sale")
            customers = get_customers()
            product_rows = get_products()

            if not customers:
                st.info("No existing customers found. Add a customer before recording a sale.")
                return

            if not product_rows:
                st.info("No products are available. Add a product before creating a sale.")
                return

            with st.form("add_sale_form", clear_on_submit=True):
                customer_search = st.text_input("Search customer by name or phone", placeholder="Type a customer name or phone number")
                customer_options = [_format_customer(row) for row in customers]
                if customer_search.strip():
                    customer_options = [
                        label for label in customer_options
                        if customer_search.lower() in label.lower()
                    ]
                if not customer_options:
                    st.warning("No matching customer found. Please use a different search value.")
                    st.stop()

                selected_customer_label = st.selectbox("Select Customer", customer_options)
                customer_phone = _get_customer_phone_from_label(selected_customer_label, customers)
                customer_name = next((row[1] for row in customers if row[0] == customer_phone), "")

                product_search = st.text_input("Search product", placeholder="Type product name or company")
                product_options = [_format_product_row(row) for row in product_rows]
                if product_search.strip():
                    product_options = [
                        label for label in product_options
                        if product_search.lower() in label.lower()
                    ]
                if not product_options:
                    st.warning("No matching product found. Please use a different search value.")
                    st.stop()

                selected_product_label = st.selectbox("Select Product", product_options)
                selected_product_row = _get_product_row_from_label(selected_product_label, product_rows)
                product_id = selected_product_row[0]
                product_name = selected_product_row[2]
                product_company = selected_product_row[1]
                default_sale_price = float(get_product_sale_price(product_id) or 0)

                st.markdown("### Sale Details")
                sale_col1, sale_col2 = st.columns(2)
                with sale_col1:
                    sale_date = _safe_date_input("Sale Date")
                    if sale_date is None:
                        st.stop()
                    actual_price = default_sale_price
                    quantity = st.number_input("Quantity", min_value=1, step=1, value=1)
                with sale_col2:
                    paid_amount = 0.0
                    pending_amount = max(actual_price - paid_amount, 0.0)

                st.markdown("### Product Summary")
                summary_col1, summary_col2, summary_col3 = st.columns(3)
                with summary_col1:
                    st.text_input("Product ID", value=str(product_id), disabled=True)
                with summary_col2:
                    st.text_input("Product Name", value=product_name, disabled=True)
                with summary_col3:
                    st.text_input("Product Company", value=product_company, disabled=True)

                warranty_applicable = False
                warranty_start_date = None
                warranty_end_date = None
                product_warranty_flag, product_size_mm, warranty_limit_mm = get_product_warranty_details(product_id)
                if product_warranty_flag:
                    warranty_applicable = True
                    warranty_start_date = sale_date.isoformat()
                    warranty_end_date = sale_date.isoformat()
                    warranty_threshold_mm = float(product_size_mm) - float(warranty_limit_mm)
                    st.success(
                        f"Warranty applies while the product size stays above {warranty_threshold_mm:.1f} mm "
                        f"(allowed wear: {warranty_limit_mm} mm)."
                    )
                else:
                    st.info("This product does not carry warranty coverage.")

                submitted = st.form_submit_button("Save Sale", use_container_width=True)
                if submitted:
                    if not customer_phone:
                        st.error("Please select a valid customer")
                    else:
                        try:
                            normalized_sale_date = validate_date_value(sale_date, "Sale Date")
                            add_sale(
                                customer_phone,
                                product_id,
                                product_name,
                                product_company,
                                normalized_sale_date,
                                actual_price,
                                paid_amount,
                                pending_amount,
                                warranty_applicable,
                                warranty_start_date,
                                warranty_end_date,
                                quantity,
                                customer_name,
                            )
                            st.success("Sale saved successfully")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

        elif selected_action == "Edit Sale":
            st.subheader("Edit Sale")
            sales_rows = get_sales()
            if not sales_rows:
                st.info("No sales found")
                return

            search_term = st.text_input("Search by customer, phone, or product", placeholder="Type a customer name, phone, or product")
            if search_term.strip() == "":
                st.info("Enter a customer name, phone number, or product name to search")
                return

            filtered_rows = [
                row for row in sales_rows
                if str(row[1]).lower().find(search_term.lower()) != -1
                or str(row[2]).lower().find(search_term.lower()) != -1
                or str(row[3]).lower().find(search_term.lower()) != -1
                or str(row[4]).lower().find(search_term.lower()) != -1
                or str(row[5]).lower().find(search_term.lower()) != -1
                or str(row[6]).lower().find(search_term.lower()) != -1
            ]

            if not filtered_rows:
                st.info("No matching sale found")
                return

            sale_options = [f"{row[2]} ({row[1]}) - {row[4]} - {row[6]}" for row in filtered_rows]
            selected_sale_label = st.selectbox("Matching sales", sale_options)
            selected_sale_row = filtered_rows[sale_options.index(selected_sale_label)]
            selected_sale_id = selected_sale_row[0]

            customers = get_customers()
            customer_options = [_format_customer(row) for row in customers]
            customer_index = customer_options.index(_format_customer(next((c for c in customers if c[0] == selected_sale_row[1]), customers[0])))

            product_rows = get_products()
            product_options = [_format_product_row(row) for row in product_rows]
            product_index = 0
            if str(selected_sale_row[3]) in [str(row[0]) for row in product_rows]:
                product_index = [str(row[0]) for row in product_rows].index(str(selected_sale_row[3]))

            with st.form("edit_sale_form"):
                selected_customer_label = st.selectbox("Customer", customer_options, index=customer_index)
                customer_phone = _get_customer_phone_from_label(selected_customer_label, customers)
                customer_name = next((row[1] for row in customers if row[0] == customer_phone), selected_sale_row[2] or "")

                selected_product_label = st.selectbox("Product", product_options, index=product_index)
                selected_product_row = _get_product_row_from_label(selected_product_label, product_rows)
                product_id = selected_product_row[0]
                product_name = selected_product_row[2]
                product_company = selected_product_row[1]

                edited_sale_date = _safe_date_input(
                    "Sale Date",
                    value=datetime.strptime(selected_sale_row[6], "%Y-%m-%d").date()
                )
                if edited_sale_date is None:
                    st.stop()

                default_edit_price = float(get_product_sale_price(product_id) or selected_sale_row[7] or 0)
                edited_actual_price = default_edit_price
                edited_quantity = st.number_input("Quantity", min_value=1, step=1, value=int(selected_sale_row[13] if len(selected_sale_row) > 13 else 1))
                edited_paid_amount = float(selected_sale_row[8] or 0)
                edited_pending_amount = max(edited_actual_price - edited_paid_amount, 0.0)

                warranty_applicable = bool(selected_sale_row[10])
                warranty_start_date = selected_sale_row[11]
                warranty_end_date = selected_sale_row[12]
                if selected_product_row:
                    product_warranty_flag, product_size_mm, warranty_limit_mm = get_product_warranty_details(product_id)
                    if product_warranty_flag:
                        warranty_applicable = True
                        warranty_start_date = edited_sale_date.isoformat()
                        warranty_end_date = edited_sale_date.isoformat()
                        warranty_threshold_mm = float(product_size_mm) - float(warranty_limit_mm)
                        st.success(
                            f"Warranty applies while the product size stays above {warranty_threshold_mm:.1f} mm "
                            f"(allowed wear: {warranty_limit_mm} mm)."
                        )
                    else:
                        warranty_applicable = False
                        warranty_start_date = None
                        warranty_end_date = None
                        st.info("This product does not carry warranty coverage.")

                submit = st.form_submit_button("Update Sale")
                if submit:
                    try:
                        normalized_sale_date = validate_date_value(edited_sale_date, "Sale Date")
                        update_sale(
                            selected_sale_id,
                            customer_phone,
                            product_id,
                            product_name,
                            product_company,
                            normalized_sale_date,
                            edited_actual_price,
                            edited_paid_amount,
                            edited_pending_amount,
                            warranty_applicable,
                            warranty_start_date,
                            warranty_end_date,
                            edited_quantity,
                            customer_name,
                        )
                        st.success("Sale updated successfully")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

        elif selected_action == "Delete Sale":
            st.subheader("Delete Sale")
            sales_rows = get_sales()
            if not sales_rows:
                st.info("No sales found")
                return

            search_term = st.text_input("Search by customer, phone, or product", placeholder="Type a customer name, phone, or product")
            if search_term.strip() == "":
                st.info("Enter a customer name, phone number, or product name to search")
                return

            filtered_rows = [
                row for row in sales_rows
                if str(row[1]).lower().find(search_term.lower()) != -1
                or str(row[2]).lower().find(search_term.lower()) != -1
                or str(row[3]).lower().find(search_term.lower()) != -1
                or str(row[4]).lower().find(search_term.lower()) != -1
                or str(row[5]).lower().find(search_term.lower()) != -1
                or str(row[6]).lower().find(search_term.lower()) != -1
            ]

            if not filtered_rows:
                st.info("No matching sale found")
                return

            sale_options = [f"{row[2]} ({row[1]}) - {row[4]} - {row[6]}" for row in filtered_rows]
            selected_sale_label = st.selectbox("Matching sales", sale_options)
            selected_sale_row = filtered_rows[sale_options.index(selected_sale_label)]

            st.warning(f"Are you sure you want to delete the sale for {selected_sale_row[2]} ({selected_sale_row[1]})?")
            with st.form("delete_sale_form"):
                delete_submitted = st.form_submit_button("Delete This Sale")
                if delete_submitted:
                    delete_sale(selected_sale_row[0])
                    st.success("Sale deleted")
                    st.rerun()
