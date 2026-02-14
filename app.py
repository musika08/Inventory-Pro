import streamlit as st
import pandas as pd
import os
import shutil
from datetime import date, datetime

# --- PRE-FLIGHT CHECK ---
try:
    import plotly.express as px
except ImportError:
    st.error("Missing dependency: Plotly. Run 'pip install plotly'")
    st.stop()

# --- CONFIG & COMPACT CSS ---
st.set_page_config(page_title="Inventory Pro", layout="wide")

DB_FILE = "inventory_data.csv"
STOCK_FILE = "stock_data.csv"
SALES_FILE = "sales_data.csv"
EXPENSE_FILE = "expenditures.csv"
CASH_FILE = "cash_in.csv"
LOG_FILE = "activity_log.csv"
EXPENSE_COLS = ["Cost per Unit", "Boxed Cost"]

if not os.path.exists("backups"):
    os.makedirs("backups")

SALES_ORDER = ["Date", "Customer", "Product", "Qty", "Price Tier", "Cost", "Boxed Cost", "Profit", "Discount", "Total", "Status", "Payment"]

# --- DYNAMIC CSS (STRICT COMPACT SIDEBAR) ---
st.markdown(f"""
    <style>
    /* Global Font Size */
    html, body, [class*="ViewContainer"] {{ font-size: 12px !important; }}
    .block-container {{ padding: 1rem !important; }}
    
    /* Compact Sidebar Width */
    [data-testid="stSidebar"] {{
        min-width: 180px !important;
        max-width: 180px !important;
    }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }}

    /* Headers */
    h1 {{ display: block !important; font-size: 1.4rem !important; font-weight: 700 !important; margin-top: 1rem !important; margin-bottom: 1rem !important; color: #FFFFFF !important; }}
    
    /* Navigation Buttons Styling */
    .stButton > button {{ 
        width: 100% !important; 
        padding: 4px 10px !important; 
        text-align: left !important;
        font-size: 11px !important;
        border-radius: 4px !important;
        margin-bottom: -5px !important;
    }}
    
    /* Sidebar Title */
    [data-testid="stSidebar"] h2 {{
        font-size: 1.1rem !important;
        margin-bottom: 0.5rem !important;
    }}

    hr {{ border: none !important; height: 1px !important; background-color: #333 !important; display: block !important; margin: 8px 0 !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- DATA HELPERS ---
def log_action(action_desc):
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    new_log = pd.DataFrame({"Timestamp": [now], "Detailed Action": [action_desc]})
    if os.path.exists(LOG_FILE):
        try:
            log_df = pd.read_csv(LOG_FILE)
            log_df = pd.concat([new_log, log_df], ignore_index=True)
        except:
            log_df = new_log
    else:
        log_df = new_log
    log_df.to_csv(LOG_FILE, index=False)

def load_data(file, defaults):
    if os.path.exists(file):
        df = pd.read_csv(file)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors='coerce').dt.date
            df["Date"] = df["Date"].fillna(date.today())
        return df
    return pd.DataFrame(defaults)

def save_data(df, file):
    df.to_csv(file, index=False)

# --- INITIALIZATION ---
if 'inventory' not in st.session_state:
    st.session_state.inventory = load_data(DB_FILE, {"Product Name": ["Item 1"], "Cost per Unit": [0.0], "Boxed Cost": [0.0]})
if 'stock' not in st.session_state:
    st.session_state.stock = load_data(STOCK_FILE, {"Product Name": ["Item 1"], "Quantity": [0], "Status": ["In Stock"], "Date": [date.today()]})
if 'sales' not in st.session_state:
    st.session_state.sales = load_data(SALES_FILE, {c: [] for c in SALES_ORDER})
if 'expenditures' not in st.session_state:
    st.session_state.expenditures = load_data(EXPENSE_FILE, {"Date": [], "Item": [], "Cost": []})
if 'cash_in' not in st.session_state:
    st.session_state.cash_in = load_data(CASH_FILE, {"Date": [], "Source": [], "Amount": []})
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Dashboard"

db_df = st.session_state.inventory
product_list = db_df["Product Name"].dropna().unique().tolist()
all_numeric = [c for c in db_df.columns if c != "Product Name"]
price_tiers_list = [c for c in all_numeric if c not in EXPENSE_COLS]

# --- NAVIGATION ---
with st.sidebar:
    st.markdown("## 🚀 Menu")
    if st.button("📊 Dashboard"): st.session_state.current_page = "Dashboard"
    if st.button("📂 Database"): st.session_state.current_page = "Database"
    if st.button("📦 Inventory"): st.session_state.current_page = "Inventory"
    if st.button("💰 Sales"): st.session_state.current_page = "Sales"
    if st.button("💸 Expenditures"): st.session_state.current_page = "Expenditures"
    if st.button("📜 Activity Log"): st.session_state.current_page = "Log"

page = st.session_state.current_page

# --- PAGE LOGIC ---
if page == "Sales":
    st.markdown("<h1>💰 Sales Tracker</h1>", unsafe_allow_html=True)
    sales_df = st.session_state.sales.copy()
    sales_df["Date"] = pd.to_datetime(sales_df["Date"]).dt.date
    sales_config = {
        "Product": st.column_config.SelectboxColumn("Product", options=sorted(product_list), required=True),
        "Price Tier": st.column_config.SelectboxColumn("Price Tier", options=price_tiers_list, required=True),
        "Status": st.column_config.SelectboxColumn("Status", options=["Sold", "Reserved"], default="Sold", required=True),
        "Payment": st.column_config.SelectboxColumn("Payment", options=["Paid", "Unpaid"], default="Unpaid", required=True),
        "Cost": st.column_config.NumberColumn(disabled=True, format="₱%.2f"),
        "Boxed Cost": st.column_config.NumberColumn(disabled=True, format="₱%.2f"),
        "Profit": st.column_config.NumberColumn(disabled=True, format="₱%.2f"),
        "Total": st.column_config.NumberColumn(disabled=True, format="₱%.2f"),
        "Qty": st.column_config.NumberColumn("Qty", min_value=1, default=1),
        "Discount": st.column_config.NumberColumn("Discount", min_value=0.0, default=0.0, format="₱%.2f"),
    }
    edited_sales = st.data_editor(sales_df[SALES_ORDER], use_container_width=True, hide_index=True, num_rows="dynamic", column_config=sales_config, key="sales_editor")
    state = st.session_state["sales_editor"]
    if state["edited_rows"] or state["added_rows"] or state["deleted_rows"]:
        new_df = edited_sales.copy()
        for idx in new_df.index:
            row = new_df.loc[idx]
            match = db_df[db_df["Product Name"] == row["Product"]]
            if not match.empty:
                current_tier = str(row["Price Tier"])
                u_cost, b_cost = float(match["Cost per Unit"].values[0]), float(match["Boxed Cost"].values[0])
                tier_price = float(match[current_tier].values[0]) if current_tier in match.columns else 0.0
                qty, discount = float(row["Qty"]) if pd.notnull(row["Qty"]) else 1.0, float(row["Discount"]) if pd.notnull(row["Discount"]) else 0.0
                new_df.at[idx, "Cost"], new_df.at[idx, "Boxed Cost"] = u_cost, b_cost
                total_val = (tier_price - discount) * qty
                new_df.at[idx, "Total"], new_df.at[idx, "Profit"] = total_val, total_val - (b_cost * qty)
                old_row = st.session_state.sales.iloc[idx] if idx < len(st.session_state.sales) else None
                current_status = str(row["Status"])
                if old_row is None or str(old_row["Status"]) != current_status:
                    icon = "🟢 [SOLD]" if current_status == "Sold" else "🟡 [RESERVED]"
                    log_action(f"{icon} {int(qty)} units of '{row['Product']}' to Customer: {row['Customer']}")
                if current_status == "Sold" and (old_row is None or old_row["Status"] != "Sold"):
                    s_df, needed = st.session_state.stock, int(qty)
                    mask = (s_df["Product Name"] == row["Product"]) & (s_df["Status"] == "In Stock") & (s_df["Quantity"] > 0)
                    available_indices = s_df[mask].index.tolist()
                    for t_idx in available_indices:
                        if needed <= 0: break
                        available = s_df.at[t_idx, "Quantity"]
                        take = min(needed, available)
                        s_df.at[t_idx, "Quantity"] -= take
                        needed -= take
                    st.session_state.stock = s_df; save_data(s_df, STOCK_FILE)
        if state["deleted_rows"]: log_action("🔴 [REMOVED] Sales records deleted.")
        st.session_state.sales = new_df; save_data(new_df, SALES_FILE); st.rerun()

elif page == "Expenditures":
    st.markdown("<h1>💸 Cash Flow & Expenditures</h1>", unsafe_allow_html=True)
    m1, m2 = st.columns(2)
    e_total, d_total = st.session_state.expenditures['Cost'].sum(), st.session_state.cash_in['Amount'].sum()
    m1.metric("Total Expenses", f"₱{e_total:,.2f}"); m2.metric("Total Deposits", f"₱{d_total:,.2f}")
    st.write("### ➖ Log Expense")
    ex_row = st.columns([2, 1, 1, 0.4])
    ex_item, ex_cost = ex_row[0].text_input("Expense Item"), ex_row[1].number_input("Cost (₱)", min_value=0.0)
    if ex_row[3].button("➕", key="btn_add_ex"):
        new_ex = pd.DataFrame({"Date": [date.today()], "Item": [ex_item], "Cost": [ex_cost]})
        st.session_state.expenditures = pd.concat([st.session_state.expenditures, new_ex], ignore_index=True)
        save_data(st.session_state.expenditures, EXPENSE_FILE); log_action(f"💸 [EXPENSE] '{ex_item}' added for ₱{ex_cost:,.2f}"); st.rerun()
    st.write("### ➕ Log Deposit")
    in_row = st.columns([2, 1, 1, 0.4])
    in_source, in_amt = in_row[0].text_input("Source"), in_row[1].number_input("Amount (₱)", min_value=0.0)
    if in_row[3].button("➕", key="btn_add_in"):
        new_in = pd.DataFrame({"Date": [date.today()], "Source": [in_source], "Amount": [in_amt]})
        st.session_state.cash_in = pd.concat([st.session_state.cash_in, new_in], ignore_index=True)
        save_data(st.session_state.cash_in, CASH_FILE); log_action(f"💰 [DEPOSIT] Received ₱{in_amt:,.2f} from '{in_source}'"); st.rerun()
    l_c, r_c = st.columns(2)
    with l_c:
        st.write("Expense History")
        v_ex = st.session_state.expenditures.copy().iloc[::-1]
        ed_ex = st.data_editor(v_ex, use_container_width=True, hide_index=True, num_rows="dynamic", key="ed_ex_log")
        if not ed_ex.equals(v_ex): log_action("🧹 Expense Log adjusted."); st.session_state.expenditures = ed_ex.iloc[::-1]; save_data(st.session_state.expenditures, EXPENSE_FILE); st.rerun()
    with r_c:
        st.write("Deposit History")
        v_in = st.session_state.cash_in.copy().iloc[::-1]
        ed_in = st.data_editor(v_in, use_container_width=True, hide_index=True, num_rows="dynamic", key="ed_in_log")
        if not ed_in.equals(v_in): log_action("🧹 Deposit Log adjusted."); st.session_state.cash_in = ed_in.iloc[::-1]; save_data(st.session_state.cash_in, CASH_FILE); st.rerun()

elif page == "Log":
    st.markdown("<h1>📜 Activity Log & Backups</h1>", unsafe_allow_html=True)
    if st.button("🛡️ Create Data Backup"):
        backup_dir = f"backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"; os.makedirs(backup_dir, exist_ok=True)
        for f in [DB_FILE, STOCK_FILE, SALES_FILE, EXPENSE_FILE, CASH_FILE, LOG_FILE]:
            if os.path.exists(f): shutil.copy(f, backup_dir)
        log_action(f"🛡️ [BACKUP] Created at {backup_dir}"); st.success("Backup Successful.")
    if os.path.exists(LOG_FILE):
        st.dataframe(pd.read_csv(LOG_FILE), use_container_width=True, hide_index=True)
        if st.button("🗑️ Clear Log"): os.remove(LOG_FILE); log_action("⚠️ Log cleared."); st.rerun()

elif page == "Database":
    st.markdown("<h1>📂 Database</h1>", unsafe_allow_html=True)
    t_c1, t_c2 = st.columns([4, 1])
    n_t = t_c1.text_input("New Tier Name")
    if t_c2.button("➕"):
        if n_t and n_t not in db_df.columns:
            st.session_state.inventory[n_t] = 0.0; save_data(st.session_state.inventory, DB_FILE); log_action(f"📂 [DATABASE] Added Price Tier '{n_t}'"); st.rerun()
    ed = st.data_editor(st.session_state.inventory, use_container_width=True, hide_index=True, num_rows="dynamic")
    if not ed.equals(st.session_state.inventory): log_action("📂 Database modified."); st.session_state.inventory = ed; save_data(ed, DB_FILE); st.rerun()

elif page == "Inventory":
    st.markdown("<h1>📦 Inventory Summary</h1>", unsafe_allow_html=True)
    c_l, c_r = st.columns([1, 2])
    with c_l:
        st.write("### 📊 Quick Tally")
        sum_df = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index()
        sum_df["Alert"] = sum_df["Quantity"].apply(lambda q: "❌ Out" if q <= 0 else "⚠️ Low" if q < 5 else "✅ Good")
        st.dataframe(sum_df, use_container_width=True, hide_index=True)
    with c_r:
        st.write("### ⚙️ Add Stock Entry")
        f_row = st.columns([1.5, 0.7, 1, 0.4])
        n_p, n_q, n_s = f_row[0].selectbox("Product", product_list), f_row[1].number_input("Qty", min_value=1), f_row[2].selectbox("Status", ["In Stock", "Bought"])
        if f_row[3].button("➕"):
            n_row = pd.DataFrame({"Product Name": [n_p], "Quantity": [n_q], "Status": [n_s], "Date": [date.today()]})
            st.session_state.stock = pd.concat([st.session_state.stock, n_row], ignore_index=True); save_data(st.session_state.stock, STOCK_FILE); log_action(f"➕ [STOCK-IN] {n_q} units of '{n_p}'"); st.rerun()
        s_v = st.session_state.stock.copy().iloc[::-1]
        s_conf = {"Product Name": st.column_config.SelectboxColumn(options=sorted(product_list)), "Status": st.column_config.SelectboxColumn(options=["In Stock", "Bought"])}
        ed_s = st.data_editor(s_v, use_container_width=True, hide_index=True, num_rows="dynamic", column_config=s_conf)
        if not ed_s.equals(s_v): log_action("📦 Inventory Log adjusted."); st.session_state.stock = ed_s.iloc[::-1]; save_data(st.session_state.stock, STOCK_FILE); st.rerun()

elif page == "Dashboard":
    st.markdown("<h1>📊 Dashboard</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        f_row = st.columns(2)
        all_dates = pd.to_datetime(st.session_state.sales["Date"])
        y = sorted(all_dates.dt.year.unique().tolist(), reverse=True) if not all_dates.empty else [date.today().year]
        s_y, s_m = f_row[0].selectbox("Year", y), f_row[1].selectbox("Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], index=date.today().month-1)
    month_idx = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"].index(s_m)+1
    f_sales = st.session_state.sales.copy(); f_sales["Date"] = pd.to_datetime(f_sales["Date"])
    f_sales = f_sales[(f_sales["Date"].dt.year == s_y) & (f_sales["Date"].dt.month == month_idx)]
    cash = (st.session_state.cash_in['Amount'].sum() + st.session_state.sales['Profit'].sum()) - st.session_state.expenditures['Cost'].sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Money", f"₱{cash:,.2f}"); m2.metric("Monthly Profit", f"₱{f_sales['Profit'].sum():,.2f}")
    m3.metric("Net Period Profit", f"₱{(f_sales['Profit'].sum() - st.session_state.expenditures['Cost'].sum()):,.2f}"); m4.metric("Unpaid Balance", f"₱{f_sales[f_sales['Payment'] == 'Unpaid']['Total'].sum():,.2f}")
    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.write("### 🚨 Current Stock Alerts")
        summary = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index()
        alerts = summary[summary["Quantity"] < 5].sort_values("Quantity")
        if not alerts.empty: st.dataframe(alerts, use_container_width=True, hide_index=True)
        else: st.success("All stock healthy! ✅")
    with c2:
        st.write("### 🏆 Top Selling Products")
        if not f_sales.empty: st.table(f_sales.groupby("Product")["Qty"].sum().sort_values(ascending=False).head(5).reset_index())
    st.write("---")
    st.write("### 📈 Net Cash Flow Trend")
    p, d, e = st.session_state.sales[['Date', 'Profit']].rename(columns={'Profit': 'Amt'}), st.session_state.cash_in[['Date', 'Amount']].rename(columns={'Amount': 'Amt'}), st.session_state.expenditures[['Date', 'Cost']].rename(columns={'Cost': 'Amt'})
    e['Amt'] = -e['Amt']; t_df = pd.concat([p, d, e])
    if not t_df.empty:
        t_df['Date'] = pd.to_datetime(t_df['Date']); t_df = t_df.sort_values('Date').groupby('Date').sum().reset_index(); t_df['CumCash'] = t_df['Amt'].cumsum()
        st.plotly_chart(px.line(t_df, x='Date', y='CumCash', template="plotly_dark", markers=True), use_container_width=True)
