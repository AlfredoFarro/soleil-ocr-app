import streamlit as st
from google import genai
import pathlib
import os
import tempfile
import json
import time
from pathlib import Path
import base64

def show_logo():
    for name in ("logo_soleil.png", "logo_soleil.jpg"):
        p = Path(__file__).with_name(name)
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            ext = p.suffix[1:].lower()  # png o jpg
            st.markdown(
                f"""
                <div class="logo-container">
                    <img src="data:image/{ext};base64,{b64}" alt="Soleil Metals Logo">
                </div>
                """,
                unsafe_allow_html=True
            )
            return True
    st.warning("No encuentro el logo. Coloca 'logo_soleil.png' o 'logo_soleil.jpg' junto al .py")
    return False

# ----------------------------------------------------------------------
# PASO 1: REEMPLAZA ESTA CADENA CON TU CLAVE DE API REAL
# ATENCIÓN: ¡Esto expone tu clave de API! Úsalo solo para pruebas locales.
# ----------------------------------------------------------------------
# ⚠️ SOLO PARA PRUEBAS LOCALES — NO SUBAS ESTA CLAVE A GITHUB ⚠️
#GEMINI_API_KEY_DIRECTA = "AIzaSyDQDKaaDFdVQrUvHs6sEhunwQJQqjnWLgM"  # reemplaza por tu clave real
GEMINI_API_KEY_DIRECTA = os.getenv("GEMINI_API_KEY")
try:
    client = genai.Client(api_key=GEMINI_API_KEY_DIRECTA)
except Exception as e:
    st.error(f"Error al inicializar el cliente Gemini: {e}")
    client = None


# --- Función de OCR con Gemini ---

