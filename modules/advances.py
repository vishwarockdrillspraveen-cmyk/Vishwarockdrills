import streamlit as st
from datetime import datetime

from database import (
    add_company_advance,
    add_customer_advance,
    add_customer_outstanding,
    delete_company_advance,
    delete_customer_advance,
    delete_customer_outstanding,
    get_companies,
    get_company_advances,
    get_customer_advances,
    get_customer_outstanding,
    get_customer_report,
    get_customers,
    update_company_advance,
    update_customer_advance,
    update_customer_outstanding,
    validate_date_value,
)
from modules.ui import action_control

PAYMENT_MODES = ["Cash", "UPI", "Bank Transfer", "Cheque", "Other"]


def _safe_date_field(label, value=None):
    try:
        return st.date_input(label, value=value) if value is not None else st.date_input(label)
    except Exception:
        st.error(f"{label} must be a valid date.")
        return None


def _render_advance_table(rows, columns, filter_key):
    if not rows:
        st.info("No advance records available.")
        return
    dataframe = [dict(zip(columns, row)) for row in rows]
    search_term = st.text_input(
        "Filter records",
        placeholder="Search this list",
        icon=":material/search:",
        key=filter_key,
    ).strip().lower()
    visible_rows = [
        row for row in dataframe
        if not search_term or search_term in " ".join(str(value) for value in row.values()).lower()
    ]
    st.caption(f"Showing {len(visible_rows)} of {len(dataframe)} records")
    st.dataframe(visible_rows, width="stretch", hide_index=True)


def _render_company_advances():
    st.subheader("Company advances", icon=":material/account_balance:")
    selected_action = action_control("company_advance_action_mode", ["Add", "Edit", "Delete"], "Add")

    with st.container():

        companies = get_companies()
        if not companies:
            st.info("No companies are available. Add a company first in the Partnership with section.")
            return

        if selected_action == "Add":
            with st.form("add_company_advance_form", clear_on_submit=True):
                company_name = st.selectbox("Company", [row[1] for row in companies])
                advance_date = _safe_date_field("Advance Date")
                amount_paid = st.number_input("Amount Paid", min_value=0.0, step=0.01, format="%.2f")
                payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES)
                transaction_details = st.text_input("Transaction Details", placeholder="UPI ID, bank ref, cheque no., etc.")
                remarks = st.text_input("Remarks")

                if payment_mode != "Cash":
                    st.caption("Transaction Details is required for non-cash payment modes.")

                submitted = st.form_submit_button("Save Company Advance")
                if submitted:
                    try:
                        if payment_mode != "Cash" and transaction_details.strip() == "":
                            st.error("Transaction Details is required for non-cash payment modes.")
                        else:
                            add_company_advance(company_name, advance_date, amount_paid, payment_mode, transaction_details, remarks)
                            st.success("Company advance saved successfully")
                            st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

        elif selected_action == "Edit":
            rows = get_company_advances()
            if not rows:
                st.info("No company advances found.")
                return

            search_term = st.text_input("Search by company or remarks", placeholder="Type a company name or note")
            if search_term.strip() == "":
                st.info("Enter a company name or remarks to search")
                return

            filtered_rows = [
                row for row in rows
                if str(row[2]).lower().find(search_term.lower()) != -1 or str(row[7]).lower().find(search_term.lower()) != -1
            ]
            if not filtered_rows:
                st.info("No matching company advance found.")
                return

            options = [f"{row[2]} - {row[3]} - {row[4]:,.2f}" for row in filtered_rows]
            selected_label = st.selectbox("Matching company advances", options)
            selected_row = filtered_rows[options.index(selected_label)]
            selected_id = selected_row[0]

            with st.form("edit_company_advance_form"):
                company_name = st.selectbox("Company", [row[1] for row in companies], index=[row[1] for row in companies].index(selected_row[2]))
                advance_date = _safe_date_field("Advance Date", value=datetime.strptime(selected_row[3], "%Y-%m-%d").date())
                amount_paid = st.number_input("Amount Paid", min_value=0.0, step=0.01, format="%.2f", value=float(selected_row[4] or 0))
                payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES, index=PAYMENT_MODES.index(selected_row[5]) if selected_row[5] in PAYMENT_MODES else 0)
                transaction_details = st.text_input("Transaction Details", value=str(selected_row[6] or ""))
                remarks = st.text_input("Remarks", value=str(selected_row[7] or ""))
                submitted = st.form_submit_button("Update Company Advance")
                if submitted:
                    try:
                        if payment_mode != "Cash" and transaction_details.strip() == "":
                            st.error("Transaction Details is required for non-cash payment modes.")
                        else:
                            update_company_advance(selected_id, company_name, advance_date, amount_paid, payment_mode, transaction_details, remarks, selected_row[8])
                            st.success("Company advance updated successfully")
                            st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

        elif selected_action == "Delete":
            rows = get_company_advances()
            if not rows:
                st.info("No company advances found.")
                return

            search_term = st.text_input("Search by company or remarks", placeholder="Type a company name or note")
            if search_term.strip() == "":
                st.info("Enter a company name or remarks to search")
                return

            filtered_rows = [
                row for row in rows
                if str(row[2]).lower().find(search_term.lower()) != -1 or str(row[7]).lower().find(search_term.lower()) != -1
            ]
            if not filtered_rows:
                st.info("No matching company advance found.")
                return

            options = [f"{row[2]} - {row[3]} - {row[4]:,.2f}" for row in filtered_rows]
            selected_label = st.selectbox("Matching company advances", options)
            selected_row = filtered_rows[options.index(selected_label)]

            st.warning(f"Are you sure you want to delete the company advance for {selected_row[2]} on {selected_row[3]}?")
            with st.form("delete_company_advance_form"):
                if st.form_submit_button("Delete This Advance"):
                    delete_company_advance(selected_row[0])
                    st.success("Company advance deleted")
                    st.rerun()

        st.markdown("### Company Advances List")
        _render_advance_table(
            get_company_advances(),
            ["Advance ID", "Company ID", "Company Name", "Advance Date", "Amount Paid", "Payment Mode", "Transaction Details", "Remarks", "Linked Customer Advance ID"],
            "company_advances_filter",
        )


