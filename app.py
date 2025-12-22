import streamlit as st
import pandas as pd
import urllib.parse
import streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Menú El Comedor", page_icon="🍲", layout="centered")

# --- CONEXIÓN A GOOGLE SHEETS (HÍBRIDA + PARCHE) ---
def conectar_google_sheets(nombre_hoja="Hoja1"):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        # INTENTO 1: NUBE (Streamlit Secrets)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            # CORRECCIÓN DE LLAVE: Reemplaza los \n literales por saltos de línea reales
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        # INTENTO 2: LOCAL (Archivo JSON)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
            
        client = gspread.authorize(creds)
        wb = client.open("Base_Datos_Comedor")
        if nombre_hoja == "Menu":
            return wb.worksheet("Menu")
        else:
            return wb.sheet1
    except Exception as e:
        st.error(f"⚠️ Error conectando con Google ({nombre_hoja}): {e}")
        return None

# --- CARGA DEL MENÚ DINÁMICO ---
@st.cache_data(ttl=60)
def cargar_menu_dinamico():
    hoja = conectar_google_sheets("Menu")
    if not hoja: return None
    
    data = hoja.get_all_records()
    df = pd.DataFrame(data)
    
    # Filtrar solo disponibles
    if 'Disponible' in df.columns:
        df = df[df['Disponible'].astype(str).str.upper() == 'TRUE']
    
    menu = {
        "PLANCHA": {}, "BARRA": {}, "EXTRAS": {}, "GUARNICION": [],
        "ENTRADA": [], "ACOMPANAMIENTO": [], "BEBIDA": [], "POSTRE": []
    }

    for _, row in df.iterrows():
        cat = row['Categoria']
        platillo = row['Platillo']
        precio = row['Precio']

        if cat in ["PLANCHA", "BARRA", "EXTRAS"]:
            menu[cat][platillo] = precio
        elif cat in menu:
            menu[cat].append(platillo)
            
    # Opciones por defecto
    if "Sin Guarnición" not in menu["GUARNICION"]: menu["GUARNICION"].insert(0, "Sin Guarnición")
    if "Ninguna" not in menu["ENTRADA"]: menu["ENTRADA"].insert(0, "Ninguna")
    if "Ninguno" not in menu["ACOMPANAMIENTO"]: menu["ACOMPANAMIENTO"].insert(0, "Ninguno")
            
    return menu

MENU_DATA = cargar_menu_dinamico()

# Respaldo si falla la carga
if not MENU_DATA:
    st.warning("⚠️ Usando menú de respaldo (Error de conexión)")
    MENU_DATA = {
        "PLANCHA": {"Milanesa (Respaldo)": 95}, "BARRA": {"Guisado (Respaldo)": 80}, "EXTRAS": {},
        "GUARNICION": ["Arroz"], "ENTRADA": ["Sopa"], "ACOMPANAMIENTO": ["Tortillas"], "BEBIDA": [], "POSTRE": []
    }

def guardar_pedido_en_nube(sheet, carrito, cliente, ubicacion, tel, horario_entrega):
    zona_mx = pytz.timezone('America/Mexico_City')
    fecha_hoy = datetime.now(zona_mx).strftime("%Y-%m-%d")

    columna_a = sheet.col_values(1) 
    siguiente_fila = len(columna_a) + 1
    filas_a_insertar = []
    
    for item in carrito:
        # SANITIZACIÓN: Agregamos "'" para evitar fórmulas de Excel maliciosas
        fila = [
            fecha_hoy, horario_entrega, 
            f"'{cliente}", f"'{ubicacion}", f"'{tel}",
            item['Plato'], item['Guarn'], f"'{item['Detalles']}", f"'{item['Extras']}",
            f"'{item['Notas']}", item['Precio'], item['Tipo'], "PENDIENTE"
        ]
        filas_a_insertar.append(fila)
    
    fila_fin = siguiente_fila + len(filas_a_insertar) - 1
    rango = f"A{siguiente_fila}:M{fila_fin}"
    sheet.update(range_name=rango, values=filas_a_insertar)

# --- SESIÓN ---
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'scroll_to_top' not in st.session_state: st.session_state.scroll_to_top = False

# --- CALLBACKS ---
def agregar_al_carrito_callback(item):
    st.session_state.carrito.append(item)
    st.session_state.tab_plancha = None
    st.session_state.tab_barra = None
    st.toast('✅ ¡Agregado!', icon='😋')

