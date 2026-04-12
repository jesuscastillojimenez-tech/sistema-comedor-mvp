import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Admin", page_icon="🔑", layout="wide")

# --- SEGURIDAD ---
if "admin_password" not in st.secrets:
    st.error("❌ FALTA PASSWORD EN SECRETS")
    st.stop()
if st.sidebar.text_input("🔑 Password:", type="password") != st.secrets["admin_password"]:
    st.warning("Acceso denegado")
    st.stop()

# --- CONEXIÓN ---
def conectar():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    if "gcp_service_account" in st.secrets:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
    return gspread.authorize(creds).open("Base_Datos_Comedor")

wb = conectar()
st.title("⚙️ Panel de Control")

# --- CARGAR CONFIGURACIÓN PARA TÍTULOS DINÁMICOS ---
sh_config = wb.worksheet("Config")
df_config = pd.DataFrame(sh_config.get_all_records())
config_dict = {str(r['Clave']): str(r['Valor']) for _, r in df_config.iterrows()}

T1 = config_dict.get('titulo_pestana_1', 'Principal')
T2 = config_dict.get('titulo_pestana_2', 'Secundario')
S1 = config_dict.get('titulo_selector_1', 'Opcional 1')
S2 = config_dict.get('titulo_selector_2', 'Opcional 2')
EXT = config_dict.get('titulo_extras', 'Extras')

# --- PESTAÑAS PRINCIPALES ---
tab_menu, tab_conf, tab_sedes, tab_cierre = st.tabs(["🍔 Menú", "⚙️ Config", "📍 Sedes", "📂 Cierre"])

with tab_menu:
    st.header("Editor de Menú Seguro")
    sh_menu = wb.worksheet("Menu")
    df_menu = pd.DataFrame(sh_menu.get_all_records())

    # DIVIDIMOS LOS DATOS (Para evitar errores visuales)
    secciones_fuertes = [T1, T2]
    secciones_complementos = [S1, S2, EXT, "Notas", "Bebida", "Postre"]

    df_main = df_menu[df_menu['Seccion'].isin(secciones_fuertes)]
    df_comp = df_menu[~df_menu['Seccion'].isin(secciones_fuertes)] # El resto

    st.info(f"Edita por separado para mayor seguridad. Recuerda: Usa los nombres exactos: '{T1}', '{T2}', '{S1}', etc.")

    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("1. Platos Fuertes")
        edit_main = st.data_editor(df_main, num_rows="dynamic", key="editor_main", use_container_width=True,
                                   column_config={"Seccion": st.column_config.SelectboxColumn("Sección", options=secciones_fuertes, required=True)})
    
    with c2:
        st.subheader("2. Complementos / Extras")
        edit_comp = st.data_editor(df_comp, num_rows="dynamic", key="editor_comp", use_container_width=True,
                                   column_config={"Seccion": st.column_config.SelectboxColumn("Sección", options=secciones_complementos, required=True)})

    if st.button("💾 GUARDAR TODO EL MENÚ", type="primary"):
        # UNIR Y GUARDAR
        df_final = pd.concat([edit_main, edit_comp], ignore_index=True)
        sh_menu.clear()
        sh_menu.update([df_final.columns.values.tolist()] + df_final.values.tolist())
        st.success("¡Menú guardado y unificado correctamente!")

with tab_conf:
    st.header("Configuración Universal")
    edited_conf = st.data_editor(df_config, use_container_width=True)
    if st.button("💾 Actualizar Config"):
        sh_config.clear()
        sh_config.update([edited_conf.columns.values.tolist()] + edited_conf.values.tolist())
        st.success("Config actualizada")

with tab_sedes:
    st.header("Sedes")
    sh_sedes = wb.worksheet("Sedes")
    df_sedes = pd.DataFrame(sh_sedes.get_all_records())
    edited_sedes = st.data_editor(df_sedes, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Guardar Sedes"):
        sh_sedes.clear()
        sh_sedes.update([edited_sedes.columns.values.tolist()] + edited_sedes.values.tolist())
        st.success("Sedes guardadas")

with tab_cierre:
    st.header("Cierre de Día")
    if st.button("🏁 ARCHIVAR PEDIDOS DE HOY"):
        sh_ped = wb.worksheet("Pedidos")
        pedidos = sh_ped.get_all_values()
        if len(pedidos) > 1:
            wb.worksheet("Historial").append_rows(pedidos[1:])
            sh_ped.batch_clear([f"A2:L{len(pedidos)+1}"])
            st.success("Bandeja limpia.")
        else: st.info("Nada que archivar.")