def _render_customer_advances():
    st.subheader("Customer advances and payments", icon=":material/payments:")
    selected_action = action_control("customer_advance_action_mode", ["Add", "Edit", "Delete"], "Add")

    with st.container():
        customers = get_customers()

        if selected_action == "Add":
            if not customers:
                st.info("No customers are available. Add a customer before recording an advance.")
                return

            with st.form("add_customer_advance_form", clear_on_submit=True):
                customer = st.selectbox("Customer", [f"{row[1]} ({row[0]})" for row in customers])
                customer_phone = next((row[0] for row in customers if f"{row[1]} ({row[0]})" == customer), customers[0][0])
                customer_name = next((row[1] for row in customers if row[0] == customer_phone), "")

                payment_to = st.selectbox("Payment To", ["Us", "Company"])
                company_name = ""
                if payment_to == "Company":
                    companies = get_companies()
                    if not companies:
                        st.info("No companies available. Add a company in Partnership with before creating a customer advance to company.")
                        return
                    company_name = st.selectbox("Company", [row[1] for row in companies])

                advance_date = _safe_date_field("Advance Date")
                amount_paid = st.number_input("Amount Paid", min_value=0.0, step=0.01, format="%.2f")
                payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES)
                transaction_details = st.text_input("Transaction Details", placeholder="UPI ID, bank ref, cheque no., etc.")
                remarks = st.text_input("Remarks")

                submitted = st.form_submit_button("Save Customer Advance")
                if submitted:
                    try:
                        if payment_mode != "Cash" and transaction_details.strip() == "":
                            st.error("Transaction Details is required for non-cash payment modes.")
                        else:
                            add_customer_advance(customer_phone, customer_name, company_name, payment_to, advance_date, amount_paid, payment_mode, transaction_details, remarks)
                            st.success("Customer advance saved successfully")
                            st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

        elif selected_action == "Edit":
            rows = get_customer_advances()
            if not rows:
                st.info("No customer advances found.")
                return

            search_term = st.text_input("Search by customer, company, or remarks", placeholder="Type a customer or company name")
            if search_term.strip() == "":
                st.info("Enter a customer or company name to search")
                return

            filtered_rows = [
                row for row in rows
                if str(row[1]).lower().find(search_term.lower()) != -1 or str(row[2]).lower().find(search_term.lower()) != -1 or str(row[3]).lower().find(search_term.lower()) != -1 or str(row[9]).lower().find(search_term.lower()) != -1
            ]
            if not filtered_rows:
                st.info("No matching customer advance found.")
                return

            options = [f"{row[2]} ({row[1]}) - {row[5]} - {row[6]:,.2f}" for row in filtered_rows]
            selected_label = st.selectbox("Matching customer advances", options)
            selected_row = filtered_rows[options.index(selected_label)]
            selected_id = selected_row[0]

            with st.form("edit_customer_advance_form"):
                row_customer = next((row for row in customers if row[0] == selected_row[1]), None)
                customer_name = row_customer[1] if row_customer else selected_row[2]
                customer_value = f"{customer_name} ({selected_row[1]})"
                customer_options = [f"{row[1]} ({row[0]})" for row in customers]
                customer_index = customer_options.index(customer_value) if customer_value in customer_options else 0
                customer = st.selectbox("Customer", customer_options, index=customer_index)
                customer_phone = next((row[0] for row in customers if f"{row[1]} ({row[0]})" == customer), customers[0][0])
                customer_name = next((row[1] for row in customers if row[0] == customer_phone), "")

                payment_to = st.selectbox("Payment To", ["Us", "Company"], index=["Us", "Company"].index(selected_row[4]))
                company_name = ""
                if payment_to == "Company":
                    company_options = [row[1] for row in get_companies()]
                    company_name = st.selectbox("Company", company_options, index=company_options.index(selected_row[3]) if selected_row[3] in company_options else 0)

                advance_date = _safe_date_field("Advance Date", value=datetime.strptime(selected_row[5], "%Y-%m-%d").date())
                amount_paid = st.number_input("Amount Paid", min_value=0.0, step=0.01, format="%.2f", value=float(selected_row[6] or 0))
                payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES, index=PAYMENT_MODES.index(selected_row[7]) if selected_row[7] in PAYMENT_MODES else 0)
                transaction_details = st.text_input("Transaction Details", value=str(selected_row[8] or ""))
                remarks = st.text_input("Remarks", value=str(selected_row[9] or ""))
                submitted = st.form_submit_button("Update Customer Advance")
                if submitted:
                    try:
                        if payment_mode != "Cash" and transaction_details.strip() == "":
                            st.error("Transaction Details is required for non-cash payment modes.")
                        else:
                            update_customer_advance(selected_id, customer_phone, customer_name, company_name, payment_to, advance_date, amount_paid, payment_mode, transaction_details, remarks)
                            st.success("Customer advance updated successfully")
                            st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

        elif selected_action == "Delete":
            rows = get_customer_advances()
            if not rows:
                st.info("No customer advances found.")
                return

            search_term = st.text_input("Search by customer, company, or remarks", placeholder="Type a customer or company name")
            if search_term.strip() == "":
                st.info("Enter a customer or company name to search")
                return

            filtered_rows = [
                row for row in rows
                if str(row[1]).lower().find(search_term.lower()) != -1 or str(row[2]).lower().find(search_term.lower()) != -1 or str(row[3]).lower().find(search_term.lower()) != -1 or str(row[9]).lower().find(search_term.lower()) != -1
            ]
            if not filtered_rows:
                st.info("No matching customer advance found.")
                return

            options = [f"{row[2]} ({row[1]}) - {row[5]} - {row[6]:,.2f}" for row in filtered_rows]
            selected_label = st.selectbox("Matching customer advances", options)
            selected_row = filtered_rows[options.index(selected_label)]

            st.warning(f"Are you sure you want to delete the customer advance for {selected_row[2]} on {selected_row[5]}?")
            with st.form("delete_customer_advance_form"):
                if st.form_submit_button("Delete This Advance"):
                    delete_customer_advance(selected_row[0])
                    st.success("Customer advance deleted")
                    st.rerun()

        st.markdown("### Customer Advance List")
        _render_advance_table(
            get_customer_advances(),
            ["Advance ID", "Customer Phone", "Customer Name", "Company Name", "Paid To", "Advance Date", "Amount Paid", "Payment Mode", "Transaction Details", "Remarks", "Linked Company Advance ID"],
            "customer_advances_filter",
        )


