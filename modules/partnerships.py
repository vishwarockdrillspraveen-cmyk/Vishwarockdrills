import streamlit as st

from database import add_company, delete_company, get_companies, update_company


def partnership_page():
    st.header("Partnership with")

    if "partnership_action" not in st.session_state:
        st.session_state.partnership_action = "Add Company"

    menu_options = ["Add Company", "Edit Company", "Delete Company"]
    action_col, content_col = st.columns([1.5, 4])

    with action_col:
        st.markdown("#### Companies")
        for option in menu_options:
            if st.button(option, key=f"partnership_action_{option}", use_container_width=True):
                st.session_state.partnership_action = option

    with content_col:
        selected_action = st.session_state.partnership_action

        st.subheader("Companies")
        companies = get_companies()
        if companies:
            st.dataframe(
                [{"Company ID": row[0], "Company Name": row[1]} for row in companies],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No companies available yet.")

        if selected_action == "Add Company":
            st.subheader("Add Company")
            with st.form("add_company_form", clear_on_submit=True):
                company_name = st.text_input("Company Name", placeholder="Enter company name")
                submitted = st.form_submit_button("Save Company")

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

        elif selected_action == "Edit Company":
            st.subheader("Edit Company")
            companies = get_companies()

            if not companies:
                st.info("No companies available to edit")
                return

            search_term = st.text_input(
                "Search by company name",
                placeholder="Type a company name"
            )

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
            selected_company_label = st.selectbox("Matching companies", company_options)
            selected_row = filtered_companies[company_options.index(selected_company_label)]
            selected_company_id = selected_row[0]

            with st.form("edit_company_form"):
                edited_company_name = st.text_input(
                    "Company Name",
                    value=selected_row[1]
                )
                st.caption(f"Company ID: {selected_company_id}")

                submit = st.form_submit_button("Update Company")
                if submit:
                    if edited_company_name.strip() == "":
                        st.error("Company name is required")
                    else:
                        update_company(selected_company_id, edited_company_name)
                        st.success("Company Updated Successfully")
                        st.rerun()

        elif selected_action == "Delete Company":
            st.subheader("Delete Company")
            companies = get_companies()

            if not companies:
                st.info("No companies available to delete")
                return

            search_term = st.text_input(
                "Search by company name",
                placeholder="Type a company name"
            )

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
            selected_company_label = st.selectbox("Matching companies", company_options)
            selected_row = filtered_companies[company_options.index(selected_company_label)]
            selected_company_id = selected_row[0]

            st.warning(f"Are you sure you want to delete company: {selected_row[1]}?")
            with st.form("delete_company_form"):
                delete_submitted = st.form_submit_button("Delete This Company")
                if delete_submitted:
                    deleted = delete_company(selected_company_id)
                    if deleted:
                        st.success("Company Deleted")
                        st.rerun()
                    else:
                        st.error("This company cannot be deleted because it is linked to one or more products.")
