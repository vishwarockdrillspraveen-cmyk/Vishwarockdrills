import streamlit as st
from datetime import datetime

from database import add_warranty_claim, delete_warranty_claim, get_products, get_warranty_claims


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
    st.header("Warranty claims", icon=":material/verified_user:")
    st.caption("Assess product wear and track eligible warranty returns.")

    products = get_products()
    if not products:
        st.info("No products are available. Add a product in Product Management before processing warranty claims.")
        return

    product_options = {
        f"{row[2]} ({row[1]}) | ID: {row[0]}": row
        for row in products
    }
    product_labels = list(product_options)
    selected_product_label = st.selectbox(
        "Select product",
        product_labels,
        key="warranty_selected_product",
    )
    master_row = product_options[selected_product_label]

    product_id = master_row[0]
    product_name = master_row[2]
    company_name = master_row[1]
    sale_price = float(master_row[8] or 0)
    initial_mm = float(str(master_row[5] or 0).strip() or 0)
    warranty_limit_mm = float(master_row[7] or 0)

    with st.container(border=True):
        detail_col1, detail_col2, detail_col3 = st.columns(3)
        with detail_col1:
            st.metric("Product ID", str(master_row[0]))
            st.metric("Sold by", str(master_row[3] or "-"))
            st.metric("Sale price", f"{sale_price:,.2f}")
        with detail_col2:
            st.metric("Product name", str(master_row[2]))
            st.metric("Product type", str(master_row[4] or "-"))
            st.metric("Initial size", f"{initial_mm:.1f} mm")
        with detail_col3:
            st.metric("Company", company_name)
            st.metric("Warranty coverage", "Yes" if master_row[6] else "No")
            st.metric("Warranty limit", f"{warranty_limit_mm:.1f} mm")

    current_mm = st.number_input("Current size (mm)", min_value=0.0, step=0.1, format="%.1f", key="warranty_current_mm")
    claim_date = st.date_input("Claim date", value=datetime.today().date(), key="warranty_claim_date")

    current_mm = float(st.session_state.get("warranty_current_mm", 0.0) or 0.0)
    live_claim_value = _calculate_warranty_value(
        float(master_row[8] or 0),
        float(str(master_row[5] or 0).strip() or 0),
        current_mm,
        float(master_row[7] or 0),
    )
    st.metric("Estimated amount to return", f"{live_claim_value:,.2f}")

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

    if st.button("Save warranty claim", type="primary", icon=":material/save:"):
        if product_name.strip() == "":
            st.error("Product is required.")
        else:
            try:
                claim_id = add_warranty_claim(
                    product_id=product_id,
                    product_name=product_name,
                    company_name=company_name,
                    initial_mm=initial_mm,
                    current_mm=current_mm,
                    sale_price=sale_price,
                    warranty_limit_mm=warranty_limit_mm,
                    warranty_value=live_claim_value,
                    claim_date=claim_date,
                )
                st.success(f"Warranty claim saved successfully. Claim ID: {claim_id}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

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
        width="stretch",
        hide_index=True,
    )

    st.subheader("Delete a claim")
    claim_options = [
        f"#{row[0]} - {row[2]} ({row[3]}) - ₹{float(row[8] or 0):,.2f}"
        for row in claims
    ]
    selected_claim_label = st.selectbox("Select claim to delete", claim_options)
    selected_claim_id = claims[claim_options.index(selected_claim_label)][0]

    if st.button("Delete selected claim", type="secondary", icon=":material/delete:"):
        deleted = delete_warranty_claim(selected_claim_id)
        if deleted:
            st.success(f"Warranty claim #{selected_claim_id} deleted successfully.")
            st.rerun()
        else:
            st.error("Unable to delete this warranty claim.")
