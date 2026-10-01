import streamlit as st

from database import (
    add_product,
    delete_product,
    get_companies,
    get_products,
    update_product,
)
from modules.ui import action_control


def product_page():
    st.header("Products", icon=":material/category:")
    st.caption("Maintain product specifications, warranty limits, and sale prices.")
    selected_action = action_control("product_action_mode", ["Add", "Edit", "Delete"], "Add")

    product_rows = get_products()
    if product_rows:
        st.subheader("Product list")
        product_search = st.text_input(
            "Filter products",
            placeholder="Search by product, company, or ID",
            icon=":material/search:",
            key="product_list_search",
        )
        visible_products = [
            row for row in product_rows
            if product_search.strip().lower() in " ".join(str(value or "") for value in row[:3]).lower()
        ]
        st.dataframe(
            [
                {
                    "Product ID": row[0],
                    "Company": row[1],
                    "Product name": row[2],
                    "Sold by": row[3],
                    "Type": row[4],
                    "Actual size (mm)": row[5],
                    "Under warranty": "Yes" if row[6] else "No",
                    "Warranty limit (mm)": row[7],
                    "Sale price": row[8],
                }
                for row in visible_products
            ],
            width="stretch",
            hide_index=True,
        )

    if selected_action == "Add":
            st.subheader("Add product")
            company_rows = get_companies()
            if not company_rows:
                st.info("No partnership companies available. Add a company in Partnership with first.")
                return

            with st.form("add_product_form", clear_on_submit=True):
                company_options = [company[1] for company in company_rows]
                company_name = st.selectbox(
                    "Procured From Company",
                    options=company_options,
                    index=0
                )

                product_name = st.text_input("Product Name")
                sold_by_product_name = st.text_input("Sold by Product Name")
                product_type = st.selectbox(
                    "Type",
                    ["Normal", "Special", "Drilling"]
                )
                actual_size_mm = st.number_input("Actual Size (mm)", min_value=0.0, step=0.1, format="%.1f", value=0.0)
                under_warranty = st.selectbox("Under Warranty", ["Yes", "No"])
                warranty_limit_mm = st.number_input(
                    "Warranty Limit (mm)",
                    min_value=0,
                    step=1,
                    value=0
                )
                sale_price = st.number_input(
                    "Sale Price",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    value=0.0
                )

                submitted = st.form_submit_button("Save product", type="primary", icon=":material/add:")

                if submitted:
                    final_company = company_name.strip()
                    if final_company == "":
                        st.error("Company name is required")
                    elif product_name.strip() == "":
                        st.error("Product name is required")
                    else:
                        add_product(
                            final_company,
                            product_name.strip(),
                            sold_by_product_name.strip(),
                            product_type,
                            str(actual_size_mm),
                            under_warranty == "Yes",
                            warranty_limit_mm,
                            sale_price
                        )
                        st.success("Product Saved Successfully")
                        st.rerun()
    elif selected_action == "Edit":
            st.subheader("Edit product")
            products = get_products()

            if not products:
                st.info("No products available to edit")
                return

            search_term = st.text_input("Find a product", placeholder="Search by company or product name", icon=":material/search:")

            if search_term.strip() == "":
                st.info("Enter a company or product name to search")
                return

            filtered_products = [
                row for row in products
                if str(row[1]).lower().find(search_term.lower()) != -1
                or str(row[2]).lower().find(search_term.lower()) != -1
            ]

            if not filtered_products:
                st.info("No matching product found")
                return

            product_options = [f"{row[2]} ({row[1]})" for row in filtered_products]
            selected_product_label = st.selectbox("Matching product", product_options)
            selected_row = filtered_products[product_options.index(selected_product_label)]
            selected_product_id = selected_row[0]

            with st.form("edit_product_form"):
                company_rows = get_companies()
                company_options = [company[1] for company in company_rows]
                company_index = company_options.index(selected_row[1]) if selected_row[1] in company_options else 0
                edited_company_name = st.selectbox(
                    "Procured From Company",
                    options=company_options,
                    index=company_index
                )
                edited_product_name = st.text_input("Product Name", value=selected_row[2])
                edited_sold_by_product_name = st.text_input("Sold by Product Name", value=selected_row[3] or "")
                edited_product_type = st.selectbox(
                    "Type",
                    ["Normal", "Special", "Drilling"],
                    index=["Normal", "Special", "Drilling"].index(selected_row[4])
                )
                edited_diameter = st.number_input("Actual Size (mm)", min_value=0.0, step=0.1, format="%.1f", value=float(selected_row[5] or 0))
                edited_under_warranty = st.selectbox(
                    "Under Warranty",
                    ["Yes", "No"],
                    index=0 if selected_row[6] == 1 else 1
                )
                edited_warranty_limit_mm = st.number_input(
                    "Warranty Limit (mm)",
                    min_value=0,
                    step=1,
                    value=int(selected_row[7] or 0)
                )
                edited_sale_price = st.number_input(
                    "Sale Price",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    value=float(selected_row[8] or 0)
                )

                update_submitted = st.form_submit_button("Save changes", type="primary", icon=":material/save:")
                if update_submitted:
                    if edited_company_name.strip() == "" or edited_product_name.strip() == "":
                        st.error("Company name and product name are required")
                    else:
                        update_product(
                            selected_product_id,
                            edited_company_name.strip(),
                            edited_product_name.strip(),
                            edited_sold_by_product_name.strip(),
                            edited_product_type,
                            str(edited_diameter),
                            edited_under_warranty == "Yes",
                            edited_warranty_limit_mm,
                            edited_sale_price
                        )
                        st.success("Product updated successfully")
                        st.rerun()

    elif selected_action == "Delete":
            st.subheader("Delete product")
            products = get_products()

            if not products:
                st.info("No products available to delete")
                return

            search_term = st.text_input("Find a product", placeholder="Search by company or product name", icon=":material/search:")

            if search_term.strip() == "":
                st.info("Enter a company or product name to search")
                return

            filtered_products = [
                row for row in products
                if str(row[1]).lower().find(search_term.lower()) != -1
                or str(row[2]).lower().find(search_term.lower()) != -1
            ]

            if not filtered_products:
                st.info("No matching product found")
                return

            product_options = [f"{row[2]} ({row[1]})" for row in filtered_products]
            selected_product_label = st.selectbox("Matching product", product_options)
            selected_row = filtered_products[product_options.index(selected_product_label)]
            selected_product_id = selected_row[0]

            st.warning(f"Confirm deletion of {selected_row[2]} ({selected_row[1]})?")
            with st.form("delete_product_form"):
                delete_submitted = st.form_submit_button("Delete product", type="primary", icon=":material/delete:")
                if delete_submitted:
                    delete_product(selected_product_id)
                    st.success("Product Deleted")
                    st.rerun()
