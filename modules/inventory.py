import streamlit as st
from datetime import datetime

from database import (
    add_inventory_record,
    delete_inventory_record,
    get_inventory_records,
    get_products,
    update_inventory_record,
    validate_date_value,
)


def _date_field(label, value=None):
    try:
        if value is None:
            return st.date_input(label)
        return st.date_input(label, value=value)
    except Exception:
        st.error(f"{label} must be a valid date.")
        return None


def inventory_tracking_page():
    st.header("Purchase Details")

    if "inventory_tracking_action" not in st.session_state:
        st.session_state.inventory_tracking_action = "Add Purchase"

    menu_options = ["Add Purchase", "Edit Purchase", "Delete Purchase"]
    action_col, content_col = st.columns([1.5, 4])

    with action_col:
        for option in menu_options:
            if st.button(option, key=f"inventory_tracking_action_{option}", use_container_width=True):
                st.session_state.inventory_tracking_action = option

    with content_col:
        selected_action = st.session_state.inventory_tracking_action

        if selected_action == "Add Purchase":
            st.subheader("Add Purchase Details")
            with st.form("add_inventory_form", clear_on_submit=True):
                all_products = get_products()
                product_choices = [f"{row[2]} ({row[1]})" for row in all_products]

                if not product_choices:
                    st.info("No products available yet. Add a product first in Product Management.")
                    st.stop()

                selected_product_label = st.selectbox("Product Name", product_choices)
                product_name = selected_product_label.split(" (", 1)[0]
                product_company = next((row[1] for row in all_products if row[2] == product_name), "")
                product_id = next((str(row[0]) for row in all_products if row[2] == product_name), "")

                st.text_input("Product Company", value=product_company, disabled=True)
                st.text_input("Product ID", value=product_id, disabled=True)
                qty_received = st.number_input("Qty Received", min_value=0, step=1, value=0)
                received_date = _date_field("Purchase Date")
                if received_date is None:
                    st.stop()

                single_product_price = st.number_input("Price per qty", min_value=0.0, step=0.01, format="%.2f")
                total_price = qty_received * single_product_price
                st.markdown(f"### Total Price: {total_price:,.2f}")
                submitted = st.form_submit_button("Save Inventory")
                if submitted:
                    if product_name.strip() == "":
                        st.error("Product Name is required")
                    elif product_company.strip() == "":
                        st.error("Product Company is required")
                    else:
                        try:
                            normalized_date = validate_date_value(received_date, "Purchase Date")
                            add_inventory_record(
                                product_id,
                                product_name.strip(),
                                product_company.strip(),
                                normalized_date,
                                qty_received,
                                single_product_price
                            )
                            st.success("Inventory record saved successfully")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

        elif selected_action == "Edit Purchase":
            st.subheader("Edit Purchase Details")
            inventory_records = get_inventory_records()

            if not inventory_records:
                st.info("No inventory records found")
                return

            search_term = st.text_input(
                "Search by product ID or product name",
                placeholder="Type product ID or name"
            )

            if search_term.strip() == "":
                st.info("Enter a product ID or product name to search")
                return

            filtered_records = [
                row for row in inventory_records
                if str(row[1]).lower().find(search_term.lower()) != -1
                or str(row[2]).lower().find(search_term.lower()) != -1
            ]

            if not filtered_records:
                st.info("No matching inventory record found")
                return

            record_options = [f"{row[2]} (ID: {row[1]})" for row in filtered_records]
            selected_record_label = st.selectbox("Matching inventory records", record_options)
            selected_row = filtered_records[record_options.index(selected_record_label)]
            selected_inventory_id = selected_row[0]

            with st.form("edit_inventory_form"):
                all_products = get_products()
                product_names = [row[2] for row in all_products]
                default_name = selected_row[2]
                if default_name in product_names:
                    selected_index = product_names.index(default_name)
                else:
                    selected_index = 0

                edited_product_name = st.selectbox(
                    "Product Name",
                    options=product_names,
                    index=selected_index
                )
                product_company = next((row[1] for row in all_products if row[2] == edited_product_name), "")
                edited_product_id = st.text_input(
                    "Product ID",
                    value=str(next((row[0] for row in all_products if row[2] == edited_product_name), selected_row[1]))
                )
                edited_product_company = st.text_input("Product Company", value=product_company, disabled=True)
                edited_qty_received = st.number_input(
                    "Qty Received",
                    min_value=0,
                    step=1,
                    value=int(selected_row[4] or 0)
                )
                edited_received_date = _date_field(
                    "Purchase Date",
                    value=datetime.strptime(selected_row[5], "%Y-%m-%d").date()
                )
                if edited_received_date is None:
                    st.stop()

                edited_single_product_price = st.number_input(
                    "Price per qty",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    value=float(selected_row[6] or 0)
                )

                submit = st.form_submit_button("Update Inventory")
                if submit:
                    if edited_product_name.strip() == "" or edited_product_company.strip() == "":
                        st.error("Product Name and Product Company are required")
                    else:
                        try:
                            normalized_date = validate_date_value(edited_received_date, "Purchase Date")
                            update_inventory_record(
                                selected_inventory_id,
                                edited_product_id,
                                edited_product_name.strip(),
                                edited_product_company.strip(),
                                normalized_date,
                                edited_qty_received,
                                edited_single_product_price
                            )
                            st.success("Inventory record updated successfully")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

            edited_total_price = edited_qty_received * edited_single_product_price
            st.markdown(f"### Total Price: {edited_total_price:,.2f}")

        elif selected_action == "Delete Purchase":
            st.subheader("Delete Purchase Details")
            inventory_records = get_inventory_records()

            if not inventory_records:
                st.info("No inventory records found")
                return

            search_term = st.text_input(
                "Search by product ID or product name",
                placeholder="Type product ID or name"
            )

            if search_term.strip() == "":
                st.info("Enter a product ID or product name to search")
                return

            filtered_records = [
                row for row in inventory_records
                if str(row[1]).lower().find(search_term.lower()) != -1
                or str(row[2]).lower().find(search_term.lower()) != -1
            ]

            if not filtered_records:
                st.info("No matching inventory record found")
                return

            record_options = [f"{row[2]} (ID: {row[1]})" for row in filtered_records]
            selected_record_label = st.selectbox("Matching inventory records", record_options)
            selected_row = filtered_records[record_options.index(selected_record_label)]
            selected_inventory_id = selected_row[0]

            st.warning(f"Are you sure you want to delete inventory record: {selected_row[2]} (ID: {selected_row[1]})?")
            with st.form("delete_inventory_form"):
                delete_submitted = st.form_submit_button("Delete This Record")
                if delete_submitted:
                    delete_inventory_record(selected_inventory_id)
                    st.success("Inventory record deleted")
                    st.rerun()
