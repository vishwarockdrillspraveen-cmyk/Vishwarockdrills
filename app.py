import streamlit as st

from database import initialize_database
from modules.customers import customer_page

initialize_database()

st.set_page_config(
    page_title="Vishwa Rock Drills",
    page_icon="🛠️",
    layout="wide"
)

st.markdown(
    """
    <style>
    :root {
        --bg: #0f172a;
        --panel: #111827;
        --panel-2: #1f2937;
        --primary: #f59e0b;
        --primary-soft: #fbbf24;
        --text: #f8fafc;
        --muted: #cbd5e1;
        --border: rgba(255,255,255,0.08);
    }

    .stApp {
        background: linear-gradient(135deg, #0b1120 0%, #111827 100%);
        color: var(--text);
    }

    .stApp > div {
        background: transparent;
    }

    h1, h2, h3, h4, h5, h6 {
        color: var(--primary-soft) !important;
    }

    .stSidebar {
        background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
        border-right: 1px solid var(--border);
    }

    .stSidebar .block-container {
        padding-top: 1rem;
    }

    .stButton > button {
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-soft) 100%);
        color: #111827;
        border: none;
        border-radius: 0.75rem;
        font-weight: 700;
        transition: 0.2s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 18px rgba(245, 158, 11, 0.25);
    }

    div[data-testid="stForm"] {
        background: rgba(17, 24, 39, 0.8);
        border: 1px solid var(--border);
        border-radius: 1rem;
        padding: 1rem;
    }

    .stDataFrame, .stTable {
        border-radius: 0.75rem;
        overflow: hidden;
    }

    [data-testid="stMetric"] {
        background: rgba(31, 41, 55, 0.9);
        border: 1px solid var(--border);
        border-radius: 0.75rem;
    }

    .stAlert, .stSuccess, .stInfo, .stWarning, .stError {
        border-radius: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
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