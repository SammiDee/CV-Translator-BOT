import streamlit as st
from openai import OpenAI
import PyPDF2
import os
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
import streamlit.components.v1 as components
from io import BytesIO
from fpdf import FPDF
import re

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Set up the page
st.set_page_config(page_title="CV Translator", page_icon="🌐")

st.title("🌐 CV Translator / Traducteur de CV")

# Session state
if "original_cv" not in st.session_state:
    st.session_state.original_cv = ""
if "translated_cv" not in st.session_state:
    st.session_state.translated_cv = ""
if "detected_language" not in st.session_state:
    st.session_state.detected_language = ""
if "target_language" not in st.session_state:
    st.session_state.target_language = "fr"  # Default to French
if "translation_done" not in st.session_state:
    st.session_state.translation_done = False
if "parsed_cv_sections" not in st.session_state:
    st.session_state.parsed_cv_sections = {}

# Default language fallback
INTERFACE_LANGUAGE = "fr"

# Helper functions
def extract_text(uploaded_file):
    if uploaded_file.type == "application/pdf":
        reader = PyPDF2.PdfReader(uploaded_file)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    else:
        return uploaded_file.read().decode("utf-8", errors="ignore")

def detect_language(text):
    try:
        detected = detect(text[:1000])
        print(f"Detected language: {detected}")
        return detected
    except LangDetectException:
        print(f"Language detection failed, using default: {INTERFACE_LANGUAGE}")
        return INTERFACE_LANGUAGE

def get_language_code(lang):
    mapping = {
        "en": "en-US",
        "fr": "fr-FR",
        "es": "es-ES",
        "ar": "ar-SA",
        "de": "de-DE",
        "pt": "pt-PT",
        "it": "it-IT",
        "ru": "ru-RU"
    }
    return mapping.get(lang, "en-US")

def get_language_name(lang_code):
    mapping = {
        "en": "English",
        "fr": "French",
        "es": "Spanish",
        "ar": "Arabic",
        "de": "German",
        "pt": "Portuguese",
        "it": "Italian",
        "ru": "Russian"
    }
    return mapping.get(lang_code, "Unknown")

def parse_cv_content(content):
    """Parse CV content into sections with improved section detection"""
    lines = content.split("\n")
    sections = {}
    current_section = "header"
    sections[current_section] = []
    
    # Regular expressions for section detection
    section_patterns = [
        re.compile(r'^\s*\*{2}([^*]+)\*{2}\s*$'),  # **Section**
        re.compile(r'^\s*[A-Z\s]{5,}\s*$'),        # UPPERCASE SECTIONS
        re.compile(r'^\s*-{3,}\s*([^-]+)\s*-{3,}\s*$')  # ---Section---
    ]
    
    # Process the content line by line
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Check if this line is a section header
        is_section_header = False
        section_name = None
        
        # Test against all patterns
        for pattern in section_patterns:
            match = pattern.match(line)
            if match:
                try:
                    section_name = match.group(1).strip().lower()
                    is_section_header = True
                except:
                    # If no capture group, use the full line
                    section_name = line.strip('* -').strip().lower()
                    is_section_header = True
                break
        
        # If line starts with ** and ends with **, it's likely a section
        if line.startswith('**') and line.endswith('**'):
            section_name = line.strip('*').strip().lower()
            is_section_header = True
        
        if is_section_header and section_name:
            current_section = section_name
            if current_section not in sections:
                sections[current_section] = []
        else:
            # Add the line to the current section
            sections[current_section].append(line)
    
    # Convert lists to strings
    for section in sections:
        sections[section] = "\n".join(sections[section])
    
    # Special handling to identify header section properly
    # If we don't have a clear header section, create one from the first few lines
    if "header" in sections and not sections["header"].strip():
        # Find first non-empty section
        for section in sections:
            if sections[section].strip():
                first_lines = sections[section].split("\n")[:5]
                sections["header"] = "\n".join(first_lines)
                # Remove these lines from the original section
                sections[section] = "\n".join(sections[section].split("\n")[5:])
                break
    
    # Clean up empty sections
    sections = {k: v for k, v in sections.items() if v.strip()}
    
    # Ensure we have the common sections
    common_sections = ["header", "profile", "experience", "education", "skills", "languages"]
    for section in common_sections:
        variant_found = False
        # Check if we have any section that could match (e.g., "expérience" for "experience")
        for existing_section in list(sections.keys()):
            # Check if the existing section contains the common section name
            if section in existing_section.lower() or existing_section in section:
                variant_found = True
                # Rename to standard name if needed
                if existing_section != section:
                    sections[section] = sections.pop(existing_section)
                break
        
        # If no variant was found, add an empty section
        if not variant_found and section not in sections:
            sections[section] = ""
    
    return sections

