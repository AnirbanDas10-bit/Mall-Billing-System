import streamlit as st
import mysql.connector as m
from fpdf import FPDF
import datetime
import certifi

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
        try:
            # We replace hardcoded strings with st.secrets
            self.db = m.connect(
                host=st.secrets["tidb"]["host"],
                port=st.secrets["tidb"]["port"],
                user=st.secrets["tidb"]["user"],
                password=st.secrets["tidb"]["password"],
                database=st.secrets["tidb"]["database"],
                ssl_ca=certifi.where(),
                ssl_verify_cert=True
            )
            self.cursor = self.db.cursor(dictionary=True)
        except Exception as e:
            st.error(f"❌ Connection Failed: {e}")

    def get_customer(self, ph):
        self.cursor.execute("SELECT * FROM customer_details WHERE customer_phone_num = %s", (ph,))
        return self.cursor.fetchone()

    def reg_customer(self, name, loc, ph):
        try:
            self.cursor.execute(
                "INSERT INTO customer_details (customer_name, customer_location, customer_phone_num) VALUES (%s, %s, %s)",
                (name, loc, ph)
            )
            self.db.commit()
            return True
        except Exception as e:
            st.error(f"Reg Error: {e}")
            return False

    def get_product(self, p_id):
        self.cursor.execute("SELECT product_name, product_price FROM product_detail WHERE product_id = %s", (p_id,))
        return self.cursor.fetchone()

    def close(self):
        if hasattr(self, 'db'):
            self.cursor.close()
            self.db.close()


# --- PDF Generation Logic ---
def generate_pdf(customer, cart, total):
    pdf = FPDF()
    pdf.add_page()

    # Heading
    pdf.set_font("Arial", 'B', 22)
    pdf.set_text_color(229, 9, 20)  # Red
    pdf.cell(200, 15, txt="Anirban Mall Billing Receipt", ln=True, align='C')

    # Date and Meta
    pdf.set_font("Arial", size=10)
    pdf.set_text_color(100)
    pdf.cell(200, 10, txt=f"Invoice Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True,
             align='C')
    pdf.ln(10)

    # Customer Info Box
    pdf.set_fill_color(240, 240, 240)
    pdf.set_text_color(0)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt=" CUSTOMER DETAILS", ln=True, fill=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, txt=f" Name: {customer['customer_name']}", ln=True)
    pdf.cell(0, 8, txt=f" Phone: {customer['customer_phone_num']}", ln=True)
    pdf.cell(0, 8, txt=f" Location: {customer['customer_location']}", ln=True)
    pdf.ln(10)

    # Table Header
    pdf.set_fill_color(229, 9, 20)
    pdf.set_text_color(255)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(90, 10, "Product Description", 1, 0, 'C', True)
    pdf.cell(30, 10, "Price", 1, 0, 'C', True)
    pdf.cell(25, 10, "Qty", 1, 0, 'C', True)
    pdf.cell(45, 10, "Subtotal", 1, 1, 'C', True)

    # Table Body
    pdf.set_text_color(0)
    pdf.set_font("Arial", size=11)
    for item in cart:
        pdf.cell(90, 10, item['name'], 1)
        pdf.cell(30, 10, f"{item['price']:.2f}", 1, 0, 'C')
        pdf.cell(25, 10, str(item['qty']), 1, 0, 'C')
        pdf.cell(45, 10, f"INR {item['total']:.2f}", 1, 1, 'C')

    # Grand Total
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(145, 12, "GRAND TOTAL PAYABLE:", 0, 0, 'R')
    pdf.set_text_color(229, 9, 20)
    pdf.cell(45, 12, f"INR {total:.2f}", 1, 1, 'C')

    return pdf.output()


# --- Main App Logic ---
def main():
    st.title("🛒 Anirban's Demo Mall Billing System")

    # Use session state to keep the DB connection alive
    if 'db_manager' not in st.session_state:
        st.session_state.db_manager = TiDBManager()

    db = st.session_state.db_manager

    if 'cart' not in st.session_state: st.session_state.cart = []
    if 'cust' not in st.session_state: st.session_state.cust = None

    # Sidebar: Customer Management
    with st.sidebar:
        st.header("Cashier Panel")
        ph = st.text_input("Customer Phone", max_chars=10, placeholder="10-digit number")

        if st.button("Search Database"):
            res = db.get_customer(ph)
            if res:
                st.session_state.cust = res
                st.success(f"Customer: {res['customer_name']}")
            else:
                st.warning("Not found. Register new below.")

        if not st.session_state.cust and len(ph) == 10:
            st.divider()
            new_name = st.text_input("Full Name")
            new_loc = st.text_input("Location")
            if st.button("Register Customer"):
                if db.reg_customer(new_name.title(), new_loc.title(), ph):
                    st.success("Member Registered!")
                    st.session_state.cust = db.get_customer(ph)

    # Main Area: Product Entry and Billing
    if st.session_state.cust:
        st.write(f"### Billing for: **{st.session_state.cust['customer_name']}**")
        col1, col2 = st.columns([1.5, 1])

        with col1:
            st.subheader("Inventory Scan")
            p_id = st.text_input("Product ID", placeholder="Enter Product Code")
            qty = st.number_input("Quantity", min_value=1, step=1)

            if st.button("Add Item to Cart"):
                prod = db.get_product(p_id)
                if prod:
                    st.session_state.cart.append({
                        "name": prod['product_name'],
                        "price": float(prod['product_price']),
                        "qty": qty,
                        "total": float(prod['product_price']) * qty
                    })
                    st.toast(f"Added {prod['product_name']}!", icon="✅")
                else:
                    st.error("Product ID not found.")

        with col2:
            st.subheader("Live Receipt Preview")
            grand_total = 0
            if st.session_state.cart:
                for item in st.session_state.cart:
                    st.markdown(f"""
                    <div class='card'>
                        <b>{item['name']}</b><br>
                        {item['qty']} x {item['price']} = <b>INR {item['total']:.2f}</b>
                    </div>
                    """, unsafe_allow_html=True)
                    grand_total += item['total']

                st.write(f"## Total: INR {grand_total:.2f}")

                # PDF Action
                
                pdf_data = generate_pdf(st.session_state.cust, st.session_state.cart, grand_total)
                pdf_bytes = bytes(pdf_data)
                st.download_button(
                    label="📥 Print PDF Receipt",
                    data=pdf_bytes,
                    file_name=f"Receipt_{st.session_state.cust['customer_name']}.pdf",
                    mime="application/pdf"
                )

                if st.button("Reset / New Transaction"):
                    st.session_state.cart = []
                    st.session_state.cust = None
                    st.rerun()
            else:
                st.info("Cart is empty. Start scanning products.")
    else:
        st.info("👈 Please enter a phone number in the sidebar to begin.")


if __name__ == "__main__":
    main()
