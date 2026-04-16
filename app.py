import tempfile
import smtplib
from email.message import EmailMessage

import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# CONFIG
st.set_page_config(page_title="Medical Interview", layout="centered")

# UI
st.title("Medical Interview")

name = st.text_input("What is your name?")
age = st.number_input("How old are you?", min_value=0)
problem = st.text_area("What is your main problem?")
symptoms = st.text_area("Describe your symptoms")
duration = st.text_input("How long do symptoms last?")
meds = st.text_input("Are you taking any medications?")
allergies = st.text_input("Do you have any allergies?")
submit = st.button("Submit")

# AFTER SUBMIT
if submit:
    if not name:
        st.error("Please enter your name")
    else:
        # ===== PDF GENERATION =====
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()

        c = canvas.Canvas(tmp.name, pagesize=A4)

        y = 800
        c.setFont("Helvetica-Bold", 18)
        c.drawString(100, y, "Medical Interview Report")

        c.setFont("Helvetica", 12)
        y -= 40

        data = [
            f"Name: {name}",
            f"Age: {age}",
            f"Main problem: {problem}",
            f"Symptoms: {symptoms}",
            f"Duration: {duration}",
            f"Medications: {meds}",
            f"Allergies: {allergies}",
        ]

        for line in data:
            y -= 25
            c.drawString(100, y, line)

        c.save()

        with open(tmp.name, "rb") as f:
            pdf_bytes = f.read()

        st.success("Report generated")

        # DOWNLOAD BUTTON
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name="medical_report.pdf",
            mime="application/pdf",
        )

        # ===== EMAIL SENDING =====
        try:
            msg = EmailMessage()
            msg["Subject"] = "Medical Interview Report"
            msg["From"] = st.secrets["EMAIL_USER"]
            msg["To"] = st.secrets["EMAIL_RECEIVER"]

            msg.set_content("Medical report attached.")

            msg.add_attachment(
                pdf_bytes,
                maintype="application",
                subtype="pdf",
                filename="medical_report.pdf",
            )

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(
                    st.secrets["EMAIL_USER"],
                    st.secrets["EMAIL_PASSWORD"]
                )
                smtp.send_message(msg)

            st.success("Email sent successfully")

        except Exception as e:
            st.error(f"Email error: {e}")