def create_cv_pdf(content, filename="translated_cv.pdf"):
    """Create a professionally formatted CV PDF with improved styling"""
    
    # Parse the CV content into sections
    sections = parse_cv_content(content)
    
    # Create PDF instance with word wrap capability
    class PDF(FPDF):
        def header(self):
            # We'll handle the header manually in the content
            pass
            
        def footer(self):
            # Add page numbers
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
        
        # Add a multi-cell method that checks width first
        def safe_multi_cell(self, w, h, txt, border=0, align='J', fill=False):
            # Get the current position
            x = self.get_x()
            y = self.get_y()
            
            # Set a smaller font if the text is too long for a single line
            if self.get_string_width(txt) > (self.w - 2*self.l_margin):
                self.multi_cell(w, h, txt, border, align, fill)
            else:
                self.cell(w, h, txt, border, 1, align, fill)
    
    # Initialize PDF
    pdf = PDF()
    pdf.add_page()
    
    # Set margins - smaller margins to accommodate more text
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Set default font size smaller
    default_font_size = 9  # Reduced from 10
    
    # Color definitions
    header_color = (50, 50, 50)  # Dark gray
    section_color = (0, 102, 204)  # Professional blue
    text_color = (0, 0, 0)  # Black
    subheader_color = (80, 80, 80)  # Medium gray
    
    # Extract name and contact details from header section
    name = ""
    contact_info = []
    
    if "header" in sections and sections["header"]:
        header_lines = sections["header"].split("\n")
        if header_lines:
            # First line is likely the name
            name = header_lines[0].strip('*').strip()
            # Rest are contact details
            contact_info = [line.strip() for line in header_lines[1:] if line.strip()]
    
    # Add name as header
    pdf.set_font("Arial", "B", 16)  # Slightly smaller header
    pdf.set_text_color(*header_color)
    pdf.cell(0, 10, name, ln=True, align="C")
    
    # Add contact info
    pdf.set_font("Arial", "", default_font_size)
    pdf.set_text_color(*text_color)
    
    # Display contact info in a more compact format
    contact_text = " | ".join([info for info in contact_info if info])
    # Use multi_cell for wrapping long contact information
    pdf.multi_cell(0, 5, contact_text, align='C')
    
    # Add spacing after header
    pdf.ln(5)
    
    # Process other sections
    for section_name, section_content in sections.items():
        # Skip header as we've already processed it
        if section_name == "header" or not section_content.strip():
            continue
            
        # Convert common section names to proper display names
        section_display_name = section_name.upper()
        
        # Add section header with blue background
        pdf.set_fill_color(*section_color)
        pdf.set_text_color(255, 255, 255)  # White text
        pdf.set_font("Arial", "B", 11)  # Smaller section headers
        pdf.cell(0, 7, " " + section_display_name, ln=True, fill=True)
        pdf.set_text_color(*text_color)  # Reset text color
        pdf.ln(1)  # Less spacing
        
        # Split section content into items (paragraphs separated by blank lines)
        items = re.split(r'\n\s*\n', section_content)
        
        for item in items:
            if not item.strip():
                continue
                
            lines = item.split("\n")
            
            # First line of each item might be a title/position/date
            if lines:
                # Check if the first line looks like a title or position (no bullet point)
                first_line = lines[0].strip()
                if not first_line.startswith("-") and not first_line.startswith("•"):
                    pdf.set_font("Arial", "B", 10)  # Slightly smaller
                    pdf.set_text_color(*subheader_color)
                    
                    # Use multi_cell for potentially long titles
                    pdf.multi_cell(0, 5, first_line)
                    
                    pdf.set_text_color(*text_color)
                    pdf.set_font("Arial", "", default_font_size)
                    lines = lines[1:]
            
            # Process remaining lines - handle bullet points with word wrapping
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Truncate extremely long lines to prevent overflow
                max_line_length = 120  # Maximum characters per line
                if len(line) > max_line_length:
                    line = line[:max_line_length] + "..."
                
                # Check if line is a bullet point
                if line.startswith("-") or line.startswith("•"):
                    # Keep bullet point and indent
                    bullet = line[0]
                    bullet_text = line[1:].strip()
                    
                    # Use MultiCell for text wrapping
                    current_x = pdf.get_x()
                    current_y = pdf.get_y()
                    
                    # Add bullet
                    pdf.set_xy(current_x, current_y)
                    pdf.cell(3, 4, bullet)
                    
                    # Add text with wrapping
                    pdf.set_xy(current_x + 5, current_y)
                    pdf.multi_cell(0, 4, bullet_text)
                else:
                    # Regular line - use multi_cell for text wrapping
                    pdf.multi_cell(0, 4, line)
            
            pdf.ln(2)  # Less space between items
        
        pdf.ln(3)  # Less space between sections
    
    # Save PDF to BytesIO buffer
    pdf_buffer = BytesIO()
    pdf_buffer.write(pdf.output(dest="S").encode('latin-1'))
    pdf_buffer.seek(0)
    return pdf_buffer

