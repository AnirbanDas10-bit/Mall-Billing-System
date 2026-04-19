import streamlit as st
import mysql.connector as m
from fpdf import FPDF
import datetime
import certifi
import pandas as pd

# --- Page Configuration ---
st.set_page_config(page_title="Anirban's Demo Mall", layout="wide")

# Netflix-style Dark Theme CSS
st.markdown("""
    <style>
    .main { background-color: #141414; color: white; }
    .stButton>button {
        background-color: #E50914; color: white; border-radius: 4px;
        width: 100%; font-weight: bold; border: none; height: 3em;
    }
    .stButton>button:hover { background-color: #B20710; color: white; border: none; }
    .card {
        background-color: #2F2F2F; padding: 15px; border-radius: 8px;
        margin-bottom: 10px; border-left: 5px solid #E50914;
    }
    h1, h2, h3 { color: #E50914 !important; }
    .stTextInput>div>div>input { background-color: #333; color: white; }
    </style>
    """, unsafe_allow_html=True)


# --- TiDB Cloud Connection Manager ---
class TiDBManager:
    def __init__(self):
        self.db = None
        self.cursor = None
        try:
            self.db = m.connect(
                host=st.secrets["tidb"]["host"],
                port=st.secrets["tidb"]["port"],
                user=st.secrets["tidb"]["user"],
                password=st.secrets["tidb"]["password"],
                database=st.secrets["tidb"]["database"],
                ssl_ca=certifi.where(),
                ssl_verify_cert=True,
                autocommit=True
            )
            self.cursor = self.db.cursor(dictionary=True)
        except Exception as e:
            st.error(f"❌ Connection Failed: {e}")

    def is_connected(self):
        """Returns True only if both connection and cursor are active."""
        return self.db is not None and self.cursor is not None

    def get_customer(self, ph):
        if not self.is_connected(): return None
        self.cursor.execute("SELECT * FROM customer_details WHERE customer_phone_num = %s", (ph,))
        return self.cursor.fetchone()

    def reg_customer(self, name, loc, ph):
        if not self.is_connected(): return False
        try:
            self.cursor.execute(
                "INSERT INTO customer_details (customer_name, customer_location, customer_phone_num) VALUES (%s, %s, %s)",
                (name, loc, ph)
            )
            return True
        except Exception as e:
            st.error(f"Reg Error: {e}")
            return False

    def get_product(self, p_id):
        if not self.is_connected(): return None
        self.cursor.execute("SELECT * FROM product_detail WHERE product_id = %s", (p_id,))
        return self.cursor.fetchone()

    def bill_details(self, product_id, quantity, ph):
        if not self.is_connected(): return False
        try:
            # Find Customer ID from Phone
            self.cursor.execute("SELECT customer_id FROM customer_details WHERE customer_phone_num = %s", (ph,))
            cust = self.cursor.fetchone()

            if cust:
                cust_id = cust['customer_id']
                query = """
                    INSERT INTO bill_details (customer_id, product_id, quantity, time_of_bill) 
                    VALUES (%s, %s, %s, NOW())
                """
                self.cursor.execute(query, (cust_id, product_id, quantity))
                return True
            return False
        except Exception as e:
            st.error(f"Audit Logging Error: {e}")
            return False

    def get_audit_logs(self):
        if not self.is_connected(): return []
        query = """
            SELECT 
                b.bill_id, 
                c.customer_name, 
                p.product_name, 
                b.quantity,
                (p.product_price * b.quantity) as total_price,
                DATE_FORMAT(b.time_of_bill, '%d-%b-%Y') as day_month_year,
                TIME(b.time_of_bill) as time
            FROM bill_details b
            JOIN customer_details c ON b.customer_id = c.customer_id
            JOIN product_detail p ON b.product_id = p.product_id
            ORDER BY b.time_of_bill DESC
        """
        try:
            self.cursor.execute(query)
            return self.cursor.fetchall()
        except Exception as e:
            st.error(f"Audit fetch failed: {e}")
            return []

    def close(self):
        if self.db:
            self.cursor.close()
            self.db.close()


