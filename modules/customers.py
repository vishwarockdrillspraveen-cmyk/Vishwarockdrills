import streamlit as st
import pandas as pd

from database import (
    add_customer,
    get_customers,
    delete_customer,
    update_customer
)


def customer_page():

    st.header("Customer Management")

    if "customer_action" not in st.session_state:
        st.session_state.customer_action = "Add Customer"

    menu_options = ["Add Customer", "Edit Customer", "Delete Customer"]
    action_col, content_col = st.columns([1.5, 4])

    with action_col:
        st.markdown("#### Customers")
        for option in menu_options:
            if st.button(option, key=f"customer_action_{option}", use_container_width=True):
                st.session_state.customer_action = option

    with content_col:
        selected_action = st.session_state.customer_action

        if selected_action == "Add Customer":
            st.subheader("Add Customer")
            with st.form("add_customer_form", clear_on_submit=True):
                customer_name = st.text_input("Customer Name")
                phone = st.text_input("Phone Number")
                email = st.text_input("Email")
                submitted = st.form_submit_button("Save Customer")

                if submitted:
                    if customer_name.strip() == "":
                        st.error("Customer Name is required")
                    elif phone.strip() == "":
                        st.error("Phone Number is required and acts as the primary key")
                    else:
                        existing_customers = get_customers()
                        if any(row[0] == phone.strip() for row in existing_customers):
                            st.error("Phone Number already exists")
                        else:
                            add_customer(customer_name, phone.strip(), email)
                            st.success("Customer Saved Successfully")
                            st.rerun()

        elif selected_action == "Edit Customer":
            st.subheader("Edit Customer")
            customers = get_customers()

            if not customers:
                st.info("No customers available to edit")
                return

            search_term = st.text_input(
                "Search by customer name or phone number",
                placeholder="Type a name or phone number"
            )

            if search_term.strip() == "":
                st.info("Enter a customer name or phone number to search")
                return

            filtered_customers = [
                row for row in customers
                if str(row[0]).lower().find(search_term.lower()) != -1
                or str(row[1]).lower().find(search_term.lower()) != -1
            ]

            if not filtered_customers:
                st.info("No matching customer found")
                return

            customer_options = [f"{row[1]} ({row[0]})" for row in filtered_customers]
            selected_customer_label = st.selectbox("Matching customers", customer_options)
            selected_row = filtered_customers[customer_options.index(selected_customer_label)]
            selected_phone = selected_row[0]

            with st.form("edit_customer_form"):
                edited_name = st.text_input(
                    "Edit Customer Name",
                    value=selected_row[1]
                )
                st.text_input(
                    "Phone Number",
                    value=selected_row[0],
                    disabled=True
                )
                edited_email = st.text_input(
                    "Edit Email",
                    value=selected_row[2]
                )
                st.caption(f"Created: {selected_row[3]}")
                st.caption(f"Last Updated: {selected_row[4]}")

                update_submitted = st.form_submit_button("Update Customer")
                if update_submitted:
                    if edited_name.strip() == "":
                        st.error("Customer Name is required")
                    else:
                        update_customer(selected_phone, edited_name, edited_email)
                        st.success("Customer Updated Successfully")
                        st.rerun()

        elif selected_action == "Delete Customer":
            st.subheader("Delete Customer")
            customers = get_customers()

            if not customers:
                st.info("No customers available to delete")
                return

            search_term = st.text_input(
                "Search by customer name or phone number",
                placeholder="Type a name or phone number"
            )

            if search_term.strip() == "":
                st.info("Enter a customer name or phone number to search")
                return

            filtered_customers = [
                row for row in customers
                if str(row[0]).lower().find(search_term.lower()) != -1
                or str(row[1]).lower().find(search_term.lower()) != -1
            ]

            if not filtered_customers:
                st.info("No matching customer found")
                return

            customer_options = [f"{row[1]} ({row[0]})" for row in filtered_customers]
            selected_customer_label = st.selectbox("Matching customers", customer_options)
            selected_row = filtered_customers[customer_options.index(selected_customer_label)]
            selected_phone = selected_row[0]

            st.warning(f"Are you sure you want to delete customer: {selected_row[1]} ({selected_phone})?")
            with st.form("delete_customer_form"):
                delete_submitted = st.form_submit_button("Delete This Customer")
                if delete_submitted:
                    delete_customer(selected_phone)
                    st.success("Customer Deleted")
                    st.rerun()