import re
import smtplib
import tempfile
from datetime import date, datetime
from email.message import EmailMessage
from typing import Any, Dict, List

import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Health Assessment - Medical Interview",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .main .block-container {
        max-width: 980px;
        padding-top: 0.7rem;
        padding-bottom: 2rem;
    }

    .top-card {
        padding: 18px 18px;
        border-radius: 18px;
        border: 1px solid rgba(120,120,120,0.22);
        margin-bottom: 16px;
        background: rgba(250,250,250,0.03);
    }

    .progress-box {
        padding: 12px 14px;
        border-radius: 14px;
        border: 1px solid rgba(120,120,120,0.22);
        margin-top: 6px;
        margin-bottom: 16px;
        background: rgba(250,250,250,0.02);
    }

    .field-anchor {
        position: relative;
        top: -95px;
        visibility: hidden;
    }

    .field-error-box {
        border: 2px solid #d93025;
        border-radius: 10px;
        padding: 10px 12px;
        color: #d93025;
        background: rgba(217, 48, 37, 0.06);
        font-weight: 600;
        margin-top: -0.15rem;
        margin-bottom: 0.9rem;
    }

    .send-button > button {
        width: 100%;
        height: 3.2rem;
        font-size: 1.05rem;
        font-weight: 700;
        border-radius: 12px;
    }

    .summary-box {
        padding: 18px;
        border-radius: 16px;
        border: 1px solid rgba(120,120,120,0.22);
        margin-top: 16px;
        background: rgba(250,250,250,0.02);
    }

    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SECRETS
# =========================================================
def get_secret(name: str, default: str = "") -> str:
    return st.secrets.get(name, default)


EMAIL_USER = get_secret("EMAIL_USER")
EMAIL_PASSWORD = get_secret("EMAIL_PASSWORD")
EMAIL_RECEIVER = get_secret("EMAIL_RECEIVER")
EMAIL_RECEIVER_2 = get_secret("EMAIL_RECEIVER_2")


# =========================================================
# HELPERS
# =========================================================
def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, bool):
        return value
    return True


def safe(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value).strip()


def list_text(values: List[str]) -> str:
    return ", ".join([v for v in values if v])


def validate_phone(raw: str):
    text = (raw or "").strip()
    if not text:
        return None

    cleaned = (
        text.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if cleaned.startswith("+"):
        digits = cleaned[1:]
    else:
        digits = cleaned

    if not digits.isdigit():
        return None

    if len(digits) < 7 or len(digits) > 15:
        return None

    return text


def select_with_placeholder(label: str, options: list, key: str):
    all_options = [""] + options
    return st.selectbox(
        label,
        all_options,
        format_func=lambda x: "Select" if x == "" else x,
        key=key,
    )


def error_box(message: str):
    st.markdown(
        f"<div class='field-error-box'>{message}</div>",
        unsafe_allow_html=True,
    )


def scroll_to_anchor(anchor_id: str):
    components.html(
        f"""
        <script>
        const target = window.parent.document.getElementById("{anchor_id}");
        if (target) {{
            target.scrollIntoView({{behavior: "smooth", block: "start"}});
        }}
        </script>
        """,
        height=0,
    )


def calc_progress(values):
    if not values:
        return 0
    filled = sum(1 for v in values if nonempty(v))
    return int(round((filled / len(values)) * 100))


def wrap_long_line(text: str, width: int = 110) -> List[str]:
    if not text:
        return []
    text = re.sub(r"\s+", " ", text.strip())
    words = text.split(" ")
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= width:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def add_pdf_section(story, title: str, rows: List[str], styles_dict):
    clean_rows = [r for r in rows if nonempty(r)]
    story.append(Paragraph(title, styles_dict["section"]))
    story.append(Spacer(1, 2.2 * mm))

    if clean_rows:
        for row in clean_rows:
            story.append(Paragraph(row.replace("\n", "<br/>"), styles_dict["body"]))
            story.append(Spacer(1, 1.2 * mm))
    else:
        story.append(Paragraph("No data.", styles_dict["body"]))
        story.append(Spacer(1, 1.2 * mm))

    story.append(Spacer(1, 2.5 * mm))


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states) + 1
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(page_count)
            super().showPage()
        self.draw_page_number(page_count)
        super().save()

    def draw_page_number(self, page_count: int):
        self.setFont("Helvetica", 9)
        self.drawCentredString(A4[0] / 2, 10 * mm, f"Page {self._pageNumber} / {page_count}")


