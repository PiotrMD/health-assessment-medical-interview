import streamlit as st

st.set_page_config(page_title="Health Assessment", layout="centered")

st.title("Health Assessment - Medical Interview")

name = st.text_input("Name")
phone = st.text_input("Phone number")

submit = st.button("Submit")

if submit:
    if not phone or not any(c.isdigit() for c in phone):
        st.error("Enter a valid phone number")
    else:
        st.success("Form submitted successfully")
