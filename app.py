import streamlit as st

st.set_page_config(page_title="Medical Interview", layout="centered")

st.title("Medical Interview")

name = st.text_input("What is your name?")
age = st.number_input("How old are you?", min_value=0, max_value=120)

main_problem = st.text_input("What is your main problem?")

if main_problem:
    duration = st.selectbox(
        "How long have you had this problem?",
        ["< 24 hours", "1–7 days", "> 1 week", "> 1 month"]
    )

    severity = st.slider("How severe is it?", 0, 10, 5)

    additional = st.text_area("Any additional symptoms?")

submit = st.button("Submit")

if submit:
    if not name or not main_problem:
        st.error("Please fill required fields.")
    else:
        st.success("Interview completed.")
        st.write("Summary:")
        st.write(f"Patient: {name}, Age: {age}")
        st.write(f"Main problem: {main_problem}")
        if main_problem:
            st.write(f"Duration: {duration}")
            st.write(f"Severity: {severity}/10")
            st.write(f"Additional symptoms: {additional}")
