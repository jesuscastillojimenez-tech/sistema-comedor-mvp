import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Cocina", page_icon="👩‍🍳", layout="wide")

# --- SEGURIDAD ---
if "admin_password" not in st.secrets:
    st.error("❌ ERROR CRÍTICO")
    st.stop()
if st.sidebar.text_input("🔑 Password:", type="password") != st.secrets["admin_password"]:
    st.warning("Acceso restringido")
    st.stop()

# --- CONEXIÓN ---
def conectar_wb():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    if "gcp_service_account" in st.secrets:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
    return gspread.authorize(creds).open("Base_Datos_Comedor")

wb = conectar_wb()

# --- LEER CONFIG PARA TÍTULOS ---
sh_config = wb.worksheet("Config")
conf_data = sh_config.get_all_records()
conf = {str(r['Clave']): str(r['Valor']) for r in conf_data}
T1 = conf.get('titulo_pestana_1', 'Seccion 1')
T2 = conf.get('titulo_pestana_2', 'Seccion 2')

st.title("👩‍🍳 Monitor de Cocina")
modo = st.sidebar.radio("Modo:", ["🔥 Pendientes", "📦 Recuperar"])

if st.button("🔄 ACTUALIZAR"): st.rerun()

sh_ped = wb.worksheet("Pedidos")
df = pd.DataFrame(sh_ped.get_all_records())

if df.empty:
    st.info("Sin datos.")
    st.stop()

# --- VISTA PENDIENTES ---
if modo == "🔥 Pendientes":
    df_pend = df[df['Estatus'] == 'PENDIENTE']
    if df_pend.empty:
        st.success("Todo despachado.")
        st.stop()

    horas = sorted(df_pend['Hora'].unique())
    h_sel = st.selectbox("Horario:", horas)
    df_h = df_pend[df_pend['Hora'] == h_sel]
    sedes = df_h['Sede'].unique()

    st.divider()
    for sede in sedes:
        with st.expander(f"📍 {sede} ({len(df_h[df_h['Sede']==sede])})", expanded=True):
            df_s = df_h[df_h['Sede'] == sede]
            c1, c2, c3 = st.columns([2, 2, 1])
            
            # COLUMNA 1 (Dinámica)
            with c1:
                st.markdown(f"### {T1}")
                # Buscamos coincidencias exactas con el nombre configurado
                df_1 = df_s[df_s['Seccion'] == T1]
                if not df_1.empty:
                    conteo = df_1.groupby(['Platillo', 'Detalles', 'Notas']).size().reset_index(name='c')
                    for _, r in conteo.iterrows():
                        st.info(f"**{r['c']}x** {r['Platillo']}\n\n📝 {r['Detalles']} {r['Notas']}")
            
            # COLUMNA 2 (Dinámica)
            with c2:
                st.markdown(f"### {T2}")
                df_2 = df_s[df_s['Seccion'] == T2]
                if not df_2.empty:
                    conteo = df_2.groupby(['Platillo', 'Detalles', 'Notas']).size().reset_index(name='c')
                    for _, r in conteo.iterrows():
                        st.warning(f"**{r['c']}x** {r['Platillo']}\n\n📝 {r['Detalles']} {r['Notas']}")

            # ACCIONES
            with c3:
                st.markdown("### 🖨️")
                txt = f"== {sede} {h_sel} ==\n"
                for _, r in df_s.iterrows(): txt += f"{r['Cliente']}: {r['Platillo']} ({r['Detalles']})\n---\n"
                st.text_area("Ticket", txt, height=100)
                if st.button(f"🚀 DESPACHAR {sede}", key=sede):
                    updates = [gspread.Cell(i+2, 12, 'ENVIADO') for i in df_s.index]
                    sh_ped.update_cells(updates)
                    st.success("Enviado")
                    st.rerun()

# --- VISTA RECUPERAR ---
else:
    st.header("Recuperar Despachados")
    df_env = df[df['Estatus'] == 'ENVIADO']
    if not df_env.empty:
        sel = st.multiselect("Selecciona para regresar:", df_env.index, format_func=lambda x: f"{df_env.loc[x]['Cliente']} - {df_env.loc[x]['Platillo']}")
        if st.button("↩️ REGRESAR A COCINA") and sel:
            updates = [gspread.Cell(i+2, 12, 'PENDIENTE') for i in sel]
            sh_ped.update_cells(updates)
            st.success("Recuperado")
            st.rerun()