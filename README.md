# 💊 PharmaDash (PostgreSQL Edition)

> Multi-store pharmacy analytics dashboard for Hyderabad pharmacy chains — built with Python, Streamlit, PostgreSQL, and Groq AI.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue?logo=postgresql) ![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red?logo=streamlit) ![Plotly](https://img.shields.io/badge/Plotly-5.20+-3F4F75?logo=plotly) ![Groq](https://img.shields.io/badge/AI-Groq%20Llama%203.3-orange)

---

## 📋 Overview

PharmaDash is a full-stack pharmacy analytics platform that centralises sales, inventory, supplier, and financial data across **5 Hyderabad pharmacy stores** into a single interactive web dashboard. 

Unlike the previous version which loaded data directly from CSV files, this updated version stores and queries data in **PostgreSQL** to simulate a real-world enterprise database setup. It features real-time filtering, automated reorder triggers, supplier risk scoring, and a multi-turn AI Assistant powered by Groq's Llama 3.3 model.

---

## 📁 Project Structure

```
pharma_dash/
├── pharma.py             # Main Streamlit dashboard application
├── setup_db.py           # Database setup script (creates database, tables & imports CSVs)
├── requirements.txt      # Python dependencies
├── .env                  # DB credentials & Groq API Key (not committed)
├── Dim_Products_20k.csv  # Product master dataset
├── Dim_Store.csv         # Store information (location, names)
├── Dim_Suppliers_20k.csv # Supplier ratings and lead times
├── Fact_Sales_20k.csv    # 20,000 sales transactions
└── Fact_Stock_20k.csv    # Batch-level stock records
```

---

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/Manideep0704/pharma-dash.git
cd pharma-dash
```

### 2. Install Dependencies
Make sure you have Python 3.11+ installed. Install the required packages:
```bash
pip install -r requirements.txt
```

### 3. Configure the Environment
Create a `.env` file in the root directory with your PostgreSQL credentials and Groq API Key:
```env
# PostgreSQL Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pharma_dash
DB_USER=postgres
DB_PASSWORD=your_postgres_password_here

# AI Configuration (Get a free key at console.groq.com)
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### 4. Set Up the Database
Make sure PostgreSQL is running on your machine. Run the setup script to create the database, define table schemas, create indexes, and import all CSV data:
```bash
python setup_db.py
```
*(This script URL-encodes special characters in passwords and ensures UTF-8 printing in the terminal).*

### 5. Run the Application
Launch the Streamlit dashboard:
```bash
streamlit run pharma.py
```
The application will open automatically at **http://localhost:8501**.

---

## 📊 Database Schema

The database consists of 5 tables:
* **`fact_sales`**: Raw sales transactions (TransactionID, Date, ProductID, Store_ID, QuantitySold, UnitPrice, TotalAmount, CustomerType).
* **`fact_stock`**: Current stock levels and batches (StockID, Store_ID, ProductID, BatchNumber, QuantityOnHand, ExpiryDate, DaysToExpiry, ExpiryStatus).
* **`dim_products`**: Master product directory (ProductID, ProductName, Category, UnitCost, RetailPrice, ReorderPoint, SafetyStock).
* **`dim_store`**: Store location coordinates and names.
* **`dim_suppliers`**: Supplier lead times and ratings.

---

## 🌟 Key Features

* **Home & Executive KPIs**: High-level financial cards showing total sales, inventory valuation, expired stock wastage, and overall health status.
* **Sales & Demand**: Detailed revenue timelines, category splits, and medicine velocity (fast-moving vs slow-moving inventory).
* **Inventory & Expiry**: Batch-level expiration status with conditional coloring and safety stock indicators.
* **Supplier Analysis**: Composite supplier risk scoring evaluating out-of-stock batches, ratings, and lead times.
* **Business Insights**: Underperforming store alerts, below-cost medicine tags, and auto-generated restocking checklists.
* **AI Assistant**: A chat interface powered by **Llama-3.3-70B** through Groq, letting you ask questions about your store's inventory, revenue, and margins using natural language.

---

## 🛡️ License

This project is licensed under the MIT License - see the LICENSE file for details.
