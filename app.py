import tempfile
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

st.set_page_config(page_title="PDF test", layout="centered")

st.title("PDF test")
st.success("Streamlit works")
st.write("ReportLab loaded correctly.")

if st.button("Generate PDF"):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()

    c = canvas.Canvas(tmp.name, pagesize=A4)
    c.setFont("Helvetica", 16)
    c.drawString(100, 800, "PDF test works")
    c.drawString(100, 780, "Health Assessment - Medical Interview")
    c.save()

    with open(tmp.name, "rb") as f:
        pdf_bytes = f.read()

    st.success("PDF generated successfully.")
    st.download_button(
        "Download PDF",
        data=pdf_bytes,
        file_name="test_report.pdf",
        mime="application/pdf",
    )
