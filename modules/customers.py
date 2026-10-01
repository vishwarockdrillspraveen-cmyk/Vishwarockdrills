import streamlit as st

from database import (
    add_customer,
    get_customers,
    delete_customer,
    update_customer
)
from modules.ui import action_control


def customer_page():
    st.header("Customers", icon=":material/groups:")
    st.caption("Manage customer contact details and account identity.")
    selected_action = action_control(
        "customer_action_mode",
        ["Add", "Edit", "Delete"],
        "Add",
    )
    customers = get_customers()

    st.subheader("Customer directory")
    if customers:
        customer_filter = st.text_input(
            "Filter customers",
            placeholder="Search by name, phone, or email",
            icon=":material/search:",
            key="customer_directory_filter",
        ).strip().lower()
        visible_customers = [
            row for row in customers
            if not customer_filter or customer_filter in " ".join(str(value or "") for value in row).lower()
        ]
        st.caption(f"Showing {len(visible_customers)} of {len(customers)} customers")
        st.dataframe(
            [
                {
                    "Customer name": row[1],
                    "Phone number": row[0],
                    "Email": row[2],
                    "Created": row[3],
                    "Last updated": row[4],
                }
                for row in visible_customers
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("No customers have been added yet.")

    if selected_action == "Add":
            st.subheader("Add customer")
            with st.form("add_customer_form", clear_on_submit=True):
                identity_col, contact_col = st.columns(2)
                with identity_col:
                    customer_name = st.text_input("Customer name")
                with contact_col:
                    phone = st.text_input("Phone number")
                email = st.text_input("Email")
                submitted = st.form_submit_button("Save customer", type="primary", icon=":material/person_add:")

                if submitted:
                    if customer_name.strip() == "":
                        st.error("Customer name is required")
                    elif phone.strip() == "":
                        st.error("Phone number is required and acts as the primary key")
                    else:
                        existing_customers = get_customers()
                        if any(row[0] == phone.strip() for row in existing_customers):
                            st.error("Phone number already exists")
                        else:
                            add_customer(customer_name, phone.strip(), email)
                            st.success("Customer saved successfully")
                            st.rerun()

    elif selected_action == "Edit":
            st.subheader("Edit customer")
            customers = get_customers()

            if not customers:
                st.info("No customers available to edit")
                return

            search_term = st.text_input("Find a customer", placeholder="Search by name or phone number", icon=":material/search:")

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
            selected_customer_label = st.selectbox("Matching customer", customer_options)
            selected_row = filtered_customers[customer_options.index(selected_customer_label)]
            selected_phone = selected_row[0]

            with st.form("edit_customer_form"):
                edited_name = st.text_input("Customer name", value=selected_row[1])
                st.text_input("Phone number", value=selected_row[0], disabled=True)
                edited_email = st.text_input("Email", value=selected_row[2])
                st.caption(f"Created: {selected_row[3]}")
                st.caption(f"Last Updated: {selected_row[4]}")

                update_submitted = st.form_submit_button("Save changes", type="primary", icon=":material/save:")
                if update_submitted:
                    if edited_name.strip() == "":
                        st.error("Customer name is required")
                    else:
                        update_customer(selected_phone, edited_name, edited_email)
                        st.success("Customer updated successfully")
                        st.rerun()

    elif selected_action == "Delete":
            st.subheader("Delete customer")
            customers = get_customers()

            if not customers:
                st.info("No customers available to delete")
                return

            search_term = st.text_input("Find a customer", placeholder="Search by name or phone number", icon=":material/search:")

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
            selected_customer_label = st.selectbox("Matching customer", customer_options)
            selected_row = filtered_customers[customer_options.index(selected_customer_label)]
            selected_phone = selected_row[0]

            st.warning(f"Are you sure you want to delete customer: {selected_row[1]} ({selected_phone})?")
            with st.form("delete_customer_form"):
                delete_submitted = st.form_submit_button("Delete customer", type="primary", icon=":material/delete:")
                if delete_submitted:
                    delete_customer(selected_phone)
                    st.success("Customer Deleted")
                    st.rerun()