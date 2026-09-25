import streamlit as st
from datetime import datetime

from database import add_warranty_claim, delete_warranty_claim, get_inventory_products_for_sale, get_products, get_warranty_claims


def _calculate_warranty_value(sale_price, initial_mm, current_mm, warranty_limit_mm):
    sale_price = float(sale_price or 0)
    initial_mm = float(initial_mm or 0)
    current_mm = float(current_mm or 0)
    warranty_limit_mm = float(warranty_limit_mm or 0)

    if sale_price <= 0 or warranty_limit_mm <= 0:
        return 0.0

    if current_mm >= initial_mm:
        return 0.0

    wear_used_mm = max(initial_mm - current_mm, 0)
    if wear_used_mm <= 0:
        return 0.0

    amount_per_mm = sale_price / warranty_limit_mm
    return max(0.0, sale_price - (amount_per_mm * wear_used_mm))


def warranty_page():
    st.header("Warranty Management")

    inventory_products = get_inventory_products_for_sale()
    if not inventory_products:
        st.info("No products are available in inventory. Add product inventory first before processing warranty claims.")
        return

    products = get_products()
    product_lookup = {str(row[0]): row for row in products}

    product_options = [f"{row[1]} ({row[2]})" for row in inventory_products]
    selected_product_label = st.session_state.get("warranty_selected_product", product_options[0] if product_options else "")
    selected_inventory_row = next((row for row in inventory_products if f"{row[1]} ({row[2]})" == selected_product_label), inventory_products[0] if inventory_products else None)

    if selected_inventory_row is None:
        st.info("No products available in inventory.")
        return

    master_row = product_lookup.get(str(selected_inventory_row[0]), None)
    if master_row is None:
        st.warning("This product is in inventory but not present in the product master list. Please verify the product record.")
        return

    with st.form("warranty_claim_form", clear_on_submit=True):
        current_product_label = st.selectbox("Select Product", product_options, key="warranty_selected_product")
        selected_inventory_row = next((row for row in inventory_products if f"{row[1]} ({row[2]})" == current_product_label), inventory_products[0])
        master_row = product_lookup.get(str(selected_inventory_row[0]), products[0])

        product_id = selected_inventory_row[0]
        product_name = selected_inventory_row[1]
        company_name = selected_inventory_row[2]
        sale_price = float(master_row[8] or 0)
        initial_mm = float(str(master_row[5] or 0).strip() or 0)
        warranty_limit_mm = float(master_row[7] or 0)

        st.text_input("Product Company", value=company_name, disabled=True)
        st.text_input("Product Price", value=f"{sale_price:,.2f}", disabled=True)
        st.text_input("Initial mm", value=f"{initial_mm:.1f}", disabled=True)

        current_mm = st.number_input("Current mm available now", min_value=0.0, step=0.1, format="%.1f", key="warranty_current_mm")
        claim_date = st.date_input("Claim Date", value=datetime.today().date(), key="warranty_claim_date")
        submitted = st.form_submit_button("Save Warranty Claim")

        if submitted:
            if product_name.strip() == "":
                st.error("Product is required.")
            else:
                try:
                    claim_value = _calculate_warranty_value(sale_price, initial_mm, current_mm, warranty_limit_mm)
                    claim_id = add_warranty_claim(
                        product_id=product_id,
                        product_name=product_name,
                        company_name=company_name,
                        initial_mm=initial_mm,
                        current_mm=current_mm,
                        sale_price=sale_price,
                        warranty_limit_mm=warranty_limit_mm,
                        warranty_value=claim_value,
                        claim_date=claim_date,
                    )
                    st.success(f"Warranty claim saved successfully. Claim ID: {claim_id}")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    current_mm = float(st.session_state.get("warranty_current_mm", 0.0) or 0.0)
    live_claim_value = _calculate_warranty_value(
        float(master_row[8] or 0),
        float(str(master_row[5] or 0).strip() or 0),
        current_mm,
        float(master_row[7] or 0),
    )
    st.markdown(f"### Warranty Amount to Return: {live_claim_value:,.2f}")

    if current_mm < float(str(master_row[5] or 0).strip() or 0) and float(master_row[7] or 0) > 0:
        amount_per_mm = float(master_row[8] or 0) / float(master_row[7] or 0)
        wear_used_mm = max(float(str(master_row[5] or 0).strip() or 0) - current_mm, 0)
        st.caption(
            f"Deduction rule: ₹{amount_per_mm:,.2f} per mm. "
            f"Wear used: {wear_used_mm:.1f} mm. Amount refunded: ₹{live_claim_value:,.2f}"
        )
    elif current_mm >= float(str(master_row[5] or 0).strip() or 0):
        st.caption("Current mm is at or above the initial size, so no warranty amount is due.")
    else:
        st.caption("This product does not have a valid warranty limit configured.")

    st.markdown("### Warranty Claims History")
    claims = get_warranty_claims()
    if not claims:
        st.info("No warranty claims saved yet.")
        return

    st.dataframe(
        [
            {
                "Claim ID": row[0],
                "Product ID": row[1],
                "Product": row[2],
                "Company": row[3],
                "Initial mm": row[4],
                "Current mm": row[5],
                "Sale Price": row[6],
                "Warranty Limit mm": row[7],
                "Amount Returned": row[8],
                "Claim Date": row[9],
            }
            for row in claims
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Delete Warranty Claim")
    claim_options = [
        f"#{row[0]} - {row[2]} ({row[3]}) - ₹{float(row[8] or 0):,.2f}"
        for row in claims
    ]
    selected_claim_label = st.selectbox("Select claim to delete", claim_options)
    selected_claim_id = claims[claim_options.index(selected_claim_label)][0]

    with st.form("delete_warranty_claim_form"):
        delete_submitted = st.form_submit_button("Delete This Warranty Claim")
        if delete_submitted:
            deleted = delete_warranty_claim(selected_claim_id)
            if deleted:
                st.success(f"Warranty claim #{selected_claim_id} deleted successfully.")
                st.rerun()
            else:
                st.error("Unable to delete this warranty claim.")