def make_pdf(data: Dict[str, Any]) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()

    doc = SimpleDocTemplate(
        tmp.name,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=18 * mm,
    )

    base = getSampleStyleSheet()
    styles_dict = {
        "title_big": ParagraphStyle(
            "TitleBig",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
            spaceAfter=1.5 * mm,
        ),
        "title_mid": ParagraphStyle(
            "TitleMid",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceAfter=2 * mm,
        ),
        "doctor": ParagraphStyle(
            "Doctor",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=13,
            spaceAfter=2 * mm,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            spaceBefore=2 * mm,
            spaceAfter=1.5 * mm,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
        ),
    }

    story = []
    story.append(Paragraph("HEALTH ASSESSMENT", styles_dict["title_big"]))
    story.append(Paragraph("Medical Interview", styles_dict["title_mid"]))
    story.append(Paragraph("dr n. med. Piotr Niedziałkowski", styles_dict["doctor"]))
    story.append(Paragraph("www.ocenazdrowia.pl", styles_dict["doctor"]))
    story.append(Spacer(1, 1 * mm))

    add_pdf_section(
        story,
        "Identification data",
        [
            f"Patient: {data['first_name']} {data['last_name']}",
            f"Phone number: {data['phone']}",
            f"Email address: {data['email']}",
            f"Date of birth: {data['birth_date']}",
            f"Visit type: {data['visit_type']}",
            f"Submission date and time: {data['submitted_at']}",
        ],
        styles_dict,
    )

    ordered_sections = [
        ("Basic information", data["sec_basic"]),
        ("General assessment", data["sec_overall"]),
        ("Tests performed in the last 2 years", data["sec_tests"]),
        ("Main symptoms", data["sec_main_symptoms"]),
        ("Other symptoms", data["sec_other_symptoms"]),
        ("Symptom pattern", data["sec_symptom_character"]),
        ("Health timeline and medications", data["sec_timeline_meds"]),
        ("Lifestyle", data["sec_lifestyle"]),
        ("Travel", data["sec_travel"]),
        ("Animals", data["sec_animals"]),
        ("Injuries", data["sec_injuries"]),
        ("COVID-19", data["sec_covid"]),
        ("Stress", data["sec_stress"]),
        ("Birth and childhood", data["sec_birth_childhood"]),
        ("General and neurological symptoms", data["sec_general_neuro"]),
        ("Respiratory system", data["sec_respiratory"]),
        ("Cardiovascular system", data["sec_cardio"]),
        ("Gastrointestinal tract", data["sec_gi"]),
        ("Urinary system", data["sec_urinary"]),
        ("Joints and muscles", data["sec_msk"]),
        ("Skin", data["sec_skin"]),
        ("Sleep and mental health", data["sec_sleep_psych"]),
        ("Peripheral circulation", data["sec_peripheral"]),
        ("Anal and perianal area", data["sec_anal"]),
        ("Gynecology or andrology", data["sec_sex_specific"]),
        ("Family history", data["sec_family"]),
        ("Previous diagnoses, surgeries and important information", data["sec_history_final"]),
        ("Most important question for the doctor", data["sec_question"]),
    ]

    for section_title, section_rows in ordered_sections:
        add_pdf_section(story, section_title, section_rows, styles_dict)

    doc.build(story, canvasmaker=NumberedCanvas)
    return tmp.name


def send_email_with_pdf(subject: str, body_text: str, pdf_path: str):
    if not EMAIL_USER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        raise ValueError("Missing email secrets.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER

    recipients = [EMAIL_RECEIVER]
    if EMAIL_RECEIVER_2:
        recipients.append(EMAIL_RECEIVER_2)
    msg["To"] = ", ".join(recipients)

    msg.set_content(body_text)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename="medical_interview_report.pdf",
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASSWORD)
        smtp.send_message(msg)


# =========================================================
# SESSION STATE
# =========================================================
if "field_errors" not in st.session_state:
    st.session_state.field_errors = {}
if "scroll_target" not in st.session_state:
    st.session_state.scroll_target = None

field_errors = st.session_state.field_errors
progress_placeholder = st.empty()


# =========================================================
# HEADER
# =========================================================
st.title("Health Assessment")
st.subheader("Medical Interview")
st.write("dr n. med. Piotr Niedziałkowski")
st.write("www.ocenazdrowia.pl")
st.write("Reception phone: +48 690 584 584")

