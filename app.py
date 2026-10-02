import streamlit as st

from database import initialize_database
from modules.customers import customer_page
from modules.ui import show_flash_message

initialize_database()

st.set_page_config(
    page_title="Vishwa Rock Drills",
    page_icon=":material/construction:",
    layout="wide"
)

st.title("Vishwa Rock Drills", icon=":material/construction:")
show_flash_message()

from database import get_connection_string
_active_db = get_connection_string()
if _active_db.startswith("sqlite"):
    st.sidebar.warning("⚠️ Using Local SQLite (No Supabase URL found in Secrets)")
else:
    st.sidebar.success("☁️ Supabase PostgreSQL Connected")

st.sidebar.markdown("### Workspace")
main_menu_items = [
    ("Dashboard", "dashboard"),
    ("Customers", "groups"),
    ("Inventory", "inventory_2"),
    ("Purchase Details", "receipt_long"),
    ("Sales", "point_of_sale"),
    ("Advances", "account_balance_wallet"),
    ("Reports", "summarize"),
    ("Warranty-Claims", "verified_user"),
]

if "menu" not in st.session_state:
    st.session_state.menu = "Dashboard"
if "inventory_submenu" not in st.session_state:
    st.session_state.inventory_submenu = "Partnership with"
if "advances_submenu" not in st.session_state:
    st.session_state.advances_submenu = "Company Advances"

for item, icon in main_menu_items:
    if st.sidebar.button(
        item,
        key=f"nav_{item}",
        icon=f":material/{icon}:",
        type="primary" if item == st.session_state.menu else "secondary",
        width="stretch",
    ):
        st.session_state.menu = item

menu = st.session_state.menu

if menu == "Dashboard":
    st.header("Dashboard", icon=":material/dashboard:")
    st.caption("Quick access")
    dashboard_links = [
        ("Customer Advances", "payments", "Advances", "Customer Advances"),
        ("Customer Outstanding", "account_balance_wallet", "Advances", "Customer Outstanding"),
        ("Sales", "point_of_sale", "Sales", None),
        ("Reports", "summarize", "Reports", None),
        ("Warranty Claims", "verified_user", "Warranty-Claims", None),
    ]
    for row_start in range(0, len(dashboard_links), 3):
        shortcut_columns = st.columns(3)
        for column, (label, icon, target_menu, target_submenu) in zip(
            shortcut_columns,
            dashboard_links[row_start:row_start + 3],
        ):
            with column:
                if st.button(
                    label,
                    key=f"dashboard_shortcut_{label}",
                    icon=f":material/{icon}:",
                    type="secondary",
                    width="stretch",
                ):
                    st.session_state.menu = target_menu
                    if target_submenu:
                        st.session_state.advances_submenu = target_submenu
                    st.rerun()

elif menu == "Customers":
    customer_page()

elif menu == "Inventory":
    content_col, action_col = st.columns([4, 1.5])

    with content_col:
        inventory_menu = st.session_state.inventory_submenu
        if inventory_menu == "Partnership with":
            from modules.partnerships import partnership_page
            partnership_page()
        elif inventory_menu == "Products":
            from modules.products import product_page
            product_page()

    with action_col:
        st.markdown("#### Inventory")
        for item, icon in [("Partnership with", "handshake"), ("Products", "category")]:
            if st.button(
                item,
                key=f"inventory_{item}",
                icon=f":material/{icon}:",
                type="primary" if item == st.session_state.inventory_submenu else "secondary",
                width="stretch",
            ):
                st.session_state.inventory_submenu = item

elif menu == "Purchase Details":
    from modules.inventory import inventory_tracking_page
    inventory_tracking_page()

elif menu == "Sales":
    from modules.sales import sales_page
    sales_page()

elif menu == "Advances":
    content_col, action_col = st.columns([4, 1.7])

    with content_col:
        advances_menu = st.session_state.advances_submenu
        from modules.advances import advances_page
        advances_page(advances_menu)

    with action_col:
        st.markdown("#### Advances")
        advance_menu_items = [
            ("Company Advances", "account_balance"),
            ("Customer Advances", "payments"),
            ("Customer Outstanding", "account_balance_wallet"),
            ("Customer Report", "query_stats"),
        ]
        for item, icon in advance_menu_items:
            if st.button(
                item,
                key=f"advances_{item}",
                icon=f":material/{icon}:",
                type="primary" if item == st.session_state.advances_submenu else "secondary",
                width="stretch",
            ):
                st.session_state.advances_submenu = item

elif menu == "Warranty-Claims":
    from modules.warranties import warranty_page
    warranty_page()

elif menu == "Reports":
    from modules.reports import customer_reports_page
    customer_reports_page()