def reiniciar_seleccion_callback():
    st.session_state.tab_plancha = None
    st.session_state.tab_barra = None
    st.session_state.scroll_to_top = True

def borrar_todo_callback():
    st.session_state.carrito = []
    st.session_state.tab_plancha = None
    st.session_state.tab_barra = None
    st.session_state.scroll_to_top = True

def al_seleccionar_plancha(): st.session_state.tab_barra = None
def al_seleccionar_barra(): st.session_state.tab_plancha = None

# --- SCROLL HACK ---
if st.session_state.scroll_to_top:
    components.html('<script>var body = window.parent.document.querySelector(\'[data-testid="stAppViewContainer"]\'); body.scrollTop = 0;</script>', height=0)
    st.session_state.scroll_to_top = False

# --- UI PRINCIPAL ---
st.title("🍲 Cocina Económica 'El Comedor'")
st.markdown("**¡Hola!** Arma tu pedido aquí y recíbelo en tu oficina.")
st.divider()

# 1. DATOS DE ENTREGA
hay_pedidos = len(st.session_state.carrito) > 0
with st.expander("📍 DATOS DE ENTREGA", expanded=not hay_pedidos):
    if hay_pedidos: st.info("🔒 Datos bloqueados. Usa 'Borrar Todo' para corregir.")
    
    col1, col2 = st.columns(2)
    with col1:
        ubicacion_select = st.selectbox("¿Edificio?", ["Selecciona...", "Economía", "ProMéxico", "Corum", "Tribunal", "Audi", "Otro"], disabled=hay_pedidos)
        ubicacion_final = ubicacion_select
        if ubicacion_select == "Otro":
            ubicacion_final = st.text_input("Escribe el nombre del lugar:", disabled=hay_pedidos) or ""
    with col2:
        horario = st.selectbox("¿A qué hora?", ["1:00 PM", "2:00 PM", "3:00 PM", "Lo antes posible"], disabled=hay_pedidos)
    
    c1, c2 = st.columns(2)
    with c1: cliente_nombre = st.text_input("Tu Nombre:", disabled=hay_pedidos)
    with c2: 
        # VALIDACIÓN DE TELÉFONO
        cliente_tel = st.text_input("WhatsApp (10 dígitos):", disabled=hay_pedidos, max_chars=10)
        if cliente_tel and (not cliente_tel.isdigit() or len(cliente_tel) < 10):
            st.warning("⚠️ Ingresa un número válido de 10 dígitos.")
            cliente_tel = ""

datos_completos = (ubicacion_select != "Selecciona..." and ubicacion_final != "" and cliente_nombre and cliente_tel)

# 2. SELECCIÓN DE PLATILLO
st.divider()
st.subheader("🍽️ Selecciona un Platillo")
tab1, tab2 = st.tabs(["🔥 De la Plancha", "🥘 Guisados / Barra"])

plato_elegido = ""
precio_base = 0
tipo_cocina = ""

with tab1:
    opciones = [f"{k} (${v})" for k, v in MENU_DATA["PLANCHA"].items()]
    sel = st.radio("Opciones Plancha:", opciones, index=None, key="tab_plancha", on_change=al_seleccionar_plancha)
    if sel:
        plato_elegido = sel.split(" ($")[0]
        precio_base = MENU_DATA["PLANCHA"][plato_elegido]
        tipo_cocina = "PLANCHA"

with tab2:
    opciones = [f"{k} (${v})" for k, v in MENU_DATA["BARRA"].items()]
    sel = st.radio("Opciones Barra:", opciones, index=None, key="tab_barra", on_change=al_seleccionar_barra)
    if sel:
        plato_elegido = sel.split(" ($")[0]
        precio_base = MENU_DATA["BARRA"][plato_elegido]
        tipo_cocina = "BARRA"