# --- PDF Generation ---
def generate_pdf(customer, cart, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 22)
    pdf.set_text_color(229, 9, 20)
    pdf.cell(200, 15, txt="Anirban Mall Billing Receipt", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    pdf.set_text_color(0)
    pdf.cell(0, 10, txt=f"Customer: {customer['customer_name']}", ln=True)
    pdf.cell(0, 10, txt=f"Date: {datetime.datetime.now().strftime('%d-%b-%Y %H:%M')}", ln=True)
    pdf.ln(5)

    # Table headers
    pdf.set_fill_color(229, 9, 20)
    pdf.set_text_color(255)
    pdf.cell(90, 10, "Product", 1, 0, 'C', True)
    pdf.cell(30, 10, "Qty", 1, 0, 'C', True)
    pdf.cell(60, 10, "Total", 1, 1, 'C', True)

    pdf.set_text_color(0)
    for item in cart:
        pdf.cell(90, 10, item['name'], 1)
        pdf.cell(30, 10, str(item['qty']), 1, 0, 'C')
        pdf.cell(60, 10, f"INR {item['total']:.2f}", 1, 1, 'C')

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Grand Total: INR {total:.2f}", 0, 1, 'R')
    return pdf.output()


# --- Main App ---
def main():
    st.title("🛒 Anirban's Demo Mall Billing System")

    if 'db_manager' not in st.session_state:
        st.session_state.db_manager = TiDBManager()
    db = st.session_state.db_manager

    tab1, tab2 = st.tabs(["Point of Sale (Cashier)", "Audit Logs (Manager)"])

    with tab1:
        if 'cart' not in st.session_state: st.session_state.cart = []
        if 'cust' not in st.session_state: st.session_state.cust = None

        col_side, col_main = st.columns([1, 3])

        with col_side:
            st.subheader("Customer")
            ph = st.text_input("Phone Number", max_chars=10)
            if st.button("Check Member"):
                res = db.get_customer(ph)
                if res:
                    st.session_state.cust = res
                else:
                    st.error("Not Found")

            if st.session_state.cust:
                st.success(f"Active: {st.session_state.cust['customer_name']}")

        with col_main:
            if st.session_state.cust:
                c1, c2 = st.columns(2)
                with c1:
                    p_id = st.text_input("Scan Product ID")
                    qty = st.number_input("Qty", min_value=1, value=1)
                    if st.button("Add to Cart"):
                        prod = db.get_product(p_id)
                        if prod:
                            st.session_state.cart.append({
                                "name": prod['product_name'],
                                "price": float(prod['product_price']),
                                "qty": qty,
                                "total": float(prod['product_price']) * qty
                            })
                            db.bill_details(p_id, qty, ph)
                            st.toast("Item Logged!")
                        else:
                            st.error("Invalid Product ID")

                with c2:
                    st.subheader("Current Bill")
                    g_total = sum(item['total'] for item in st.session_state.cart)
                    for item in st.session_state.cart:
                        st.text(f"{item['name']} x{item['qty']} - INR {item['total']}")
                    st.divider()
                    st.write(f"### Total: INR {g_total}")

                    if g_total > 0:
                        pdf_data = generate_pdf(st.session_state.cust, st.session_state.cart, g_total)
                        st.download_button("Print Receipt", data=bytes(pdf_data), file_name="bill.pdf")

                        if st.button("Clear Transaction"):
                            st.session_state.cart = []
                            st.session_state.cust = None
                            st.rerun()

    # --- INTEGRATED AUDITOR TAB WITH CONNECTION CHECK ---
    with tab2:
        st.subheader("📊 Auditor Tracking Dashboard")
        if db.is_connected():
            if st.button("Refresh Audit Logs"):
                logs = db.get_audit_logs()
                if logs:
                    df = pd.DataFrame(logs)
                    st.dataframe(df, use_container_width=True)

                    # Quick Stats
                    m1, m2 = st.columns(2)
                    m1.metric("Total Transactions", len(df))
                    m2.metric("Total Revenue Tracked", f"INR {df['total_price'].sum():.2f}")
                else:
                    st.info("No logs found in the bill_details table.")
        else:
            st.error("Database is offline. Please check your TiDB Cloud credentials in secrets.toml.")


if __name__ == "__main__":
    main()