st.markdown(
    """
    <div class="top-card">
    Dear Patient,<br><br>
    each appointment is prepared individually.<br>
    Please answer honestly and as accurately as possible regarding your health condition.<br>
    The more details you provide, the better the chance of accurate preparation for your visit.<br><br>
    For children, please complete the relevant fields where appropriate.<br><br>
    Data from this form are not stored in the application database. The purpose of this questionnaire is medical visit preparation.<br><br>
    Best regards and see you at the appointment.
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# FORM
# =========================================================
with st.form("medical_interview_form"):
    with st.expander("1. Basic information", expanded=True):
        visit_type = st.radio("Visit type", ["First visit", "Follow-up visit"], key="visit_type")

        st.markdown('<div id="anchor_first_name" class="field-anchor"></div>', unsafe_allow_html=True)
        first_name = st.text_input("First name", key="first_name")
        if "first_name" in field_errors:
            error_box(field_errors["first_name"])

        st.markdown('<div id="anchor_last_name" class="field-anchor"></div>', unsafe_allow_html=True)
        last_name = st.text_input("Last name", key="last_name")
        if "last_name" in field_errors:
            error_box(field_errors["last_name"])

        st.markdown('<div id="anchor_phone" class="field-anchor"></div>', unsafe_allow_html=True)
        phone = st.text_input(
            "Phone number",
            key="phone",
            help="It may include a country code or not, for example 690584584 or +48690584584",
        )
        if "phone" in field_errors:
            error_box(field_errors["phone"])

        email = st.text_input("Email address", key="email")

        birth_date = st.date_input(
            "Date of birth",
            value=date(1990, 1, 1),
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            key="birth_date",
        )

        nationality = st.text_input("Nationality", key="nationality")
        sex = select_with_placeholder("Sex", ["Female", "Male", "Other"], key="sex")
        current_status = select_with_placeholder(
            "Current status",
            ["Working", "Child", "Pupil", "Student", "Retired", "Other"],
            key="current_status",
        )
        profession = st.text_input("Current occupation", key="profession")
        height_cm = st.number_input("Height (cm)", min_value=30.0, max_value=250.0, value=170.0, step=1.0, key="height_cm")
        weight_kg = st.number_input("Weight (kg)", min_value=1.0, max_value=300.0, value=70.0, step=0.1, key="weight_kg")

    with st.expander("2. General assessment"):
        physical_score = st.slider("How do you rate your physical condition? 0 = very poor, 10 = very good", 0, 10, 6, key="physical_score")
        mental_score = st.slider("How do you rate your mental condition? 0 = very poor, 10 = very good", 0, 10, 6, key="mental_score")
        weight_change = st.radio("Has your body weight changed during the last year?", ["Increased", "Decreased", "No change"], key="weight_change")
        weight_change_amount = ""
        if weight_change != "No change":
            weight_change_amount = st.text_input("Approximately by how many kilograms did the weight change?", key="weight_change_amount")

    with st.expander("3. Tests performed in the last 2 years"):
        performed_tests = st.multiselect(
            "Select performed tests",
            [
                "Chest X-ray",
                "ECG",
                "Echocardiography",
                "Holter ECG",
                "24-hour blood pressure monitoring",
                "Gastroscopy",
                "Colonoscopy",
                "Abdominal ultrasound",
                "Pelvic ultrasound",
                "Gynecological ultrasound",
                "Thyroid ultrasound",
                "Testicular ultrasound",
                "Prostate ultrasound",
                "Breast ultrasound",
                "Mammography",
                "CT scan",
                "Head CT scan",
                "MRI",
                "Head MRI",
                "Carotid Doppler",
                "Lower limb vascular Doppler",
                "Bone densitometry",
                "Scintigraphy",
            ],
            key="performed_tests",
        )

    with st.expander("4. Main symptoms"):
        symptom_1 = st.text_input("Symptom 1", key="symptom_1")
        symptom_1_since = st.text_input("Since when has symptom 1 been present?", key="symptom_1_since")
        symptom_2 = st.text_input("Symptom 2", key="symptom_2")
        symptom_2_since = st.text_input("Since when has symptom 2 been present?", key="symptom_2_since")
        symptom_3 = st.text_input("Symptom 3", key="symptom_3")
        symptom_3_since = st.text_input("Since when has symptom 3 been present?", key="symptom_3_since")
        symptom_4 = st.text_input("Symptom 4", key="symptom_4")
        symptom_4_since = st.text_input("Since when has symptom 4 been present?", key="symptom_4_since")
        symptom_5 = st.text_input("Symptom 5", key="symptom_5")
        symptom_5_since = st.text_input("Since when has symptom 5 been present?", key="symptom_5_since")
        additional_symptoms = st.text_area("Other symptoms, even if milder", key="additional_symptoms")

    with st.expander("5. Symptom pattern"):
        symptom_pattern = st.radio("Are the symptoms constant or periodic?", ["Constant", "Periodic", "Hard to say"], key="symptom_pattern")
        symptom_periodicity = st.text_area("If periodic, describe when they occur and how often during the year", key="symptom_periodicity")
        symptom_past = st.text_area("Have similar symptoms occurred before? If yes, when?", key="symptom_past")

        worsening_factors = st.multiselect(
            "What makes the symptoms worse?",
            ["Exercise", "Hunger", "Meal", "Speaking", "Laughing", "Other"],
            key="worsening_factors",
        )
        worsening_other = ""
        if "Other" in worsening_factors:
            worsening_other = st.text_input("If other, specify what makes the symptoms worse", key="worsening_other")

        improvement_factors = st.multiselect(
            "What improves or reduces the symptoms?",
            ["Rest", "Exercise", "Hunger", "Meal", "Other"],
            key="improvement_factors",
        )
        improvement_other = ""
        if "Other" in improvement_factors:
            improvement_other = st.text_input("If other, specify what improves the symptoms", key="improvement_other")

    with st.expander("6. Health timeline and medications"):
        health_timeline = st.text_area("Describe the course of your health problems from the beginning until today", key="health_timeline")
        current_meds = st.text_area("Current medications. Please include the name and dosage. Preferably one medication per line.", key="current_meds")

    with st.expander("7. Lifestyle"):
        lifestyle = select_with_placeholder(
            "Lifestyle",
            ["Bedridden", "Sedentary", "Low activity", "Moderately active", "Very active", "Other"],
            key="lifestyle",
        )
        stimulants = st.multiselect(
            "Substances and daily habits",
            ["Coffee", "Tea", "Cigarettes", "Alcohol", "Drugs", "Sweets", "Other"],
            key="stimulants",
        )
        stimulants_other = ""
        if "Other" in stimulants:
            stimulants_other = st.text_input("If other, specify", key="stimulants_other")
        sleep_hours = select_with_placeholder(
            "Average sleep duration per day",
            ["3", "4", "5", "6", "7", "8", "9", "10", "11", "12"],
            key="sleep_hours",
        )

    with st.expander("8. Travel"):
        travel_abroad = st.radio("Have you traveled abroad in the last 3 months?", ["Yes", "No"], key="travel_abroad")
        travel_where = ""
        if travel_abroad == "Yes":
            travel_where = st.text_input("If yes, where?", key="travel_where")

    with st.expander("9. Animals"):
        animal_contact = st.radio("Have you been bitten, scratched, or had close contact with an animal in recent months?", ["Yes", "No"], key="animal_contact")
        animal_contact_details = ""
        if animal_contact == "Yes":
            animal_contact_details = st.text_area("If yes, describe when and what animal", key="animal_contact_details")

    with st.expander("10. Injuries"):
        major_injuries = st.text_area("Have you had any major injuries? Please include year and description.", key="major_injuries")

    with st.expander("11. COVID-19"):
        covid = st.radio("Have you had COVID-19?", ["Yes", "No", "I do not know"], key="covid")
        covid_details = ""
        if covid == "Yes":
            covid_details = st.text_area("If yes, describe when and what the course was like", key="covid_details")

    with st.expander("12. Stress"):
        strong_stress = st.text_area("Have there been major stress reactions or difficult life events? If yes, describe and include the year.", key="strong_stress")

    with st.expander("13. Birth and childhood"):
        birth_info = st.multiselect(
            "Birth information",
            ["Natural delivery", "Cesarean section", "Premature birth", "Full-term birth", "Post-term birth", "Green amniotic fluid", "I do not know", "Other"],
            key="birth_info",
        )
        birth_info_other = ""
        if "Other" in birth_info:
            birth_info_other = st.text_input("If other, specify", key="birth_info_other")

        breastfeeding = select_with_placeholder(
            "Was there breastfeeding?",
            ["Yes, up to 3 months", "Yes, up to 6 months", "Yes, more than 6 months", "No", "I do not know"],
            key="breastfeeding",
        )

        childhood_diseases = st.multiselect(
            "Serious childhood conditions",
            ["Asthma", "Atopic dermatitis", "Cow's milk protein allergy", "Frequent colds", "Hospital stays", "Frequent pneumonia", "Intestinal problems", "Mental disorders", "Spleen problems", "Pancreatic problems", "Other"],
            key="childhood_diseases",
        )
        childhood_diseases_other = ""
        if "Other" in childhood_diseases:
            childhood_diseases_other = st.text_input("If other, specify", key="childhood_diseases_other")

    with st.expander("14. General and neurological symptoms"):
        fever_now = st.radio("Do you currently have a fever?", ["Yes", "No"], key="fever_now")
        fever_details = ""
        if fever_now == "Yes":
            fever_details = st.text_area("If yes, describe in more detail", key="fever_details")

        headache_dizziness = st.radio("Do you have headaches or dizziness?", ["Yes", "No"], key="headache_dizziness")
        headache_dizziness_details = ""
        if headache_dizziness == "Yes":
            headache_dizziness_details = st.text_area("If yes, describe in more detail", key="headache_dizziness_details")

        headache_assoc = st.text_area("Are headaches accompanied by vomiting, fainting, visual disturbances, weakness, light sensitivity or memory problems?", key="headache_assoc")
        hearing_vision = st.text_area("Has your hearing or vision worsened in recent years?", key="hearing_vision")
        attacks = st.text_area("Do you have attacks or sudden episodes? If yes, describe.", key="attacks")
        sinus_problems = st.text_area("Do you have sinus problems?", key="sinus_problems")
        nose_problems = st.text_area("Do you have nose problems, such as bleeding, dryness, inflammation, or difficulty breathing through the nose?", key="nose_problems")
        allergies = st.text_area("Do you have allergies? If yes, to what, during which season, and how severe?", key="allergies")
        herpes = st.text_area("Do you get cold sores? If yes, how often?", key="herpes")
        mouth_corners = st.text_area("Do you get cracks at the corners of the mouth?", key="mouth_corners")
        fresh_food_reaction = st.text_area("After eating fresh fruit or vegetables, do you experience burning or redness around the mouth?", key="fresh_food_reaction")
        epilepsy = st.radio("Have you ever been diagnosed with epilepsy?", ["Yes", "No"], key="epilepsy")
        smell_taste = st.text_area("Do you have smell or taste disturbances? If yes, since when?", key="smell_taste")
        colds = st.text_input("How often do you get colds during the year?", key="colds")

    with st.expander("15. Respiratory system"):
        throat_morning = st.radio("Do you have a sore throat in the morning?", ["Yes", "No"], key="throat_morning")
        esophagus_burning = st.radio("Do you experience burning in the esophagus?", ["Yes", "No"], key="esophagus_burning")
        asthma_dx = st.radio("Have you ever been diagnosed with asthma?", ["Yes", "No"], key="asthma_dx")
        pneumonia = st.radio("Have you ever had pneumonia?", ["Yes", "No"], key="pneumonia")
        pneumonia_details = ""
        if pneumonia == "Yes":
            pneumonia_details = st.text_area("If yes, provide the dates and which side of the lungs was affected", key="pneumonia_details")
        dyspnea = st.text_area("Do you experience shortness of breath? If yes, describe in what situations.", key="dyspnea")
        night_breath = st.text_area("Do you wake up at night due to shortness of breath?", key="night_breath")
        chest_heaviness = st.text_area("Do you experience heaviness in the chest? If yes, describe the severity.", key="chest_heaviness")
        breathing_type = select_with_placeholder(
            "Do you have difficulty breathing?",
            ["I do not have such difficulties", "Difficulty inhaling", "Difficulty exhaling", "Both"],
            key="breathing_type",
        )
        wheezing = st.multiselect(
            "Do you have wheezing?",
            ["No", "During exercise", "During infection", "At night", "In the morning", "During allergies", "In cold weather"],
            key="wheezing",
        )
        cough = st.text_area("Do you have a cough? If yes, since when, is it dry or productive, and what color is the sputum?", key="cough")

    with st.expander("16. Cardiovascular system"):
        chest_pain = st.text_area("Do you have chest pain? Is it localized or diffuse? Does it radiate anywhere?", key="chest_pain")
        pressure_type = select_with_placeholder(
            "Do you have blood pressure problems?",
            ["I do not have blood pressure problems", "I tend to have low blood pressure", "I tend to have high blood pressure"],
            key="pressure_type",
        )
        current_bp = st.text_input("What is your current blood pressure?", key="current_bp")
        current_hr = st.text_input("What is your current heart rate?", key="current_hr")
        pain_press = st.radio("Do you feel pain when pressing on the chest?", ["Yes", "No"], key="pain_press")
        pain_position = st.radio("Does chest pain occur when changing body position?", ["Yes", "No"], key="pain_position")
        palpitations = st.text_area("Do you experience irregular heartbeat? If yes, describe the time of day, circumstances and frequency.", key="palpitations")

    with st.expander("17. Gastrointestinal tract"):
        gi_problem = st.radio("Do you have gastrointestinal problems?", ["Yes", "No"], key="gi_problem")
        gi_symptoms = []
        if gi_problem == "Yes":
            gi_symptoms = st.multiselect(
                "Select symptoms",
                ["Heartburn", "Bloating", "Diarrhea", "Constipation", "Hemorrhoids", "Gas", "Cramps", "Vomiting", "Nausea"],
                key="gi_symptoms",
            )
        worsening_foods = st.text_area("Are there foods after which you feel worse?", key="worsening_foods")
        gi_infections = st.text_area("Have you ever had a bacterial or viral gastrointestinal infection? If yes, when, and was there a follow-up negative test?", key="gi_infections")

    with st.expander("18. Urinary system"):
        urine_problems = st.text_area("Do you have urinary problems, for example burning, difficulty urinating, or other issues?", key="urine_problems")
        night_urination = select_with_placeholder("How many times do you get up at night to urinate?", ["0", "1", "2", "3", "4", "5", "6", "7 or more"], key="night_urination")
        fluids = select_with_placeholder("How many liters of fluids do you drink per day?", ["1", "2", "3", "4", "5", "More than 5"], key="fluids")

    with st.expander("19. Joints and muscles"):
        joints = st.text_area("Do you have joint pain? If yes, which joints?", key="joints")
        stiffness = st.text_area("After getting out of bed, do you have pain or stiffness in the joints?", key="stiffness")

    with st.expander("20. Skin"):
        skin_changes = st.text_area("Do you have any skin changes? If yes, describe them in detail. When did they first appear? Since then, has there been improvement or worsening?", key="skin_changes")
        skin_itch = st.text_area("Do you have itchy skin? If yes, which parts of the body are affected?", key="skin_itch")
        acne = st.radio("Have you had or do you currently have significant acne on the face or back?", ["Yes", "No"], key="acne")
        acne_details = ""
        if acne == "Yes":
            acne_details = st.text_area("If yes, you may describe it in more detail", key="acne_details")
        skin_sensation = st.text_area("Do you have abnormal skin sensations? If yes, describe the location and since when.", key="skin_sensation")
        wound_healing = st.radio("Do you have problems with wound healing?", ["Yes", "No"], key="wound_healing")
        wound_healing_details = ""
        if wound_healing == "Yes":
            wound_healing_details = st.text_area("If yes, describe the wound healing problems", key="wound_healing_details")

    with st.expander("21. Sleep and mental health"):
        sleep_problem = st.radio("Do you have sleep problems?", ["Yes", "No"], key="sleep_problem")
        sleep_problem_types = []
        if sleep_problem == "Yes":
            sleep_problem_types = st.multiselect(
                "What kind of sleep problems do you have?",
                ["Difficulty falling asleep", "Waking up during the night", "Waking up tired", "Snoring", "Sleep too short", "Very deep sleep"],
                key="sleep_problem_types",
            )
        psych_contact = select_with_placeholder("Have you ever had an appointment with a psychologist or psychiatrist?", ["No", "Psychologist", "Psychiatrist", "Both"], key="psych_contact")
        psych_dx = st.text_area("Have you ever been diagnosed with a mental disorder? If yes, specify.", key="psych_dx")

    with st.expander("22. Peripheral circulation"):
        edema = st.radio("Do you have swelling in the lower legs or ankles?", ["Yes", "No"], key="edema")
        edema_details = ""
        if edema == "Yes":
            edema_details = st.text_area("If yes, describe whether it is constant or occurs after standing, sitting, or in other situations.", key="edema_details")
        calf_pain = st.text_area("Do you have calf pain when walking? If yes, after what distance and how quickly does it resolve?", key="calf_pain")
        cold_fingers = st.text_area("Do your fingers or toes get cold easily or change color?", key="cold_fingers")
        tingling = st.text_area("Do you have tingling or numbness in the hands or feet?", key="tingling")
        varicose = st.text_area("Do you have varicose veins?", key="varicose")

    with st.expander("23. Anal and perianal area"):
        anal_problems = st.multiselect(
            "Do you have any problems in the anal area?",
            ["No", "Hemorrhoids", "Inflammation of anal mucosa", "Burning", "Itching", "Fungal infection", "Other"],
            key="anal_problems",
        )
        anal_other = ""
        if "Other" in anal_problems:
            anal_other = st.text_input("If other, describe", key="anal_other")

    with st.expander("24. Gynecology or andrology"):
        gyn_problems = ""
        menstruation = ""
        first_menses = ""
        last_menses = None
        potency = ""

        if sex == "Female":
            gyn_problems = st.text_area("Do you have gynecological problems?", key="gyn_problems")
            menstruation = st.text_area("Do you have irregular menstruation, menopause, or hormonal treatment? If yes, since when?", key="menstruation")
            first_menses = st.text_input("Provide the month and year of your first menstruation", key="first_menses")
            last_menses = st.date_input(
                "Date of the last menstrual period",
                value=date.today(),
                min_value=date(1950, 1, 1),
                max_value=date.today(),
                key="last_menses",
            )
        elif sex == "Male":
            potency = select_with_placeholder("Do you have erectile dysfunction?", ["No", "Sometimes", "Often"], key="potency")

    with st.expander("25. Family history"):
        mother_history = st.text_area("What illnesses does or did your mother have?", key="mother_history")
        father_history = st.text_area("What illnesses does or did your father have?", key="father_history")
        maternal_grandmother = st.text_area("What illnesses does or did your maternal grandmother have?", key="maternal_grandmother")
        paternal_grandmother = st.text_area("What illnesses does or did your paternal grandmother have?", key="paternal_grandmother")
        maternal_grandfather = st.text_area("What illnesses does or did your maternal grandfather have?", key="maternal_grandfather")
        paternal_grandfather = st.text_area("What illnesses does or did your paternal grandfather have?", key="paternal_grandfather")

    with st.expander("26. Previous diagnoses, surgeries and important information"):
        own_diagnoses = st.text_area("Please list all previous diagnoses and surgeries", key="own_diagnoses")
        important_info = st.text_area("Is there any important information you would like to provide to the doctor?", key="important_info")
        current_reason = st.text_area("What is the reason for your current complaints or health problems?", key="current_reason")
        key_question = st.text_area("What is your most important question for the doctor or the most important issue to discuss during the visit?", key="key_question")

    with st.expander("27. Organizational information and consents", expanded=True):
        st.write("Please bring all available test results to the appointment. If needed, they may also be sent electronically later.")

        st.markdown('<div id="anchor_consent" class="field-anchor"></div>', unsafe_allow_html=True)
        consent_true = st.checkbox("I confirm that the information provided is true.", key="consent_true")
        consent_visit = st.checkbox("I consent to the use of this information solely for medical visit preparation.", key="consent_visit")
        consent_privacy = st.checkbox("I understand that this form is not stored in the application database.", key="consent_privacy")
        contact_consent = st.checkbox("I consent to phone or email contact regarding organizational matters related to the appointment.", key="contact_consent")

        if "consent" in field_errors:
            error_box(field_errors["consent"])

    progress_values = [
        visit_type, first_name, last_name, phone, email, birth_date, nationality, sex, current_status,
        profession, height_cm, weight_kg,
        physical_score, mental_score, weight_change, weight_change_amount,
        performed_tests,
        symptom_1, symptom_1_since, symptom_2, symptom_2_since, symptom_3, symptom_3_since,
        symptom_4, symptom_4_since, symptom_5, symptom_5_since, additional_symptoms,
        symptom_pattern, symptom_periodicity, symptom_past, worsening_factors, worsening_other,
        improvement_factors, improvement_other,
        health_timeline, current_meds,
        lifestyle, stimulants, stimulants_other, sleep_hours,
        travel_abroad, travel_where,
        animal_contact, animal_contact_details,
        major_injuries,
        covid, covid_details,
        strong_stress,
        birth_info, birth_info_other, breastfeeding, childhood_diseases, childhood_diseases_other,
        fever_now, fever_details, headache_dizziness, headache_dizziness_details, headache_assoc,
        hearing_vision, attacks, sinus_problems, nose_problems, allergies, herpes, mouth_corners,
        fresh_food_reaction, epilepsy, smell_taste, colds,
        throat_morning, esophagus_burning, asthma_dx, pneumonia, pneumonia_details, dyspnea,
        night_breath, chest_heaviness, breathing_type, wheezing, cough,
        chest_pain, pressure_type, current_bp, current_hr, pain_press, pain_position, palpitations,
        gi_problem, gi_symptoms, worsening_foods, gi_infections,
        urine_problems, night_urination, fluids,
        joints, stiffness,
        skin_changes, skin_itch, acne, acne_details, skin_sensation, wound_healing, wound_healing_details,
        sleep_problem, sleep_problem_types, psych_contact, psych_dx,
        edema, edema_details, calf_pain, cold_fingers, tingling, varicose,
        anal_problems, anal_other,
        gyn_problems, menstruation, first_menses, potency,
        mother_history, father_history, maternal_grandmother, paternal_grandmother, maternal_grandfather, paternal_grandfather,
        own_diagnoses, important_info, current_reason, key_question,
        consent_true, consent_visit, consent_privacy, contact_consent
    ]

    progress_percent = calc_progress(progress_values)

    st.markdown('<div class="send-button">', unsafe_allow_html=True)
    send_clicked = st.form_submit_button("Submit")
    st.markdown("</div>", unsafe_allow_html=True)

with progress_placeholder.container():
    st.markdown("<div class='progress-box'>", unsafe_allow_html=True)
    st.write(f"**Form completion progress: {progress_percent}%**")
    st.progress(progress_percent / 100)
    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# SUBMIT
# =========================================================
if send_clicked:
    st.session_state.field_errors = {}
    st.session_state.scroll_target = None

    first_name_clean = st.session_state.get("first_name", "").strip()
    last_name_clean = st.session_state.get("last_name", "").strip()
    phone_raw = st.session_state.get("phone", "").strip()
    email_clean = st.session_state.get("email", "").strip()
    validated_phone = validate_phone(phone_raw)

    if not first_name_clean:
        st.session_state.field_errors["first_name"] = "Please enter your first name."
    if not last_name_clean:
        st.session_state.field_errors["last_name"] = "Please enter your last name."
    if not validated_phone:
        st.session_state.field_errors["phone"] = "Please enter a valid phone number. It may include a country code or not."
    if not consent_true or not consent_visit or not consent_privacy:
        st.session_state.field_errors["consent"] = "Please check all required consents."

    anchor_order = [
        ("first_name", "anchor_first_name"),
        ("last_name", "anchor_last_name"),
        ("phone", "anchor_phone"),
        ("consent", "anchor_consent"),
    ]

    if st.session_state.field_errors:
        for field_key, anchor_id in anchor_order:
            if field_key in st.session_state.field_errors:
                st.session_state.scroll_target = anchor_id
                break
        st.rerun()

    submitted_at = datetime.now().strftime("%d.%m.%Y, %H:%M")
    main_symptoms_list = [x for x in [symptom_1, symptom_2, symptom_3, symptom_4, symptom_5] if nonempty(x)]

    pdf_data = {
        "first_name": first_name_clean,
        "last_name": last_name_clean,
        "phone": validated_phone,
        "email": email_clean,
        "birth_date": birth_date.strftime("%d.%m.%Y"),
        "visit_type": visit_type,
        "submitted_at": submitted_at,
        "sec_basic": [
            f"Nationality: {nationality}" if nonempty(nationality) else "",
            f"Sex: {sex}" if nonempty(sex) else "",
            f"Current status: {current_status}" if nonempty(current_status) else "",
            f"Current occupation: {profession}" if nonempty(profession) else "",
            f"Height: {height_cm} cm",
            f"Weight: {weight_kg} kg",
        ],
        "sec_overall": [
            f"Physical condition: {physical_score}/10",
            f"Mental condition: {mental_score}/10",
            f"Weight change: {weight_change}" + (f", approx. {weight_change_amount} kg" if nonempty(weight_change_amount) else ""),
        ],
        "sec_tests": [f"Performed tests: {list_text(performed_tests)}" if performed_tests else ""],
        "sec_main_symptoms": [
            f"Symptom 1: {symptom_1}" + (f" | since: {symptom_1_since}" if nonempty(symptom_1_since) else "") if nonempty(symptom_1) else "",
            f"Symptom 2: {symptom_2}" + (f" | since: {symptom_2_since}" if nonempty(symptom_2_since) else "") if nonempty(symptom_2) else "",
            f"Symptom 3: {symptom_3}" + (f" | since: {symptom_3_since}" if nonempty(symptom_3_since) else "") if nonempty(symptom_3) else "",
            f"Symptom 4: {symptom_4}" + (f" | since: {symptom_4_since}" if nonempty(symptom_4_since) else "") if nonempty(symptom_4) else "",
            f"Symptom 5: {symptom_5}" + (f" | since: {symptom_5_since}" if nonempty(symptom_5_since) else "") if nonempty(symptom_5) else "",
        ],
        "sec_other_symptoms": [additional_symptoms],
        "sec_symptom_character": [
            f"Pattern: {symptom_pattern}",
            f"Periodicity: {symptom_periodicity}" if nonempty(symptom_periodicity) else "",
            f"Similar symptoms in the past: {symptom_past}" if nonempty(symptom_past) else "",
            f"Worsening factors: {list_text(worsening_factors)}" if worsening_factors else "",
            f"Other worsening factors: {worsening_other}" if nonempty(worsening_other) else "",
            f"Improvement factors: {list_text(improvement_factors)}" if improvement_factors else "",
            f"Other improvement factors: {improvement_other}" if nonempty(improvement_other) else "",
        ],
        "sec_timeline_meds": [
            f"Health timeline: {health_timeline}" if nonempty(health_timeline) else "",
            "Current medications:" if nonempty(current_meds) else "",
            *[x for x in current_meds.splitlines() if x.strip()],
        ],
        "sec_lifestyle": [
            f"Lifestyle: {lifestyle}" if nonempty(lifestyle) else "",
            f"Substances and habits: {list_text(stimulants)}" if stimulants else "",
            f"Other substances: {stimulants_other}" if nonempty(stimulants_other) else "",
            f"Sleep duration: {sleep_hours} hours" if nonempty(sleep_hours) else "",
        ],
        "sec_travel": [f"Travel abroad in the last 3 months: {travel_abroad}" + (f", {travel_where}" if nonempty(travel_where) else "")],
        "sec_animals": [f"Animal contact: {animal_contact}" + (f", {animal_contact_details}" if nonempty(animal_contact_details) else "")],
        "sec_injuries": [major_injuries],
        "sec_covid": [f"COVID-19: {covid}" + (f", {covid_details}" if nonempty(covid_details) else "")],
        "sec_stress": [strong_stress],
        "sec_birth_childhood": [
            f"Birth information: {list_text(birth_info)}" if birth_info else "",
            f"Other birth information: {birth_info_other}" if nonempty(birth_info_other) else "",
            f"Breastfeeding: {breastfeeding}" if nonempty(breastfeeding) else "",
            f"Childhood conditions: {list_text(childhood_diseases)}" if childhood_diseases else "",
            f"Other childhood conditions: {childhood_diseases_other}" if nonempty(childhood_diseases_other) else "",
        ],
        "sec_general_neuro": [
            f"Fever: {fever_now}" + (f", {fever_details}" if nonempty(fever_details) else ""),
            f"Headaches or dizziness: {headache_dizziness}" + (f", {headache_dizziness_details}" if nonempty(headache_dizziness_details) else ""),
            f"Associated headache symptoms: {headache_assoc}" if nonempty(headache_assoc) else "",
            f"Hearing or vision worsening: {hearing_vision}" if nonempty(hearing_vision) else "",
            f"Attacks or sudden episodes: {attacks}" if nonempty(attacks) else "",
            f"Sinus problems: {sinus_problems}" if nonempty(sinus_problems) else "",
            f"Nose problems: {nose_problems}" if nonempty(nose_problems) else "",
            f"Allergies: {allergies}" if nonempty(allergies) else "",
            f"Cold sores: {herpes}" if nonempty(herpes) else "",
            f"Cracks at the corners of the mouth: {mouth_corners}" if nonempty(mouth_corners) else "",
            f"Reaction after fresh fruit or vegetables: {fresh_food_reaction}" if nonempty(fresh_food_reaction) else "",
            f"Epilepsy: {epilepsy}",
            f"Smell or taste disturbances: {smell_taste}" if nonempty(smell_taste) else "",
            f"Frequency of colds: {colds}" if nonempty(colds) else "",
        ],
        "sec_respiratory": [
            f"Sore throat in the morning: {throat_morning}",
            f"Burning in the esophagus: {esophagus_burning}",
            f"Diagnosed asthma: {asthma_dx}",
            f"Pneumonia: {pneumonia}" + (f", {pneumonia_details}" if nonempty(pneumonia_details) else ""),
            f"Shortness of breath: {dyspnea}" if nonempty(dyspnea) else "",
            f"Waking at night due to shortness of breath: {night_breath}" if nonempty(night_breath) else "",
            f"Chest heaviness: {chest_heaviness}" if nonempty(chest_heaviness) else "",
            f"Breathing difficulty: {breathing_type}" if nonempty(breathing_type) else "",
            f"Wheezing: {list_text(wheezing)}" if wheezing else "",
            f"Cough: {cough}" if nonempty(cough) else "",
        ],
        "sec_cardio": [
            f"Chest pain: {chest_pain}" if nonempty(chest_pain) else "",
            f"Blood pressure problems: {pressure_type}" if nonempty(pressure_type) else "",
            f"Current blood pressure: {current_bp}" if nonempty(current_bp) else "",
            f"Current heart rate: {current_hr}" if nonempty(current_hr) else "",
            f"Pain on palpation of the chest: {pain_press}",
            f"Pain with change of body position: {pain_position}",
            f"Palpitations: {palpitations}" if nonempty(palpitations) else "",
        ],
        "sec_gi": [
            f"Gastrointestinal problems: {gi_problem}",
            f"Symptoms: {list_text(gi_symptoms)}" if gi_symptoms else "",
            f"Foods that worsen symptoms: {worsening_foods}" if nonempty(worsening_foods) else "",
            f"Previous GI infections: {gi_infections}" if nonempty(gi_infections) else "",
        ],
        "sec_urinary": [
            f"Urinary problems: {urine_problems}" if nonempty(urine_problems) else "",
            f"Night urination count: {night_urination}" if nonempty(night_urination) else "",
            f"Fluid intake: {fluids} liters" if nonempty(fluids) else "",
        ],
        "sec_msk": [
            f"Joint pain: {joints}" if nonempty(joints) else "",
            f"Pain or stiffness after getting out of bed: {stiffness}" if nonempty(stiffness) else "",
        ],
        "sec_skin": [
            f"Skin changes: {skin_changes}" if nonempty(skin_changes) else "",
            f"Itchy skin: {skin_itch}" if nonempty(skin_itch) else "",
            f"Acne: {acne}" + (f", {acne_details}" if nonempty(acne_details) else ""),
            f"Abnormal skin sensations: {skin_sensation}" if nonempty(skin_sensation) else "",
            f"Wound healing problems: {wound_healing}" + (f", {wound_healing_details}" if nonempty(wound_healing_details) else ""),
        ],
        "sec_sleep_psych": [
            f"Sleep problems: {sleep_problem}",
            f"Types of sleep problems: {list_text(sleep_problem_types)}" if sleep_problem_types else "",
            f"Psychologist or psychiatrist contact: {psych_contact}" if nonempty(psych_contact) else "",
            f"Mental disorder diagnosis: {psych_dx}" if nonempty(psych_dx) else "",
        ],
        "sec_peripheral": [
            f"Lower leg or ankle swelling: {edema}" + (f", {edema_details}" if nonempty(edema_details) else ""),
            f"Calf pain when walking: {calf_pain}" if nonempty(calf_pain) else "",
            f"Cold fingers or toes / discoloration: {cold_fingers}" if nonempty(cold_fingers) else "",
            f"Tingling or numbness: {tingling}" if nonempty(tingling) else "",
            f"Varicose veins: {varicose}" if nonempty(varicose) else "",
        ],
        "sec_anal": [
            f"Anal area problems: {list_text(anal_problems)}" if anal_problems else "",
            f"Other anal area problems: {anal_other}" if nonempty(anal_other) else "",
        ],
        "sec_sex_specific": [
            f"Gynecological problems: {gyn_problems}" if nonempty(gyn_problems) else "",
            f"Menstruation / menopause / hormonal treatment: {menstruation}" if nonempty(menstruation) else "",
            f"First menstruation: {first_menses}" if nonempty(first_menses) else "",
            f"Last menstrual period: {safe(last_menses)}" if nonempty(last_menses) else "",
            f"Erectile dysfunction: {potency}" if nonempty(potency) else "",
        ],
        "sec_family": [
            f"Mother: {mother_history}" if nonempty(mother_history) else "",
            f"Father: {father_history}" if nonempty(father_history) else "",
            f"Maternal grandmother: {maternal_grandmother}" if nonempty(maternal_grandmother) else "",
            f"Paternal grandmother: {paternal_grandmother}" if nonempty(paternal_grandmother) else "",
            f"Maternal grandfather: {maternal_grandfather}" if nonempty(maternal_grandfather) else "",
            f"Paternal grandfather: {paternal_grandfather}" if nonempty(paternal_grandfather) else "",
        ],
        "sec_history_final": [
            f"Previous diagnoses and surgeries: {own_diagnoses}" if nonempty(own_diagnoses) else "",
            f"Important information for the doctor: {important_info}" if nonempty(important_info) else "",
            f"Current reason for complaints: {current_reason}" if nonempty(current_reason) else "",
        ],
        "sec_question": [
            f"Most important question: {key_question}" if nonempty(key_question) else "",
        ],
    }

    try:
        pdf_path = make_pdf(pdf_data)

        subject = f"Medical Interview Report - {first_name_clean} {last_name_clean}"
        body_lines = [
            "Attached is the medical interview report.",
            "",
            f"Patient: {first_name_clean} {last_name_clean}",
            f"Phone: {validated_phone}",
            f"Email: {email_clean}",
            f"Visit type: {visit_type}",
            f"Submission date: {submitted_at}",
        ]
        body_text = "\n".join(body_lines)

        email_sent = False
        email_error = ""

        try:
            send_email_with_pdf(subject, body_text, pdf_path)
            email_sent = True
        except Exception as mail_exc:
            email_error = str(mail_exc)

        st.success("The form has been submitted successfully. The PDF report has been generated.")

        if email_sent:
            st.success("The PDF report has been sent by email.")
        else:
            st.warning(f"The PDF was generated, but the email was not sent: {email_error}")

        st.markdown("<div class='summary-box'>", unsafe_allow_html=True)
        st.write("### Summary")
        st.write(f"**Patient:** {first_name_clean} {last_name_clean}")
        st.write(f"**Phone number:** {validated_phone}")
        st.write(f"**Email:** {email_clean}")
        st.write(f"**Visit type:** {visit_type}")
        st.write(f"**Main symptoms:** {', '.join(main_symptoms_list) if main_symptoms_list else 'No main symptoms entered'}")
        st.write(f"**Current reason:** {current_reason if nonempty(current_reason) else 'Not provided'}")
        st.write(f"**Most important question:** {key_question if nonempty(key_question) else 'Not provided'}")
        st.markdown("</div>", unsafe_allow_html=True)

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        st.download_button(
            "Download PDF report",
            data=pdf_bytes,
            file_name="medical_interview_report.pdf",
            mime="application/pdf",
        )

    except Exception as e:
        st.error(f"An error occurred while generating or sending the PDF: {e}")

if st.session_state.scroll_target:
    scroll_to_anchor(st.session_state.scroll_target)