# File upload section
st.header("1️⃣ Upload your CV / Téléverser votre CV")
uploaded_file = st.file_uploader("Upload a PDF or TXT file / Téléverser un fichier PDF ou TXT", type=["pdf", "txt"])

if uploaded_file:
    # Extract text from the uploaded file
    st.session_state.original_cv = extract_text(uploaded_file)
    
    # Detect language
    st.session_state.detected_language = detect_language(st.session_state.original_cv)
    detected_language_name = get_language_name(st.session_state.detected_language)
    
    # Parse the CV into sections for better processing
    st.session_state.parsed_cv_sections = parse_cv_content(st.session_state.original_cv)
    
    st.success(f"CV uploaded successfully! Detected language: {detected_language_name}")
    
    # Show a preview of the original CV
    with st.expander("Preview Original CV"):
        st.text_area("Original CV Content", st.session_state.original_cv, height=300)

# Language selection
st.header("2️⃣ Select Target Language / Sélectionner la langue cible")
target_language = st.radio(
    "Choose translation language / Choisir la langue de traduction:",
    ["English", "French / Français"],
    horizontal=True
)

# Map selection to language code
if target_language == "English":
    st.session_state.target_language = "en"
else:
    st.session_state.target_language = "fr"

# Translation button
if st.session_state.original_cv and st.button("🔄 Translate CV / Traduire le CV"):
    target_language_name = "English" if st.session_state.target_language == "en" else "French"
    st.info(f"Translating your CV to {target_language_name}... This may take a moment.")
    
    # Build a better prompt that helps preserve formatting
    prompt = f"""
    Translate the following CV from {get_language_name(st.session_state.detected_language)} to {target_language_name}.
    Maintain the professional CV format, structure, and section headers.
    
    Rules for translation:
    1. Preserve all formatting characters like **, --, and bullet points (- or •)
    2. Keep section titles clearly marked (with ** or similar formatting)
    3. Ensure job titles, skills, and educational qualifications are accurately translated
    4. Maintain the same number of bullet points and similar length for each point
    5. Preserve formatting of dates, locations, and company names
    6. Do not add or remove information, just translate it accurately
    
    CV to translate:
    {st.session_state.original_cv}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000
        )
        
        st.session_state.translated_cv = response.choices[0].message.content
        st.session_state.translation_done = True
        st.success("Translation complete!")
    except Exception as e:
        st.error(f"Translation error: {str(e)}")

# Display and edit translated CV
if st.session_state.translation_done:
    st.header("3️⃣ Edit Translated CV / Modifier le CV traduit")
    
    edited_cv = st.text_area(
        "Edit your translated CV / Modifier votre CV traduit",
        st.session_state.translated_cv,
        height=500
    )
    
    # Update the translation in session state if edited
    if edited_cv != st.session_state.translated_cv:
        st.session_state.translated_cv = edited_cv
        # Also update parsed sections
        st.session_state.parsed_cv_sections = parse_cv_content(edited_cv)
    
    # Generate and download PDF
    st.header("4️⃣ Download CV / Télécharger le CV")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📄 Download as PDF / Télécharger en PDF"):
            pdf_buffer = create_cv_pdf(st.session_state.translated_cv)
            target_lang_name = "English" if st.session_state.target_language == "en" else "French"
            st.download_button(
                label=f"Download {target_lang_name} CV PDF",
                data=pdf_buffer,
                file_name="translated_cv.pdf",
                mime="application/pdf"
            )
    
    with col2:
        # Preview PDF button
        if st.button("👁️ Preview PDF / Aperçu PDF"):
            # Create the PDF
            pdf_buffer = create_cv_pdf(st.session_state.translated_cv)
            
            # Display PDF directly in the app using an iframe
            # First, save the PDF to a temporary file
            import tempfile
            import base64
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(pdf_buffer.getvalue())
                tmp_path = tmp.name
            
            # Display PDF using base64 encoding to embed in HTML
            with open(tmp_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
            
            # Display PDF with PDF.js viewer
            pdf_display = f'''
                <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500" type="application/pdf"></iframe>
            '''
            st.markdown(pdf_display, unsafe_allow_html=True)
            
            # Also provide download button
            st.download_button(
                label="Download This Preview / Télécharger cet aperçu",
                data=pdf_buffer,
                file_name="preview_cv.pdf",
                mime="application/pdf",
                key="preview_download"
            )
    
    # Read aloud section
    st.subheader("🗣️ Listen to your CV / Écouter votre CV")
    
    # Add speech rate control
    speech_rate = st.slider("Speed / Vitesse:", min_value=0.5, max_value=1.5, value=0.8, step=0.1)
    
    # Clean text for speech synthesis
    clean_text = st.session_state.translated_cv.replace("\n", " ").replace('"', '\\"')
    
    # Get appropriate language code for speech
    lang_code = get_language_code(st.session_state.target_language)
    
    components.html(f"""
        <script>
            let utterance;
            function speak() {{
                if (utterance) window.speechSynthesis.cancel();
                
                // Debug language support
                console.log("Available voices:");
                let voices = window.speechSynthesis.getVoices();
                voices.forEach(voice => console.log(voice.name + " (" + voice.lang + ")"));
                
                utterance = new SpeechSynthesisUtterance("{clean_text}");
                
                // Set speech rate
                utterance.rate = {speech_rate};
                console.log("Speech rate set to: {speech_rate}");
                
                // For French, explicitly set fr-FR
                const targetLang = "{st.session_state.target_language}";
                if (targetLang === "fr") {{
                    utterance.lang = "fr-FR";
                    console.log("Setting French voice: fr-FR");
                    
                    // Try to find a French voice
                    const frenchVoices = voices.filter(voice => voice.lang.startsWith('fr'));
                    if (frenchVoices.length > 0) {{
                        utterance.voice = frenchVoices[0];
                        console.log("Found French voice: " + frenchVoices[0].name);
                    }}
                }} else {{
                    utterance.lang = "{lang_code}";
                    console.log("Using language code: " + "{lang_code}");
                }}
                
                window.speechSynthesis.speak(utterance);
            }}
            function stopSpeech() {{
                window.speechSynthesis.cancel();
            }}
        </script>
        <button onclick="speak()" style="padding: 8px 16px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px;">
            ▶️ Read Aloud / Lire à voix haute
        </button>
        <button onclick="stopSpeech()" style="padding: 8px 16px; background-color: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer;">
            ⏹️ Stop
        </button>
    """, height=100)

# Show instructions in the sidebar
with st.sidebar:
    st.header("How to use this app / Comment utiliser cette application")
    st.markdown("""
    **English Instructions:**
    1. Upload your CV in any language (PDF or TXT)
    2. Select target language (English or French)
    3. Click "Translate CV" to generate the translation
    4. Edit the translated CV if needed
    5. Preview the PDF formatting before downloading
    6. Download the final CV as a professionally formatted PDF
    
    **Instructions en français:**
    1. Téléversez votre CV dans n'importe quelle langue (PDF ou TXT)
    2. Sélectionnez la langue cible (anglais ou français)
    3. Cliquez sur "Traduire le CV" pour générer la traduction
    4. Modifiez le CV traduit si nécessaire
    5. Prévisualisez le formatage PDF avant de télécharger
    6. Téléchargez le CV final au format PDF professionnel
    """)
    
    # Add tips for better results
    st.subheader("Tips for better results / Conseils pour de meilleurs résultats")
    st.markdown("""
    **English:**
    - Make sure section titles are clearly marked (e.g., **Experience**)
    - Use bullet points (- or •) for listing responsibilities and achievements
    - After translation, check specialized terminology for accuracy
    
    **Français:**
    - Assurez-vous que les titres de sections sont clairement marqués (par ex., **Expérience**)
    - Utilisez des puces (- ou •) pour énumérer les responsabilités et réalisations
    - Après la traduction, vérifiez la terminologie spécialisée pour son exactitude
    """)