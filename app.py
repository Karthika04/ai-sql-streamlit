import streamlit as st
import sqlite3
import pandas as pd
import openai
import os

openai.api_key =  os.getenv("OPENAI_API_KEY")
DB_PATH = "patient.db"


def query_db(sql_query):
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(sql_query, conn)
        return df
    except Exception as e:
        st.error(f"SQL error: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def ask_openai(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates SQL queries for a SQLite database."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message["content"]


st.title("Patient Database Explorer with OpenAI")


conn = sqlite3.connect(DB_PATH)
tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
conn.close()
st.sidebar.subheader("Tables in database")
st.sidebar.table(tables)

table_selected = st.sidebar.selectbox("Select a table to view", tables["name"].tolist())
if table_selected:
    st.subheader(f"Preview of {table_selected}")
    df = query_db(f"SELECT * FROM {table_selected} LIMIT 10;")
    st.dataframe(df)


st.subheader("First 10 Patients")
df_patients = query_db("SELECT * FROM patients LIMIT 10;")
st.dataframe(df_patients)

st.subheader("Top Patients by Lab Count")
df_lab_counts = query_db("""
SELECT PatientID, COUNT(LabName) AS LabCount
FROM stage_labs
GROUP BY PatientID
ORDER BY LabCount DESC
LIMIT 10;
""")
st.dataframe(df_lab_counts)
st.bar_chart(df_lab_counts.set_index("PatientID"))


st.subheader("Run a Custom SQL Query")
user_query = st.text_area("Enter SQL query here", height=100)
if st.button("Run Query"):
    if user_query.strip() != "":
        df_custom = query_db(user_query)
        st.dataframe(df_custom)


st.subheader("Ask a Question (OpenAI)")
user_prompt = st.text_area("Enter your question about the patient data", height=100)

if st.button("Ask AI"):
    if user_prompt.strip() != "":
        with st.spinner("Generating SQL query with OpenAI..."):
            ai_sql = ask_openai(f"Generate a valid SQLite query for this database: {user_prompt}")
            st.code(ai_sql, language="sql")
            
            # Try running the SQL query
            st.subheader("AI Query Results")
            df_ai = query_db(ai_sql)
            st.dataframe(df_ai)