def ocr_gemini(file_path, document_type):
    """
    Usa la API de Gemini para extraer texto, con clasificación condicional 
    y extracción estructurada (JSON) para DNI y Tarjeta de Propiedad (ambos lados).
    """
    if not client:
        return "ERROR: Cliente Gemini no inicializado. Revisa la clave de API."

    try:
        # 1. Cargar el archivo al servicio de Gemini
        with st.spinner(f"Subiendo archivo y procesando '{document_type}'..."):
            
            uploaded_file = client.files.upload(file=file_path) 
            
            # --- Lógica del Prompt Condicional ---
            
            if document_type == "DNI":
                # PROMPT CORREGIDO PARA DNI (Evita alucinaciones de ubicación)
                prompt = """
                *INSTRUCCIÓN:* Analiza la imagen adjunta. Esta puede contener la cara frontal del DNI, la cara trasera, o ambas en una misma foto.

                1. *CLASIFICACIÓN:* Determina si el documento es un DNI peruano (incluyendo DNI electrónico).
                2. *SALIDA CONDICIONAL:*
                    * *SI ES DNI:* Extrae *TODOS* los campos solicitados. *Si algún campo (como Departamento, Provincia, Distrito o Dirección) no es visible o se encuentra en el reverso del DNI y este no está presente, usa estrictamente una cadena vacía ("") para ese campo. NO ADIVINES O INFIERAS UBICACIONES.* Devuelve los campos *EXCLUSIVAMENTE* en el FORMATO JSON requerido.
                    * *SI NO ES DNI:* Devuelve *EXCLUSIVAMENTE* la cadena de texto: "No es del tipo del documento seleccionado".

                *CAMPOS JSON (Solo si es DNI):* {"tipo_documento": "DNI/DNIe", "numero_dni": "...", "apellido_paterno": "...", "apellido_materno": "...", "nombres": "...", "fecha_nacimiento": "DD/MM/AAAA", "fecha_emision": "DD/MM/AAAA", "fecha_caducidad": "DD/MM/AAAA", "estado_civil": "...", "sexo": "...", "departamento": "...", "provincia": "...", "distrito": "...", "direccion_completa": "..."}

                *IMPORTANTE:* No incluyas explicaciones, markdown extra o texto fuera del JSON o la frase de error.
                """
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[prompt, uploaded_file],
                    config={"response_mime_type": "application/json"} 
                )

            elif document_type == "Tarjeta de Propiedad":
                # --- PROMPT UNIFICADO Y CORREGIDO PARA TARJETA DE PROPIEDAD (FRONTAL Y TRASERO) ---
                prompt = """
                *INSTRUCCIÓN:* Analiza la imagen adjunta. Puede ser la parte frontal (anverso) o trasera (reverso) de una Tarjeta de Identificación Vehicular peruana (SUNARP), o ambas.

                1. *CLASIFICACIÓN:* Determina si el documento es una Tarjeta de Identificación Vehicular de Perú.
                2. *SALIDA CONDICIONAL:*
                    * *SI ES TARJETA DE PROPIEDAD:* Extrae *TODOS* los campos solicitados de cualquiera de los lados (frontal o trasero) que sean visibles. *Si algún campo (como Nombres, Domicilio, o DUA/DAM) no es visible o se encuentra en el lado opuesto de la tarjeta y este no está presente, usa estrictamente una cadena vacía ("") para ese campo. NO ADIVINES O INFIERAS DATOS.* Devuelve los campos *EXCLUSIVAMENTE* en el FORMATO JSON requerido.
                    * *SI NO ES TARJETA DE PROPIEDAD:* Devuelve *EXCLUSIVAMENTE* la cadena de texto: "No es del tipo del documento seleccionado".

                *CAMPOS JSON (Ambos lados):* {
                    "tipo_documento": "Tarjeta de Propiedad", 
                    "placa_no": "...", 
                    "partida_registral": "...", 
                    "titulo_frontal": "...", 
                    "fecha_titulo_frontal": "...", 
                    "condicion": "...", 
                    "tipo_de_prop": "...", 
                    "denominacion": "...",
                    "apellido_paterno": "...", 
                    "apellido_materno": "...", 
                    "nombres": "...", 
                    "fecha_adq": "...", 
                    "exp_tarj": "...", 
                    "vig_temp": "...", 
                    "domicilio": "...",
                    "zona_registral_no": "...",
                    "oficina_registral": "...",
                    "placa_ant": "...",
                    "dua_dam": "...",
                    "titulo_reverso": "...",
                    "fecha_del_titulo_reverso": "..."
                }

                *IMPORTANTE:* No incluyas explicaciones, markdown extra o texto fuera del JSON o la frase de error.
                """
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[prompt, uploaded_file],
                    config={"response_mime_type": "application/json"} 
                )

            # -------------------------------------------------------------
            # NUEVO BLOQUE: TARJETA DE IDENTIFICACIÓN VEHICULAR ELECTRÓNICA
            # -------------------------------------------------------------
            elif document_type == "Tarjeta de Identificación":
                prompt = """
                *INSTRUCCIÓN:* Analiza la imagen adjunta. Esta contiene una Tarjeta de Identificación Vehicular Electrónica (TIVE) de SUNARP (Perú).

                1. *CLASIFICACIÓN:* Determina si el documento es una Tarjeta de Identificación Vehicular Electrónica de SUNARP.
                2. *SALIDA CONDICIONAL:*
                    * *SI ES TIVE:* Extrae *TODOS* los campos solicitados. Si algún campo no es visible, usa estrictamente una cadena vacía ("") para ese campo. NO ADIVINES O INFIERAS DATOS. Devuelve los campos *EXCLUSIVAMENTE* en el FORMATO JSON requerido.
                    * *SI NO ES TIVE:* Devuelve *EXCLUSIVAMENTE* la cadena de texto: "No es del tipo del documento seleccionado".

                *CAMPOS JSON (TIVE):* {
                    "tipo_documento": "Tarjeta de Identificación Vehicular",
                    "codigo_verificacion": "...",
                    "titulo_no": "...",
                    "fecha_titulo": "DD/MM/AAAA",
                    "placa_no": "...",
                    "partida_registral": "...",
                    "zona_registral_no": "...",
                    "sede_registral": "...",
                    "dua_dam": "...",
                    "categoria": "...",
                    "marca": "...",
                    "modelo": "...",
                    "ano_modelo": "...",
                    "color": "...",
                    "numero_vin": "...",
                    "numero_serie": "...",
                    "carroceria": "...",
                    "potencia": "...",
                    "form_rod": "...",
                    "traccion": "...",
                    "combustible": "...",
                    "asientos": "...",
                    "cilindros": "...",
                    "ruedas": "...",
                    "ejes": "...",
                    "cilindrada": "...",
                    "longitud": "...",
                    "altura": "...",
                    "ancho": "...",
                    "p_bruto": "...",
                    "p_neto": "...",
                    "carga_util": "...",
                    "pasajeros": "..."
                }

                *IMPORTANTE:* No incluyas explicaciones, markdown extra o texto fuera del JSON o la frase de error.
                """
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[prompt, uploaded_file],
                    config={"response_mime_type": "application/json"} 
                )
            
            # -------------------------------------------------------------
            # FIN NUEVO BLOQUE
            # -------------------------------------------------------------
            # -------------------------------------------------------------
            # NUEVO BLOQUE: TARJETA ÚNICA DE CIRCULACIÓN (TUC)
            # -------------------------------------------------------------
            elif document_type == "Tarjeta Única de Circulación (TUC)":
                prompt = """
                *INSTRUCCIÓN:* Analiza la imagen adjunta, que es una Tarjeta Única de Circulación (TUC) o Tarjeta de Habilitación Vehicular de Perú (MTC).

                1. *CLASIFICACIÓN:* Determina si el documento es una TUC o Tarjeta de Habilitación Vehicular de Perú.
                2. *SALIDA CONDICIONAL:*
                    * *SI ES TUC:* Extrae *TODOS* los campos solicitados. Si algún campo no es visible, usa estrictamente una cadena vacía ("") para ese campo. NO ADIVINES O INFIERAS DATOS. Devuelve los campos *EXCLUSIVAMENTE* en el FORMATO JSON requerido.
                    * *SI NO ES TUC:* Devuelve *EXCLUSIVAMENTE* la cadena de texto: "No es del tipo del documento seleccionado".

                *CAMPOS JSON (TUC):* {
                    "tipo_documento": "TUC / Habilitación Vehicular",
                    "numero_tuc": "...",
                    "vigente_desde": "DD/MM/AAAA",
                    "vigente_hasta": "DD/MM/AAAA",
                    "nombre_o_razon_social": "...",
                    "ruc": "...",
                    "partida_registral": "...",
                    "modalidad_de_servicio": "...",
                    "documento_sustento": "...",
                    "placa_no": "...",
                    "marca": "...",
                    "carroceria": "...",
                    "vin": "...",
                    "n_de_serie_de_chasis": "...",
                    "color": "...",
                    "n_de_asientos": "...",
                    "n_de_ejes": "...",
                    "peso_neto_kg": "...",
                    "peso_bruto_kg": "...",
                    "carga_util_kg": "...",
                    "ano_modelo": "...",
                    "largo_mts": "...",
                    "ancho_mts": "...",
                    "alto_mts": "..."
                }

                *IMPORTANTE:* No incluyas explicaciones, markdown extra o texto fuera del JSON o la frase de error.
                """
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[prompt, uploaded_file],
                    config={"response_mime_type": "application/json"} 
                )
            
            # -------------------------------------------------------------
            # FIN NUEVO BLOQUE TUC
            # -------------------------------------------------------------

            else:
                prompt = "Extrae todo el texto contenido en este documento/imagen en español."
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[prompt, uploaded_file]
                )
            

            # 4. Eliminar el archivo después de usarlo
            client.files.delete(name=uploaded_file.name)
            
            return response.text
            
    except Exception as e:
        return f"ERROR durante la extracción con Gemini: {e}"

