import streamlit as st
import pandas as pd
import urllib.parse
import streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Cargando...", page_icon="🍽️", layout="centered")

# --- ESTADOS DE SESIÓN ---
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'scroll_top' not in st.session_state: st.session_state.scroll_top = False

# --- CALLBACKS DE INTERACCIÓN ---
def limpiar_seleccion_1():
    if st.session_state.radio_seccion_1 is not None:
        st.session_state.radio_seccion_2 = None

def limpiar_seleccion_2():
    if st.session_state.radio_seccion_2 is not None:
        st.session_state.radio_seccion_1 = None

def agregar_y_limpiar(item):
    st.session_state.carrito.append(item)
    st.session_state.radio_seccion_1 = None
    st.session_state.radio_seccion_2 = None
    st.toast("✅ Agregado")

def reiniciar_y_subir():
    st.session_state.radio_seccion_1 = None
    st.session_state.radio_seccion_2 = None
    st.session_state.scroll_top = True

if st.session_state.scroll_top:
    components.html('<script>window.parent.document.querySelector(\'section.main\').scrollTo(0, 0);</script>', height=0)
    st.session_state.scroll_top = False

# --- CONEXIÓN ---
def conectar_google_sheets(nombre_hoja):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
        client = gspread.authorize(creds)
        wb = client.open("Base_Datos_Comedor")
        return wb.worksheet(nombre_hoja)
    except Exception as e:
        st.error(f"⚠️ Error conectando ({nombre_hoja}): {e}")
        return None

# --- CARGA CONFIG SAAS (DINÁMICA) ---
@st.cache_data(ttl=300)
def cargar_config_saas():
    # 1. Configuración
    hoja_config = conectar_google_sheets("Config")
    if not hoja_config: return {}, {}
    data_config = hoja_config.get_all_records()
    config = {str(row['Clave']): str(row['Valor']) for row in data_config}
    
    # Defaults de seguridad por si el Excel está vacío
    defaults = {
        "titulo_pestana_1": "Principal", "titulo_pestana_2": "Secundario",
        "titulo_selector_1": "Opciones", "titulo_selector_2": "Extra",
        "titulo_extras": "Adicionales", "estado_tienda": "ABIERTO"
    }
    for k, v in defaults.items():
        if k not in config or not config[k]: config[k] = v

    # 2. Sedes
    hoja_sedes = conectar_google_sheets("Sedes")
    data_sedes = hoja_sedes.get_all_records()
    sedes = {}
    for row in data_sedes:
        opciones = [x.strip() for x in str(row['Horarios_Texto']).split(',')]
        sedes[row['Sede']] = opciones
        
    return config, sedes

CONFIG, SEDES_DICT = cargar_config_saas()

# --- VALIDACIÓN APERTURA ---
if CONFIG["estado_tienda"].upper() != "ABIERTO":
    st.title("⛔ " + CONFIG.get("titulo_app", "App"))
    st.error(CONFIG.get("mensaje_cierre", "Cerrado."))
    st.stop()

st.markdown(f"# 🍽️ {CONFIG.get('titulo_app', 'Menú Digital')}")