def _render_customer_outstanding():
    st.subheader("Customer outstanding", icon=":material/account_balance_wallet:")
    selected_action = action_control("customer_outstanding_action_mode", ["Add", "Edit", "Delete"], "Add")

    with st.container():
        customers = get_customers()

        if selected_action == "Add":
            if not customers:
                st.info("No customers are available. Add a customer before entering outstanding values.")
                return

            with st.form("add_customer_outstanding_form", clear_on_submit=True):
                customer = st.selectbox("Customer", [f"{row[1]} ({row[0]})" for row in customers])
                customer_phone = next((row[0] for row in customers if f"{row[1]} ({row[0]})" == customer), customers[0][0])
                customer_name = next((row[1] for row in customers if row[0] == customer_phone), "")
                month_start = st.date_input("Month Start")
                outstanding_amount = st.number_input("Outstanding Amount", min_value=0.0, step=0.01, format="%.2f")
                remarks = st.text_input("Remarks")

                submitted = st.form_submit_button("Save Outstanding")
                if submitted:
                    try:
                        add_customer_outstanding(customer_phone, customer_name, month_start, outstanding_amount, remarks)
                        st.success("Customer outstanding saved successfully")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

        elif selected_action == "Edit":
            rows = get_customer_outstanding()
            if not rows:
                st.info("No customer outstanding entries found.")
                return

            search_term = st.text_input("Search by customer or month", placeholder="Type customer name or month")
            if search_term.strip() == "":
                st.info("Enter a customer name or month to search")
                return

            filtered_rows = [
                row for row in rows
                if str(row[1]).lower().find(search_term.lower()) != -1
                or str(row[2]).lower().find(search_term.lower()) != -1
                or str(row[3]).lower().find(search_term.lower()) != -1
            ]
            if not filtered_rows:
                st.info("No matching outstanding entry found.")
                return

            options = [f"{row[2]} ({row[1]}) - {row[3]} - ₹{float(row[4] or 0):,.2f}" for row in filtered_rows]
            selected_label = st.selectbox("Matching outstanding entries", options)
            selected_row = filtered_rows[options.index(selected_label)]
            selected_id = selected_row[0]

            with st.form("edit_customer_outstanding_form"):
                customer = st.selectbox("Customer", [f"{row[1]} ({row[0]})" for row in customers], index=[f"{row[1]} ({row[0]})" for row in customers].index(f"{selected_row[2]} ({selected_row[1]})") if f"{selected_row[2]} ({selected_row[1]})" in [f"{row[1]} ({row[0]})" for row in customers] else 0)
                customer_phone = next((row[0] for row in customers if f"{row[1]} ({row[0]})" == customer), customers[0][0])
                customer_name = next((row[1] for row in customers if row[0] == customer_phone), "")
                month_start = st.date_input("Month Start", value=datetime.strptime(selected_row[3], "%Y-%m-%d").date())
                outstanding_amount = st.number_input("Outstanding Amount", min_value=0.0, step=0.01, format="%.2f", value=float(selected_row[4] or 0))
                remarks = st.text_input("Remarks", value=str(selected_row[5] or ""))

                submitted = st.form_submit_button("Update Outstanding")
                if submitted:
                    try:
                        update_customer_outstanding(selected_id, customer_phone, customer_name, month_start, outstanding_amount, remarks)
                        st.success("Customer outstanding updated successfully")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

        elif selected_action == "Delete":
            rows = get_customer_outstanding()
            if not rows:
                st.info("No customer outstanding entries found.")
                return

            search_term = st.text_input("Search by customer or month", placeholder="Type customer name or month")
            if search_term.strip() == "":
                st.info("Enter a customer name or month to search")
                return

            filtered_rows = [
                row for row in rows
                if str(row[1]).lower().find(search_term.lower()) != -1
                or str(row[2]).lower().find(search_term.lower()) != -1
                or str(row[3]).lower().find(search_term.lower()) != -1
            ]
            if not filtered_rows:
                st.info("No matching outstanding entry found.")
                return

            options = [f"{row[2]} ({row[1]}) - {row[3]} - ₹{float(row[4] or 0):,.2f}" for row in filtered_rows]
            selected_label = st.selectbox("Matching outstanding entries", options)
            selected_row = filtered_rows[options.index(selected_label)]

            st.warning(f"Are you sure you want to delete the outstanding entry for {selected_row[2]} for {selected_row[3]}?")
            with st.form("delete_customer_outstanding_form"):
                if st.form_submit_button("Delete This Outstanding"):
                    delete_customer_outstanding(selected_row[0])
                    st.success("Outstanding entry deleted")
                    st.rerun()

        st.markdown("### Customer Outstanding List")
        rows = get_customer_outstanding()
        if not rows:
            st.info("No customer outstanding entries available.")
            return

        st.dataframe(
            [
                {
                    "Outstanding ID": row[0],
                    "Customer Phone": row[1],
                    "Customer Name": row[2],
                    "Month Start": row[3],
                    "Outstanding Amount": float(row[4] or 0),
                    "Remarks": row[5],
                }
                for row in rows
            ],
            width="stretch",
            hide_index=True,
        )


def _render_customer_report():
    st.subheader("Customer Report")
    rows = get_customer_report()
    if not rows:
        st.info("No customer data available to report.")
        return

    st.dataframe(
        [
            {
                "Customer Phone": row[0],
                "Customer Name": row[1],
                "Outstanding Entries (Net)": float(row[2] or 0),
                "Sales Outstanding": float(row[3] or 0),
                "Customer Advances (Credit)": float(row[4] or 0),
                "Warranty Claims (Credit)": float(row[5] or 0),
                "Total Outstanding": float(row[6] or 0),
            }
            for row in rows
        ],
        width="stretch",
        hide_index=True,
    )


def advances_page(menu_name="Company Advances"):
    st.header("Advances")
    if menu_name == "Company Advances":
        _render_company_advances()
    elif menu_name == "Customer Outstanding":
        _render_customer_outstanding()
    elif menu_name == "Customer Report":
        _render_customer_report()
    else:
        _render_customer_advances()