# 3. PERSONALIZACIÓN
nuevo_item = None
if plato_elegido:
    st.success(f"Personalizando: **{plato_elegido}**")

    c_guarn, c_ent = st.columns(2)
    with c_guarn: guarn = st.selectbox("Guarnición:", MENU_DATA["GUARNICION"])
    with c_ent: ent = st.radio("Entrada:", MENU_DATA["ENTRADA"], horizontal=True)

    c_p1, c_p2, c_p3 = st.columns(3)
    with c_p1: acomp = st.radio("Acompañamiento:", MENU_DATA["ACOMPANAMIENTO"])
    with c_p2: 
        nom_beb = MENU_DATA["BEBIDA"][0] if MENU_DATA["BEBIDA"] else "Agua"
        agua = st.checkbox(nom_beb, True) if MENU_DATA["BEBIDA"] else False
    with c_p3: 
        nom_postre = MENU_DATA["POSTRE"][0] if MENU_DATA["POSTRE"] else "Postre"
        postre = st.checkbox(nom_postre, True) if MENU_DATA["POSTRE"] else False

    lista_extras = [f"{k} (+${v})" for k, v in MENU_DATA["EXTRAS"].items()]
    extras_sel = st.multiselect("Extras ($):", lista_extras)
    notas = st.text_input("Instrucciones especiales:", placeholder="Ej. Sin cebolla")

    costo_extras = sum([MENU_DATA["EXTRAS"][e.split(" (+$")[0]] for e in extras_sel])
    precio_final = precio_base + costo_extras

    detalles_texto = f"{ent}, {acomp}"
    if agua: detalles_texto += f", {nom_beb}"
    if postre: detalles_texto += f", {nom_postre}"
    extras_texto = ", ".join([e.split(" (+$")[0] for e in extras_sel])

    nuevo_item = {
        "Plato": plato_elegido, "Guarn": guarn, "Detalles": detalles_texto,
        "Extras": extras_texto, "Notas": notas, "Precio": precio_final, "Tipo": tipo_cocina
    }

    st.markdown(f"**Precio: :green[${precio_final}]**")
    st.button("⬇️ AGREGAR A MI ORDEN", use_container_width=True, type="primary", on_click=agregar_al_carrito_callback, args=(nuevo_item,))

# 4. RESUMEN Y FINALIZAR
if len(st.session_state.carrito) > 0:
    st.divider()
    st.subheader(f"🛒 Tu Orden ({len(st.session_state.carrito)} platillos)")
    df = pd.DataFrame(st.session_state.carrito)
    st.caption(f"📍 Entregar en: **{ubicacion_final}** a las {horario}")
    st.dataframe(df[["Tipo", "Plato", "Guarn", "Detalles", "Extras", "Notas", "Precio"]], use_container_width=True, hide_index=True)
    
    total = df["Precio"].sum()
    st.markdown(f"<h3 style='text-align: right;'>TOTAL: ${total}</h3>", unsafe_allow_html=True)
    
    col_izq, col_der = st.columns(2)
    with col_izq: st.button("➕ AGREGAR OTRO", on_click=reiniciar_seleccion_callback, use_container_width=True)
    with col_der:
        if datos_completos:
            if st.button("✅ ENVIAR PEDIDO", type="primary", use_container_width=True):
                with st.spinner('Enviando pedido...'):
                    hoja = conectar_google_sheets()
                    if hoja:
                        guardar_pedido_en_nube(hoja, st.session_state.carrito, cliente_nombre, ubicacion_final, cliente_tel, horario)
                        st.success("¡Pedido registrado!")
                        resumen_texto = f"*PEDIDO ({horario})*\n👤 {cliente_nombre}\n📍 {ubicacion_final}\n\n"
                        for item in st.session_state.carrito:
                            resumen_texto += f"🔹 {item['Plato']} ({item['Guarn']})\n 🥣 {item['Detalles']}\n"
                            if item['Extras']: resumen_texto += f" ➕ Extras: {item['Extras']}\n"
                            if item['Notas']: resumen_texto += f" ⚠️ Nota: {item['Notas']}\n"
                            resumen_texto += "----------------\n"
                        resumen_texto += f"\n💰 *TOTAL: ${total}*"
                        link_whatsapp = f"https://wa.me/527299679866?text={urllib.parse.quote(resumen_texto)}"
                        st.markdown(f"### 👉 [CONFIRMAR EN WHATSAPP]({link_whatsapp})")
                    else: st.error("Error de conexión.")
        else:
             if ubicacion_select == "Otro" and not ubicacion_final: st.warning("Escribe el lugar.")
             else: st.warning("Faltan datos de entrega.")
    st.divider()
    st.button("🗑️ BORRAR TODO", type="secondary", use_container_width=True, on_click=borrar_todo_callback)
elif len(st.session_state.carrito) == 0: st.info("👆 Selecciona tu platillo arriba.")