# --- Interfaz de Streamlit ---
# --- CONFIGURACIÓN DE PÁGINA Y ESTILO SOLEIL METALS ---
st.set_page_config(
    page_title="OCR Soleil Metals",
    page_icon="📄",
    layout="centered"
)

# --- COLORES CORPORATIVOS ---
SOLEIL_BLUE = "#263F8C"  # Pantone Blue 072C
SOLEIL_YELLOW = "#EEAD1A" # Pantone 1235

# --- CSS PERSONALIZADO CON MODO CLARO FORZADO ---
st.markdown(
    f"""
    <style>
        /* Forzar fondo claro y tipografía */
        html, body, [class*="stAppViewContainer"], [data-testid="stAppViewContainer"], .stApp {{
            background-color: #FFFFFF !important;
            color: #222222 !important;
            font-family: "Segoe UI", sans-serif !important;
        }}

        /* Centrar todo el contenido principal */
        .block-container {{
            max-width: 900px;
            margin: 0 auto;
            padding-top: 2rem;
        }}

        /* LOGO */
        .logo-container {{
            text-align: center;
            margin-bottom: 0.5rem;
            padding-top: 0.8rem; /* pequeño espacio para que no se corte arriba */
            overflow: visible !important; /* permite mostrar toda la imagen */
        }}

        .logo-container img {{
            display: inline-block;
            max-height: 100px;    /* tamaño máximo razonable */
            width: auto;
            height: auto;
            object-fit: contain;
            border: none;
            margin: 0 auto;
        }}

        /* Título principal */
        .main-title {{
            text-align: center;
            color: {SOLEIL_BLUE};
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
        }}

        /* Subtítulo */
        .subtitle {{
            text-align: center;
            color: {SOLEIL_YELLOW};
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 2rem;
        }}

        /* Texto explicativo */
        .info-text {{
            text-align: center;
            color: #333333;
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }}

        /* Botón principal */
        div.stButton > button:first-child {{
            background-color: {SOLEIL_BLUE} !important;
            color: white !important;
            font-weight: 600;
            border: none;
            border-radius: 8px;
            padding: 0.6rem 1.4rem;
            transition: all 0.2s ease-in-out;
        }}
        div.stButton > button:first-child:hover {{
            background-color: {SOLEIL_YELLOW} !important;
            color: black !important;
        }}

        /* Inputs deshabilitados */
        input[disabled] {{
            background-color: #f4f4f8 !important;
            color: #333 !important;
            border: 1px solid #ccc !important;
        }}

        /* Expander */
        .streamlit-expanderHeader {{
            color: {SOLEIL_BLUE} !important;
            font-weight: 600;
        }}

        /* Quitar fondo oscuro en selectboxes y file uploader */
        .stSelectbox [data-baseweb="select"],
        .stFileUploader {{
            background-color: #FFFFFF !important;
            color: #000000 !important;
        }}

        /* Aclarar info box */
        [data-testid="stInfo"] {{
            background-color: #E8EFFF !important;
            color: #000000 !important;
            border-left: 4px solid {SOLEIL_BLUE} !important;
        }}
        /* Labels más fuertes */
        label, .stSelectbox label, .stFileUploader label {{
          color: #1C1C1C !important;
          font-weight: 600 !important;
        }}

        /* Texto en inputs (activo y deshabilitado) */
        .stTextInput input,
        .stTextArea textarea,
        div[data-baseweb="input"] input {{
          color: #111111 !important;
          -webkit-text-fill-color: #111111 !important; /* Safari/Chromium */
          opacity: 1 !important;
          background-color: #FFFFFF !important;
          border: 1px solid #C0C0C0 !important;
        }}

        /* Estado deshabilitado: que NO se apague */
        .stTextInput input:disabled,
        .stTextArea textarea:disabled,
        div[data-baseweb="input"] input:disabled {{
          color: #111111 !important;
          -webkit-text-fill-color: #111111 !important;
          opacity: 1 !important;
          background-color: #F6F6F6 !important;
          border: 1px solid #C0C0C0 !important;
        }}

        /* Placeholder cuando el campo viene vacío */
        .stTextInput input::placeholder,
        div[data-baseweb="input"] input::placeholder {{
          color: #6B7280 !important;
          opacity: 1 !important;
        }}

    </style>
    """,
    unsafe_allow_html=True
)

