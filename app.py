import streamlit as st

from database import initialize_database
from modules.customers import customer_page

initialize_database()

st.set_page_config(
    page_title="Vishwa Rock Drills",
    page_icon="🛠️",
    layout="wide"
)

st.title("Vishwa Rock Drills")

st.sidebar.markdown("### Menu")
main_menu_items = [
    "Dashboard",
    "Customers",
    "Inventory",
    "Purchase Details",
    "Sales",
    "Advances",
    "Warranties"
]

if "menu" not in st.session_state:
    st.session_state.menu = "Dashboard"
if "inventory_submenu" not in st.session_state:
    st.session_state.inventory_submenu = "Partnership with"
if "advances_submenu" not in st.session_state:
    st.session_state.advances_submenu = "Company Advances"

for item in main_menu_items:
    if st.sidebar.button(item, key=f"nav_{item}", width="stretch"):
        st.session_state.menu = item

menu = st.session_state.menu

if menu == "Dashboard":
    st.header("Dashboard")
    st.write("Coming Soon")

elif menu == "Customers":
    customer_page()

elif menu == "Inventory":
    action_col, content_col = st.columns([1.5, 4])

    with action_col:
        st.markdown("#### Inventory")
        for item in ["Partnership with", "Products"]:
            if st.button(item, key=f"inventory_{item}", use_container_width=True):
                st.session_state.inventory_submenu = item

    with content_col:
        inventory_menu = st.session_state.inventory_submenu

        if inventory_menu == "Partnership with":
            from modules.partnerships import partnership_page
            partnership_page()
        elif inventory_menu == "Products":
            from modules.products import product_page
            product_page()
elif menu == "Purchase Details":
    from modules.inventory import inventory_tracking_page
    inventory_tracking_page()

elif menu == "Sales":
    from modules.sales import sales_page
    sales_page()

elif menu == "Advances":
    action_col, content_col = st.columns([1.5, 4])

    with action_col:
        st.markdown("#### Advances")
        for item in ["Company Advances", "Customer Advances"]:
            if st.button(item, key=f"advances_{item}", use_container_width=True):
                st.session_state.advances_submenu = item

    with content_col:
        advances_menu = st.session_state.advances_submenu
        from modules.advances import advances_page
        advances_page(advances_menu)

elif menu == "Warranties":
    from modules.warranties import warranty_page
    warranty_page()