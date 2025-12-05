import streamlit as st
import sqlite3
import pandas as pd
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

# ---------- Load environment variables ----------
load_dotenv("/Users/karthika/anaconda-ubuntu/.env")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ---------- SQLite connection ----------
DB_PATH = "/Users/karthika/anaconda-ubuntu/shared_folder/patient.db"

# Database schema for context
DATABASE_SCHEMA = """
Database Schema:

LOOKUP TABLES:
- genders (gender_id INTEGER PRIMARY KEY, gender_desc TEXT)
- races (race_id INTEGER PRIMARY KEY, race_desc TEXT)
- marital_statuses (marital_status_id INTEGER PRIMARY KEY, marital_status_desc TEXT)
- languages (language_id INTEGER PRIMARY KEY, language_desc TEXT)
- lab_units (unit_id INTEGER PRIMARY KEY, unit_string TEXT)
- lab_tests (lab_test_id INTEGER PRIMARY KEY, lab_name TEXT, unit_id INTEGER)
- diagnosis_codes (diagnosis_code TEXT PRIMARY KEY, diagnosis_description TEXT)

CORE TABLES:
- patients (
    patient_id TEXT PRIMARY KEY,
    patient_gender INTEGER REFERENCES genders(gender_id),
    patient_dob TIMESTAMP,
    patient_race INTEGER REFERENCES races(race_id),
    patient_marital_status INTEGER REFERENCES marital_statuses(marital_status_id),
    patient_language INTEGER REFERENCES languages(language_id),
    patient_population_pct_below_poverty REAL
)

- admissions (
    patient_id TEXT,
    admission_id INTEGER,
    admission_start TIMESTAMP,
    admission_end TIMESTAMP,
    PRIMARY KEY (patient_id, admission_id)
)

- admission_primary_diagnoses (
    patient_id TEXT,
    admission_id INTEGER,
    diagnosis_code TEXT REFERENCES diagnosis_codes(diagnosis_code),
    PRIMARY KEY (patient_id, admission_id)
)

- admission_lab_results (
    patient_id TEXT,
    admission_id INTEGER,
    lab_value REAL,
    lab_datetime TIMESTAMP,
    lab_test_id INTEGER REFERENCES lab_tests(lab_test_id)
)

IMPORTANT NOTES:
- Use JOINs to get descriptive values from lookup tables
- patient_dob, admission_start, admission_end, and lab_datetime are TIMESTAMP types
- To calculate age: strftime('%Y','now') - strftime('%Y',patient_dob)
- To calculate length of stay in days: julianday(admission_end) - julianday(admission_start)
- Always use proper JOINs for foreign key relationships
"""

# ---------- Database connection ----------
@st.cache_resource
def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        return conn
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        return None

# ---------- Run query ----------
def run_query(sql):
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        df = pd.read_sql_query(sql, conn)
        return df
    except Exception as e:
        st.error(f"Error executing query: {e}")
        return None

# ---------- OpenAI client ----------
@st.cache_resource
def get_openai_client():
    """Create and cache OpenAI client."""
    return OpenAI(api_key=OPENAI_API_KEY)

# ---------- Extract SQL from GPT response ----------
def extract_sql_from_response(response_text):
    """Extract SQL query from ChatGPT response."""
    sql_pattern = r"```sql\s*(.*?)\s*```"
    matches = re.findall(sql_pattern, response_text, re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[0].strip()
    code_pattern = r"```(?:.*)?\s*(.*?)\s*```"
    matches = re.findall(code_pattern, response_text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return response_text.strip()

# ---------- Generate SQLite-compatible SQL using GPT ----------
def generate_sql_with_gpt(question):
    client = get_openai_client()
    prompt = f"""
You are an SQLite expert. Given the following database schema and a user's question, generate a valid SQLite query.

{DATABASE_SCHEMA}

User Question: {question}

Requirements:
1. Generate ONLY the SQL query, wrapped in ```sql``` code blocks
2. Use proper JOINs to get descriptive names from lookup tables
3. Use appropriate aggregations (COUNT, AVG, SUM, etc.) when needed
4. Add LIMIT clauses for queries that might return many rows (default LIMIT 100)
5. Use proper date/time functions for TIMESTAMP columns (use julianday() and strftime())
6. Make sure the query is syntactically correct for SQLite
7. Add helpful column aliases using AS

Generate the SQL query:"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an SQLite expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )

        raw_text = response.choices[0].message.content
        sql_query = extract_sql_from_response(raw_text)
        return sql_query, response

    except Exception as e:
        st.error(f"Error calling OpenAI API: {e}")
        return None, None

# ---------- Streamlit App ----------
def main():
    st.title("🤖 AI-Powered SQL Query Assistant")
    st.markdown(
        "Ask questions in natural language, and I will generate SQL queries for you to review and run!"
    )
    st.markdown("---")

    # Sidebar
    st.sidebar.title("💡 Example Questions")
    st.sidebar.markdown("""
    Try asking questions like:

    **Demographics:**  
    - How many patients do we have by gender?

    **Admissions:**  
    - What is the average length of stay?
    """)
    st.sidebar.markdown("---")
    st.sidebar.info("""
    🖊️**How it works:**

    1. Enter your question in plain English  
    2. AI generates an SQL query  
    3. Review and optionally edit the query  
    4. Click "Run Query" to execute
    """)

    # ---------- Initialize session state ----------
    if 'generated_sql' not in st.session_state:
        st.session_state.generated_sql = None
    if 'current_question' not in st.session_state:
        st.session_state.current_question = None
    if 'query_history' not in st.session_state:
        st.session_state.query_history = [] 

    # ---------- User Input ----------
    user_question = st.text_area(
        "What would you like to know?",
        height=100,
        placeholder="What is the average length of stay?"
    )

    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        generate_button = st.button("Generate SQL", type="primary", use_container_width=True)
    with col2:
        clear_button = st.button("Clear History", use_container_width=True)

    # ---------- Generate SQL ----------
    if generate_button and user_question:
        user_question = user_question.strip()
        if st.session_state.current_question != user_question:
            st.session_state.generated_sql = None
            st.session_state.current_question = None

        with st.spinner("🧠 AI is thinking and generating SQL..."):
            sql_query, _ = generate_sql_with_gpt(user_question)
            if sql_query:
                st.session_state.generated_sql = sql_query
                st.session_state.current_question = user_question

    # ---------- Display & edit SQL ----------
    if st.session_state.generated_sql:
        st.markdown("---")
        st.subheader("Generated SQL Query")
        st.info(f"**Question:** {st.session_state.current_question}")

        edited_sql = st.text_area(
            "Review and edit the SQL query if needed:",
            value=st.session_state.generated_sql,
            height=400,
            key="sql_editor"
        )

        col1, col2 = st.columns([1, 5])
        with col1:
            run_button = st.button("Run Query", type="primary", use_container_width=True)

        if run_button and edited_sql.strip():
            with st.spinner("Executing query ..."):
                df = run_query(edited_sql)

                if df is not None:
                    st.session_state.query_history.append(
                    {'question': user_question,
                     'sql': edited_sql,
                     'rows': len(df)}
                    )

                    st.markdown("---")
                    st.subheader("📊 Query Results")
                    st.success(f"✅ Query returned {len(df)} rows")
                    st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()