show_logo()
st.markdown("<h1 class='main-title'>Extractor de Texto Estructurado – Soleil Metals</h1>", unsafe_allow_html=True)
st.markdown("<p class='info-text'>Sube un archivo PDF o imagen (JPG, PNG) y el sistema extraerá automáticamente la información estructurada del documento.</p>", unsafe_allow_html=True)




document_type = st.selectbox(
    "Selecciona el tipo de documento a procesar:",
    ("DNI", "Tarjeta de Propiedad", "Tarjeta de Identificación", "Tarjeta Única de Circulación (TUC)")
)

uploaded_file = st.file_uploader(
    "Selecciona un PDF o Imagen (.pdf, .jpg, .png)",
    type=['pdf', 'jpg', 'jpeg', 'png']
)

if uploaded_file is not None:
    st.info(f"Archivo cargado: *{uploaded_file.name}*")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=pathlib.Path(uploaded_file.name).suffix) as tmp_file:
        tmp_file.write(uploaded_file.read())
        temp_file_path = tmp_file.name
    
    if st.button("▶ Iniciar OCR"):
        if client:
            extracted_text = ocr_gemini(temp_file_path, document_type)
            
            st.subheader(f"Resultado Estructurado para: {document_type}")
            
            cleaned_text = extracted_text.strip().strip('"').strip('`').lstrip('json').strip()
            
            try:
                data = json.loads(cleaned_text)
                
                # --- LÓGICA DE VISUALIZACIÓN PERSONALIZADA SEGÚN EL TIPO DE DOCUMENTO ---
                if document_type == "DNI":
                    # Campos principales
                    st.text_input("Tipo Documento", data.get("tipo_documento", ""), disabled=True, key=f"tipo_doc_dni-{time.time()}")
                    st.text_input("Número DNI", data.get("numero_dni", ""), disabled=True, key=f"num_dni-{time.time()}")
                    st.text_input("Apellido Paterno", data.get("apellido_paterno", ""), disabled=True, key=f"ap_pat_dni-{time.time()}")
                    st.text_input("Apellido Materno", data.get("apellido_materno", ""), disabled=True, key=f"ap_mat_dni-{time.time()}")
                    st.text_input("Nombres", data.get("nombres", ""), disabled=True, key=f"nombres_dni-{time.time()}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text_input("Fecha Nacimiento", data.get("fecha_nacimiento", ""), disabled=True, key=f"f_nac_dni-{time.time()}")
                    with col2:
                        st.text_input("Estado Civil", data.get("estado_civil", ""), disabled=True, key=f"est_civil_dni-{time.time()}")
                    
                    col3, col4 = st.columns(2)
                    with col3:
                        st.text_input("Fecha Emisión", data.get("fecha_emision", ""), disabled=True, key=f"f_emi_dni-{time.time()}")
                    with col4:
                        st.text_input("Fecha Caducidad", data.get("fecha_caducidad", ""), disabled=True, key=f"f_cad_dni-{time.time()}")
                    
                    st.text_input("Sexo", data.get("sexo", ""), disabled=True, key=f"sexo_dni-{time.time()}")
                    
                    st.markdown("---") # Separador visual para la dirección
                    st.subheader("Dirección (Reverso)")
                    
                    col_dir1, col_dir2, col_dir3 = st.columns(3)
                    with col_dir1:
                        st.text_input("Departamento", data.get("departamento", ""), disabled=True, key=f"dep_dni-{time.time()}")
                    with col_dir2:
                        st.text_input("Provincia", data.get("provincia", ""), disabled=True, key=f"prov_dni-{time.time()}")
                    with col_dir3:
                        st.text_input("Distrito", data.get("distrito", ""), disabled=True, key=f"dist_dni-{time.time()}")
                    
                    st.text_input("Dirección Completa", data.get("direccion_completa", ""), disabled=True, key=f"dir_comp_dni-{time.time()}")

                elif document_type == "Tarjeta de Propiedad":
                    # --- VISUALIZACIÓN UNIFICADA (FRONTAL Y TRASERO) ---
                    st.text_input("Tipo Documento", data.get("tipo_documento", ""), disabled=True, key=f"tipo_doc_prop-{time.time()}")
                    
                    st.markdown("---")
                    st.subheader("Datos del Vehículo")
                    
                    col_prop_1, col_prop_2 = st.columns(2)
                    with col_prop_1:
                        st.text_input("Placa No.", data.get("placa_no", ""), disabled=True, key=f"placa_prop-{time.time()}")
                        st.text_input("Placa Ant.", data.get("placa_ant", ""), disabled=True, key=f"placa_ant_prop-{time.time()}")
                        st.text_input("Partida Registral", data.get("partida_registral", ""), disabled=True, key=f"part_reg_prop-{time.time()}")
                        st.text_input("Condición", data.get("condicion", ""), disabled=True, key=f"cond_prop-{time.time()}")
                        st.text_input("Tipo de Prop.", data.get("tipo_de_prop", ""), disabled=True, key=f"tipo_prop-{time.time()}")
                        st.text_input("Denominación", data.get("denominacion", ""), disabled=True, key=f"denominacion_prop-{time.time()}")
                        
                    with col_prop_2:
                        st.text_input("Zona Registral No.", data.get("zona_registral_no", ""), disabled=True, key=f"zona_prop-{time.time()}")
                        st.text_input("Oficina Registral", data.get("oficina_registral", ""), disabled=True, key=f"oficina_prop-{time.time()}")
                        st.text_input("DUA/DAM", data.get("dua_dam", ""), disabled=True, key=f"dua_dam_prop-{time.time()}")
                        
                        # Lógica de unificación para Título y Fecha del Título
                        # Priorizamos el frontal si ambos están, si no, usamos el que exista.
                        titulo_unificado = data.get("titulo_frontal", "") or data.get("titulo_reverso", "")
                        fecha_titulo_unificada = data.get("fecha_titulo_frontal", "") or data.get("fecha_del_titulo_reverso", "")
                        
                        st.text_input("Título (Unificado)", titulo_unificado, disabled=True, key=f"titulo_unificado_prop-{time.time()}")
                        st.text_input("Fecha Título (Unificada)", fecha_titulo_unificada, disabled=True, key=f"fecha_titulo_unificada_prop-{time.time()}")
                        
                        # Mostramos los originales en un expander si es necesario para depuración
                        with st.expander("Ver Títulos y Fechas Originales"):
                            st.text_input("Título (Frontal)", data.get("titulo_frontal", ""), disabled=True, key=f"titulo_frontal_orig-{time.time()}")
                            st.text_input("Fecha Título (Frontal)", data.get("fecha_titulo_frontal", ""), disabled=True, key=f"fecha_titulo_frontal_orig-{time.time()}")
                            st.text_input("Título (Reverso)", data.get("titulo_reverso", ""), disabled=True, key=f"titulo_reverso_orig-{time.time()}")
                            st.text_input("Fecha del Título (Reverso)", data.get("fecha_del_titulo_reverso", ""), disabled=True, key=f"fecha_del_titulo_reverso_orig-{time.time()}")
                            

                    st.markdown("---")
                    st.subheader("Datos del Propietario (Frontal)")
                    st.text_input("Apellido Paterno", data.get("apellido_paterno", ""), disabled=True, key=f"ap_pat_prop-{time.time()}")
                    st.text_input("Apellido Materno", data.get("apellido_materno", ""), disabled=True, key=f"ap_mat_prop-{time.time()}")
                    st.text_input("Nombres", data.get("nombres", ""), disabled=True, key=f"nombres_prop-{time.time()}")
                    
                    col_prop_3, col_prop_4, col_prop_5 = st.columns(3)
                    with col_prop_3:
                        st.text_input("Fecha Adq.", data.get("fecha_adq", ""), disabled=True, key=f"f_adq_prop-{time.time()}")
                    with col_prop_4:
                        st.text_input("Exp. Tarj.", data.get("exp_tarj", ""), disabled=True, key=f"exp_tarj_prop-{time.time()}")
                    with col_prop_5:
                        st.text_input("Vig. Temp.", data.get("vig_temp", ""), disabled=True, key=f"vig_temp_prop-{time.time()}")
                    
                    st.text_input("Domicilio", data.get("domicilio", ""), disabled=True, key=f"dom_prop-{time.time()}")
                
                # --------------------------------------------------------------------------
                # NUEVA LÓGICA DE VISUALIZACIÓN: TARJETA DE IDENTIFICACIÓN VEHICULAR
                # --------------------------------------------------------------------------
                elif document_type == "Tarjeta de Identificación":
                    st.text_input("Tipo Documento", data.get("tipo_documento", ""), disabled=True, key=f"tipo_doc_tive-{time.time()}")
                    
                    st.markdown("---")
                    st.subheader("Registro y Título")
                    
                    col_tive_1, col_tive_2 = st.columns(2)
                    with col_tive_1:
                        st.text_input("Placa No.", data.get("placa_no", ""), disabled=True, key=f"placa_tive-{time.time()}")
                        st.text_input("Partida Registral", data.get("partida_registral", ""), disabled=True, key=f"part_reg_tive-{time.time()}")
                        st.text_input("Título No.", data.get("titulo_no", ""), disabled=True, key=f"titulo_tive-{time.time()}")
                        st.text_input("Fecha Título", data.get("fecha_titulo", ""), disabled=True, key=f"fecha_titulo_tive-{time.time()}")
                    with col_tive_2:
                        st.text_input("Zona Registral No.", data.get("zona_registral_no", ""), disabled=True, key=f"zona_tive-{time.time()}")
                        st.text_input("Sede Registral", data.get("sede_registral", ""), disabled=True, key=f"sede_tive-{time.time()}")
                        st.text_input("Código Verificación", data.get("codigo_verificacion", ""), disabled=True, key=f"cod_verif_tive-{time.time()}")
                        st.text_input("DUA/DAM", data.get("dua_dam", ""), disabled=True, key=f"dua_dam_tive-{time.time()}")
                        
                    st.markdown("---")
                    st.subheader("Datos del Vehículo")
                    
                    col_tive_a, col_tive_b, col_tive_c = st.columns(3)
                    with col_tive_a:
                        st.text_input("Marca", data.get("marca", ""), disabled=True, key=f"marca_tive-{time.time()}")
                        st.text_input("Modelo", data.get("modelo", ""), disabled=True, key=f"modelo_tive-{time.time()}")
                        st.text_input("Año Modelo", data.get("ano_modelo", ""), disabled=True, key=f"ano_mod_tive-{time.time()}")
                        st.text_input("Color", data.get("color", ""), disabled=True, key=f"color_tive-{time.time()}")
                        st.text_input("Carrocería", data.get("carroceria", ""), disabled=True, key=f"carroceria_tive-{time.time()}")
                        st.text_input("Potencia", data.get("potencia", ""), disabled=True, key=f"potencia_tive-{time.time()}")
                        
                    with col_tive_b:
                        st.text_input("N° VIN", data.get("numero_vin", ""), disabled=True, key=f"vin_tive-{time.time()}")
                        st.text_input("N° Serie", data.get("numero_serie", ""), disabled=True, key=f"serie_tive-{time.time()}")
                        st.text_input("Combustible", data.get("combustible", ""), disabled=True, key=f"combustible_tive-{time.time()}")
                        st.text_input("Categoría", data.get("categoria", ""), disabled=True, key=f"cat_tive-{time.time()}")
                        st.text_input("Form. Rod.", data.get("form_rod", ""), disabled=True, key=f"rod_tive-{time.time()}")
                        st.text_input("Tracción (Versión)", data.get("traccion", ""), disabled=True, key=f"traccion_tive-{time.time()}")
                        
                    with col_tive_c:
                        st.text_input("Longitud", data.get("longitud", ""), disabled=True, key=f"long_tive-{time.time()}")
                        st.text_input("Altura", data.get("altura", ""), disabled=True, key=f"altura_tive-{time.time()}")
                        st.text_input("Ancho", data.get("ancho", ""), disabled=True, key=f"ancho_tive-{time.time()}")
                        st.text_input("Cilindrada", data.get("cilindrada", ""), disabled=True, key=f"cilindrada_tive-{time.time()}")
                        st.text_input("Cilindros", data.get("cilindros", ""), disabled=True, key=f"cilindros_tive-{time.time()}")
                        st.text_input("Ruedas", data.get("ruedas", ""), disabled=True, key=f"ruedas_tive-{time.time()}")
                        st.text_input("Ejes", data.get("ejes", ""), disabled=True, key=f"ejes_tive-{time.time()}")

                    st.markdown("---")
                    st.subheader("Capacidades")
                    
                    col_tive_d, col_tive_e, col_tive_f = st.columns(3)
                    with col_tive_d:
                        st.text_input("Asientos", data.get("asientos", ""), disabled=True, key=f"asientos_tive-{time.time()}")
                    with col_tive_e:
                        st.text_input("Pasajeros", data.get("pasajeros", ""), disabled=True, key=f"pasajeros_tive-{time.time()}")
                    with col_tive_f:
                        st.text_input("P. Bruto", data.get("p_bruto", ""), disabled=True, key=f"p_bruto_tive-{time.time()}")
                    
                    col_tive_g, col_tive_h, col_tive_i = st.columns(3)
                    with col_tive_g:
                        st.text_input("P. Neto", data.get("p_neto", ""), disabled=True, key=f"p_neto_tive-{time.time()}")
                    with col_tive_h:
                        st.text_input("Carga Útil", data.get("carga_util", ""), disabled=True, key=f"carga_util_tive-{time.time()}")
                    with col_tive_i:
                        # Espacio vacío
                        pass
                
                # --------------------------------------------------------------------------
                # FIN NUEVA LÓGICA DE VISUALIZACIÓN
                # --------------------------------------------------------------------------
                # --------------------------------------------------------------------------
                # NUEVA LÓGICA DE VISUALIZACIÓN: TARJETA ÚNICA DE CIRCULACIÓN (TUC)
                # --------------------------------------------------------------------------
                elif document_type == "Tarjeta Única de Circulación (TUC)":
                    st.text_input("Tipo Documento", data.get("tipo_documento", ""), disabled=True, key=f"tipo_doc_tuc-{time.time()}")
                    st.text_input("N° TUC", data.get("numero_tuc", ""), disabled=True, key=f"num_tuc-{time.time()}")
                    
                    col_tuc_v1, col_tuc_v2 = st.columns(2)
                    with col_tuc_v1:
                        st.text_input("Vigente Desde", data.get("vigente_desde", ""), disabled=True, key=f"desde_tuc-{time.time()}")
                    with col_tuc_v2:
                        st.text_input("Vigente Hasta", data.get("vigente_hasta", ""), disabled=True, key=f"hasta_tuc-{time.time()}")
                        
                    st.markdown("---")
                    st.subheader("Datos del Transportista")
                    st.text_input("Razón Social", data.get("nombre_o_razon_social", ""), disabled=True, key=f"rs_tuc-{time.time()}")
                    st.text_input("RUC", data.get("ruc", ""), disabled=True, key=f"ruc_tuc-{time.time()}")
                    st.text_input("Partida Registral", data.get("partida_registral", ""), disabled=True, key=f"pr_tuc-{time.time()}")
                    st.text_input("Modalidad de Servicio", data.get("modalidad_de_servicio", ""), disabled=True, key=f"mod_tuc-{time.time()}")
                    st.text_input("Documento Sustento", data.get("documento_sustento", ""), disabled=True, key=f"doc_s_tuc-{time.time()}")

                    st.markdown("---")
                    st.subheader("Datos del Vehículo")
                    
                    col_tuc_v3, col_tuc_v4 = st.columns(2)
                    with col_tuc_v3:
                        st.text_input("Placa N°", data.get("placa_no", ""), disabled=True, key=f"placa_tuc-{time.time()}")
                        st.text_input("Marca", data.get("marca", ""), disabled=True, key=f"marca_tuc-{time.time()}")
                        st.text_input("Carrocería", data.get("carroceria", ""), disabled=True, key=f"carroceria_tuc-{time.time()}")
                        st.text_input("N° Asientos", data.get("n_de_asientos", ""), disabled=True, key=f"asientos_tuc-{time.time()}")
                        st.text_input("N° Ejes", data.get("n_de_ejes", ""), disabled=True, key=f"ejes_tuc-{time.time()}")
                    with col_tuc_v4:
                        st.text_input("Color", data.get("color", ""), disabled=True, key=f"color_tuc-{time.time()}")
                        st.text_input("Año Modelo", data.get("ano_modelo", ""), disabled=True, key=f"ano_tuc-{time.time()}")
                        st.text_input("VIN", data.get("vin", ""), disabled=True, key=f"vin_tuc-{time.time()}")
                        st.text_input("N° Serie Chasis", data.get("n_de_serie_de_chasis", ""), disabled=True, key=f"chasis_tuc-{time.time()}")

                    st.markdown("---")
                    st.subheader("Pesos y Dimensiones")

                    col_tuc_p1, col_tuc_p2, col_tuc_p3 = st.columns(3)
                    with col_tuc_p1:
                        st.text_input("Peso Neto (kg)", data.get("peso_neto_kg", ""), disabled=True, key=f"pneto_tuc-{time.time()}")
                        st.text_input("Largo (mts)", data.get("largo_mts", ""), disabled=True, key=f"largo_tuc-{time.time()}")
                    with col_tuc_p2:
                        st.text_input("Peso Bruto (kg)", data.get("peso_bruto_kg", ""), disabled=True, key=f"pbruto_tuc-{time.time()}")
                        st.text_input("Ancho (mts)", data.get("ancho_mts", ""), disabled=True, key=f"ancho_tuc-{time.time()}")
                    with col_tuc_p3:
                        st.text_input("Carga Útil (kg)", data.get("carga_util_kg", ""), disabled=True, key=f"carga_tuc-{time.time()}")
                        st.text_input("Alto (mts)", data.get("alto_mts", ""), disabled=True, key=f"alto_tuc-{time.time()}")
                
                # --------------------------------------------------------------------------
                # FIN LÓGICA DE VISUALIZACIÓN TUC
                # --------------------------------------------------------------------------
                # Opcional: Mostrar el JSON crudo en un expander
                with st.expander("Ver JSON Crudo"):
                    st.json(data)
                
            except json.JSONDecodeError:
                if cleaned_text == "No es del tipo del documento seleccionado":
                    st.error("🚫 El documento subido no coincide con el tipo seleccionado.")
                else:
                    st.error("⚠ Error de formato. Se muestra la salida cruda a continuación:")
                    st.text_area("Salida Cruda del Modelo", extracted_text, height=300)

    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)