# --- CARGA MENÚ DINÁMICO ---
@st.cache_data(ttl=60)
def cargar_menu():
    hoja = conectar_google_sheets("Menu")
    if not hoja: return None
    data = hoja.get_all_records()
    df = pd.DataFrame(data)
    
    if 'Activo' in df.columns:
        df = df[df['Activo'].astype(str).str.upper() == 'TRUE']
        
    # Estructura basada en CONFIG
    menu = {
        CONFIG['titulo_pestana_1']: {}, 
        CONFIG['titulo_pestana_2']: {}, 
        CONFIG['titulo_extras']: {}, 
        CONFIG['titulo_selector_1']: [], 
        CONFIG['titulo_selector_2']: [], 
        "Notas": []
    }
    
    # Normalización para búsqueda insensible a mayúsculas
    titulos_map = {
        CONFIG['titulo_pestana_1'].lower(): CONFIG['titulo_pestana_1'],
        CONFIG['titulo_pestana_2'].lower(): CONFIG['titulo_pestana_2'],
        CONFIG['titulo_extras'].lower(): CONFIG['titulo_extras'],
        CONFIG['titulo_selector_1'].lower(): CONFIG['titulo_selector_1'],
        CONFIG['titulo_selector_2'].lower(): CONFIG['titulo_selector_2']
    }

    for _, row in df.iterrows():
        seccion_excel = str(row['Seccion']).strip()
        seccion_lower = seccion_excel.lower()
        
        # Mapeo exacto
        destino = titulos_map.get(seccion_lower)
        
        if destino:
            # Si es plato fuerte o extra con precio
            if destino in [CONFIG['titulo_pestana_1'], CONFIG['titulo_pestana_2'], CONFIG['titulo_extras']]:
                menu[destino][row['Platillo']] = row['Precio']
            # Si es lista (guarnicion/entrada)
            else:
                menu[destino].append(row['Platillo'])
    
    # Defaults para listas vacías
    if not menu[CONFIG['titulo_selector_1']]: menu[CONFIG['titulo_selector_1']] = ["Ninguno"]
    if not menu[CONFIG['titulo_selector_2']]: menu[CONFIG['titulo_selector_2']] = ["Ninguno"]
    
    return menu

MENU_DATA = cargar_menu()

# --- GUARDAR PEDIDO ---
def guardar_pedido(carrito, cliente, tel, sede, horario):
    hoja = conectar_google_sheets("Pedidos")
    zona_mx = pytz.timezone('America/Mexico_City')
    fecha_hoy = datetime.now(zona_mx).strftime("%Y-%m-%d")
    nuevas_filas = []
    for item in carrito:
        fila = [
            fecha_hoy, horario, f"'{cliente}", f"'{tel}", sede,
            item['Plato'], f"'{item['Detalles']}", f"'{item['Extras']}",
            f"'{item['Notas']}", item['Precio'], item['Seccion'], "PENDIENTE"
        ]
        nuevas_filas.append(fila)
    hoja.append_rows(nuevas_filas)

# --- UI ---
st.markdown("**¡Hola!** Arma tu pedido aquí.")
st.divider()

hay_pedidos = len(st.session_state.carrito) > 0
with st.expander("📍 1. DATOS DE ENTREGA", expanded=not hay_pedidos):
    if hay_pedidos: st.info("🔒 Bloqueado. Borra el pedido para cambiar.")
    c1, c2 = st.columns(2)
    with c1:
        lista_sedes = ["Selecciona..."] + list(SEDES_DICT.keys())
        sede_select = st.selectbox("¿Sede?", lista_sedes, disabled=hay_pedidos)
    with c2:
        opciones_horario = ["Selecciona sede"]
        if sede_select != "Selecciona..." and sede_select in SEDES_DICT:
            opciones_horario = SEDES_DICT[sede_select]
        horario_select = st.selectbox("¿Horario?", opciones_horario, disabled=hay_pedidos)
    c3, c4 = st.columns(2)
    with c3: nombre = st.text_input("Nombre:", disabled=hay_pedidos)
    with c4: tel = st.text_input("WhatsApp:", max_chars=10, disabled=hay_pedidos)

datos_validos = (sede_select != "Selecciona..." and nombre and len(tel)==10)

st.divider()
st.subheader("🍽️ 2. Selecciona")

if not MENU_DATA:
    st.error("Error de conexión. Recarga.")
    st.stop()

# PESTAÑAS DINÁMICAS
t1_name = CONFIG['titulo_pestana_1']
t2_name = CONFIG['titulo_pestana_2']
tab1, tab2 = st.tabs([f"🔥 {t1_name}", f"🥘 {t2_name}"])

plato_sel = ""
precio_base = 0
seccion_sel = ""

with tab1:
    opcs = [f"{k} (${v})" for k,v in MENU_DATA[t1_name].items()]
    sel_1 = st.radio(f"Opciones {t1_name}", opcs, index=None, key="radio_seccion_1", on_change=limpiar_seleccion_2)
    if sel_1:
        plato_sel = sel_1.split(" ($")[0]
        precio_base = MENU_DATA[t1_name][plato_sel]
        seccion_sel = t1_name

