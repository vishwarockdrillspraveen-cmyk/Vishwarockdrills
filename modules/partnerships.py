import streamlit as st

from database import add_company, delete_company, get_companies, update_company
from modules.ui import action_control


def partnership_page():
    st.header("Partnership with", icon=":material/handshake:")
    st.caption("Manage the companies linked to your product catalogue.")
    selected_action = action_control("partnership_action_mode", ["Add", "Edit", "Delete"], "Add")

    companies = get_companies()
    st.subheader("Company list")
    if companies:
        company_search = st.text_input(
            "Filter companies",
            placeholder="Search by company name",
            icon=":material/search:",
            key="partnership_company_search",
        )
        visible_companies = [
            row for row in companies
            if company_search.strip().lower() in str(row[1]).lower()
        ]
        st.dataframe(
            [{"Company ID": row[0], "Company name": row[1]} for row in visible_companies],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("No companies have been added yet.")

    if selected_action == "Add":
            st.subheader("Add company")
            with st.form("add_company_form", clear_on_submit=True):
                company_name = st.text_input("Company name", placeholder="Enter company name")
                submitted = st.form_submit_button("Save company", type="primary", icon=":material/add_business:")

                if submitted:
                    cleaned_name = company_name.strip()
                    if cleaned_name == "":
                        st.error("Company name is required")
                    else:
                        company_id = add_company(cleaned_name)
                        if company_id is None:
                            st.warning("This company already exists")
                        else:
                            st.success(f"{cleaned_name} saved successfully")
                            st.rerun()

    elif selected_action == "Edit":
            st.subheader("Edit company")
            companies = get_companies()

            if not companies:
                st.info("No companies available to edit")
                return

            search_term = st.text_input("Find a company", placeholder="Search by company name", icon=":material/search:")

            if search_term.strip() == "":
                st.info("Enter a company name to search")
                return

            filtered_companies = [
                row for row in companies
                if str(row[1]).lower().find(search_term.lower()) != -1
            ]

            if not filtered_companies:
                st.info("No matching company found")
                return

            company_options = [f"{row[1]}" for row in filtered_companies]
            selected_company_label = st.selectbox("Matching company", company_options)
            selected_row = filtered_companies[company_options.index(selected_company_label)]
            selected_company_id = selected_row[0]

            with st.form("edit_company_form"):
                edited_company_name = st.text_input(
                    "Company Name",
                    value=selected_row[1]
                )
                st.caption(f"Company ID: {selected_company_id}")

                submit = st.form_submit_button("Save changes", type="primary", icon=":material/save:")
                if submit:
                    if edited_company_name.strip() == "":
                        st.error("Company name is required")
                    else:
                        update_company(selected_company_id, edited_company_name)
                        st.success("Company updated successfully")
                        st.rerun()

    elif selected_action == "Delete":
            st.subheader("Delete company")
            companies = get_companies()

            if not companies:
                st.info("No companies available to delete")
                return

            search_term = st.text_input("Find a company", placeholder="Search by company name", icon=":material/search:")

            if search_term.strip() == "":
                st.info("Enter a company name to search")
                return

            filtered_companies = [
                row for row in companies
                if str(row[1]).lower().find(search_term.lower()) != -1
            ]

            if not filtered_companies:
                st.info("No matching company found")
                return

            company_options = [f"{row[1]}" for row in filtered_companies]
            selected_company_label = st.selectbox("Matching company", company_options)
            selected_row = filtered_companies[company_options.index(selected_company_label)]
            selected_company_id = selected_row[0]

            st.warning(f"Confirm deletion of {selected_row[1]}?")
            with st.form("delete_company_form"):
                delete_submitted = st.form_submit_button("Delete company", type="primary", icon=":material/delete:")
                if delete_submitted:
                    deleted = delete_company(selected_company_id)
                    if deleted:
                        st.success("Company Deleted")
                        st.rerun()
                    else:
                        st.error("This company cannot be deleted because it is linked to one or more products.")
