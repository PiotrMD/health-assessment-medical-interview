import streamlit as st

st.set_page_config(page_title="Medical Interview", layout="centered")

st.title("Medical Interview")

name = st.text_input("What is your name?")
age = st.number_input("How old are you?", min_value=0, max_value=120)

symptoms = st.text_area("Describe your symptoms")

submit = st.button("Submit")

if submit:
    if not name or not symptoms:
        st.error("Please fill all required fields.")
    else:
        st.success("Thank you. Your medical interview has been recorded.")