with tab2:
    opcs_2 = [f"{k} (${v})" for k,v in MENU_DATA[t2_name].items()]
    sel_2 = st.radio(f"Opciones {t2_name}", opcs_2, index=None, key="radio_seccion_2", on_change=limpiar_seleccion_1)
    if sel_2:
        plato_sel = sel_2.split(" ($")[0]
        precio_base = MENU_DATA[t2_name][plato_sel]
        seccion_sel = t2_name

# PERSONALIZACIÓN DINÁMICA
if plato_sel:
    st.success(f"Seleccionaste: **{plato_sel}**")
    
    # Selectores dinámicos
    col_sel_1, col_sel_2 = st.columns(2)
    
    titulo_s1 = CONFIG['titulo_selector_1']
    lista_s1 = MENU_DATA.get(titulo_s1, ["Ninguno"])
    with col_sel_1: 
        sel_val_1 = st.selectbox(f"{titulo_s1}:", lista_s1)
        
    titulo_s2 = CONFIG['titulo_selector_2']
    lista_s2 = MENU_DATA.get(titulo_s2, [])
    sel_val_2 = None
    if lista_s2: # Solo mostramos si hay opciones
        with col_sel_2: 
            sel_val_2 = st.selectbox(f"{titulo_s2}:", lista_s2)
    
    # Extras Dinámicos
    titulo_ext = CONFIG['titulo_extras']
    extras_dict = MENU_DATA.get(titulo_ext, {})
    extras_nombres = [f"{k} (+${v})" for k,v in extras_dict.items()]
    extras_sel = st.multiselect(f"{titulo_ext}:", extras_nombres)
    
    notas = st.text_input("Notas (Sin cebolla, etc):")
    
    # Cálculos
    costo_extras = sum([extras_dict[e.split(" (+$")[0]] for e in extras_sel])
    precio_total = precio_base + costo_extras
    
    detalles = f"{titulo_s1}: {sel_val_1}"
    if sel_val_2: detalles += f", {titulo_s2}: {sel_val_2}"
    extras_txt = ", ".join([e.split(" (+$")[0] for e in extras_sel])
    
    st.markdown(f"### Total: :green[${precio_total}]")
    
    st.button("⬇️ AGREGAR A LA ORDEN", type="primary", use_container_width=True, 
              on_click=agregar_y_limpiar, 
              args=({"Plato": plato_sel, "Precio": precio_total, "Seccion": seccion_sel, 
                     "Detalles": detalles, "Extras": extras_txt, "Notas": notas},))

if st.session_state.carrito:
    st.divider()
    st.subheader(f"🛒 Pedido ({len(st.session_state.carrito)})")
    df_c = pd.DataFrame(st.session_state.carrito)
    st.dataframe(df_c[["Plato", "Detalles", "Precio"]], hide_index=True, use_container_width=True)
    
    total = df_c["Precio"].sum()
    st.markdown(f"### TOTAL: :green[${total}]")
    
    c_a, c_b = st.columns(2)
    with c_a: st.button("➕ AGREGAR OTRO", use_container_width=True, on_click=reiniciar_y_subir)
    with c_b:
        if datos_validos:
            if st.button("✅ FINALIZAR", type="primary", use_container_width=True):
                with st.spinner("Enviando..."):
                    guardar_pedido(st.session_state.carrito, nombre, tel, sede_select, horario_select)
                    msg = f"Hola {nombre}. Pedido {sede_select} ({horario_select}):\n"
                    for i in st.session_state.carrito:
                        msg += f"- {i['Plato']} ({i['Detalles']})\n"
                    msg += f"Total: ${total}\nDatos: {CONFIG.get('datos_banco','')}"
                    link = f"https://wa.me/{CONFIG.get('telefono_wa','')}?text={urllib.parse.quote(msg)}"
                    st.success("¡Listo!")
                    st.link_button("📲 Confirmar por WhatsApp", link, type="secondary", use_container_width=True)
                    st.session_state.carrito = []
        else: st.warning("Faltan datos arriba.")
    
    if st.button("🗑️ Borrar Todo"): 
        st.session_state.carrito = []
        st.rerun()