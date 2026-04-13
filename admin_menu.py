import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Admin", page_icon="🔑", layout="wide")

# --- SEGURIDAD Y ROLES ---
if "admin_password" not in st.secrets:
    st.error("❌ FALTA PASSWORD EN SECRETS")
    st.stop()

password_input = st.sidebar.text_input("🔑 Password (o usa 'GUEST'):", type="password")

# Determinamos el nivel de acceso
es_admin = (password_input == st.secrets["admin_password"])
es_invitado = (password_input.upper() == "GUEST")

if not es_admin and not es_invitado:
    st.info("💡 Tip para reclutadores: Ingresa 'GUEST' para ver el panel en modo lectura.")
    st.warning("Acceso restringido")
    st.stop()

if es_invitado:
    st.sidebar.success("✅ Modo Invitado (Solo Lectura)")
else:
    st.sidebar.success("🔑 Modo Administrador Total")

# --- CONEXIÓN ---
def conectar():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
    return gspread.authorize(creds).open("Base_Datos_Comedor")

wb = conectar()
st.title("⚙️ Panel de Control")

# --- CARGAR CONFIGURACIÓN ---
sh_config = wb.worksheet("Config")
df_config = pd.DataFrame(sh_config.get_all_records())
config_dict = {str(r['Clave']): str(r['Valor']) for _, r in df_config.iterrows()}

T1 = config_dict.get('titulo_pestana_1', 'Principal')
T2 = config_dict.get('titulo_pestana_2', 'Secundario')
S1 = config_dict.get('titulo_selector_1', 'Opcional 1')
S2 = config_dict.get('titulo_selector_2', 'Opcional 2')
EXT = config_dict.get('titulo_extras', 'Extras')

# --- PESTAÑAS PRINCIPALES ---
tab_menu, tab_conf, tab_sedes, tab_cierre, tab_reporte = st.tabs(["🍔 Menú", "⚙️ Config", "📍 Sedes", "📂 Cierre", "📊 Reporte"])

with tab_menu:
    st.header("Editor de Menú")
    sh_menu = wb.worksheet("Menu")
    df_menu = pd.DataFrame(sh_menu.get_all_records())
    secciones_fuertes = [T1, T2]
    secciones_complementos = [S1, S2, EXT, "Notas", "Bebida", "Postre"]
    df_main = df_menu[df_menu['Seccion'].isin(secciones_fuertes)]
    df_comp = df_menu[~df_menu['Seccion'].isin(secciones_fuertes)]
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Platos Fuertes")
        edit_main = st.data_editor(df_main, num_rows="dynamic" if es_admin else None, key="editor_main", 
                                   use_container_width=True, disabled=es_invitado,
                                   column_config={"Seccion": st.column_config.SelectboxColumn("Sección", options=secciones_fuertes, required=True)})
    with c2:
        st.subheader("2. Complementos / Extras")
        edit_comp = st.data_editor(df_comp, num_rows="dynamic" if es_admin else None, key="editor_comp", 
                                   use_container_width=True, disabled=es_invitado,
                                   column_config={"Seccion": st.column_config.SelectboxColumn("Sección", options=secciones_complementos, required=True)})

    if st.button("💾 GUARDAR TODO EL MENÚ", type="primary", disabled=es_invitado):
        df_final = pd.concat([edit_main, edit_comp], ignore_index=True)
        sh_menu.clear()
        sh_menu.update([df_final.columns.values.tolist()] + df_final.values.tolist())
        st.success("¡Menú guardado!")

with tab_conf:
    st.header("Configuración Universal")
    edited_conf = st.data_editor(df_config, use_container_width=True, disabled=es_invitado)
    if st.button("💾 Actualizar Config", disabled=es_invitado):
        sh_config.clear()
        sh_config.update([edited_conf.columns.values.tolist()] + edited_conf.values.tolist())
        st.success("Config actualizada")

with tab_sedes:
    st.header("Sedes")
    sh_sedes = wb.worksheet("Sedes")
    df_sedes = pd.DataFrame(sh_sedes.get_all_records())
    edited_sedes = st.data_editor(df_sedes, num_rows="dynamic" if es_admin else None, 
                                  use_container_width=True, disabled=es_invitado)
    if st.button("💾 Guardar Sedes", disabled=es_invitado):
        sh_sedes.clear()
        sh_sedes.update([edited_sedes.columns.values.tolist()] + edited_sedes.values.tolist())
        st.success("Sedes guardadas")

with tab_cierre:
    st.header("Cierre de Día")
    if es_invitado: st.info("ℹ️ El archivado de pedidos está deshabilitado en modo invitado.")
    if st.button("🏁 ARCHIVAR PEDIDOS DE HOY", disabled=es_invitado):
        sh_ped = wb.worksheet("Pedidos")
        pedidos = sh_ped.get_all_values()
        if len(pedidos) > 1:
            wb.worksheet("Historial").append_rows(pedidos[1:])
            sh_ped.batch_clear([f"A2:L{len(pedidos)+1}"])
            st.success("Bandeja limpia.")
        else: st.info("Nada que archivar.")

with tab_reporte:
    st.header("📈 Análisis de Ventas")
    url_looker = "https://lookerstudio.google.com/embed/reporting/0d692966-4fa1-402d-af72-06bb44c4ce6b/page/5kwuF"
    st.components.v1.iframe(url_looker, height=800, scrolling=True)
