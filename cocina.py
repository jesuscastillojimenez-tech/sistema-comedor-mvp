import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Monitor de Cocina", page_icon="👩‍🍳", layout="wide")

# 🔒 SEGURIDAD
pwd = st.sidebar.text_input("🔑 Contraseña de Cocina:", type="password")
if pwd != "Comedor2026": 
    st.warning("⚠️ Ingresa la contraseña en la barra lateral.")
    st.stop()

st.title("👩‍🍳 Monitor de Producción y Empaque")

# --- CONEXIÓN HÍBRIDA ---
def conectar_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        # NUBE
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        # LOCAL
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
            
        client = gspread.authorize(creds)
        sheet = client.open("Base_Datos_Comedor").sheet1 
        return sheet
    except Exception as e:
        st.error(f"⚠️ Error de conexión: {e}")
        return None

# --- CARGA DATOS ---
def cargar_datos():
    sheet = conectar_google_sheets()
    if not sheet: return pd.DataFrame()
    
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    if df.empty: return pd.DataFrame()

    cols = ['Estatus', 'Hora', 'Ubicacion', 'Tipo', 'Precio', 'Plato', 'Guarnicion', 'Notas', 'Cliente', 'Detalles', 'Extras']
    for col in cols:
        if col not in df.columns:
            st.error(f"❌ Falta la columna '{col}' en Hoja1.")
            return pd.DataFrame()

    df = df[df['Estatus'] == 'PENDIENTE']
    return df

if st.button("🔄 Actualizar Pedidos"): st.rerun()

df = cargar_datos()

if df.empty:
    st.info("✅ No hay pedidos pendientes.")
    st.stop()

# --- FILTROS ---
horarios = sorted(df['Hora'].unique())
horario_seleccionado = st.selectbox("🕒 Horario a Cocinar:", horarios)
df_hora = df[df['Hora'] == horario_seleccionado]
st.divider()

# --- VISTA POR EDIFICIO ---
edificios = sorted(df_hora['Ubicacion'].unique())

for edificio in edificios:
    df_edificio = df_hora[df_hora['Ubicacion'] == edificio]
    
    with st.expander(f"📍 {edificio} ({len(df_edificio)} pedidos)", expanded=True):
        tab_cocina, tab_empaque = st.tabs(["🔥 COCINA", "📦 EMPAQUE"])
        
        with tab_cocina:
            col_plancha, col_barra = st.columns(2)
            
            with col_plancha:
                st.markdown("### 🔥 PLANCHA")
                df_p = df_edificio[df_edificio['Tipo'] == 'PLANCHA']
                if not df_p.empty:
                    conteo = df_p.groupby(['Plato', 'Guarnicion']).size().reset_index(name='Cant')
                    for _, row in conteo.iterrows():
                        st.info(f"**{row['Cant']}x** {row['Plato']} \n\n Guarn: {row['Guarnicion']}")
                        notas = df_p[(df_p['Plato']==row['Plato']) & (df_p['Guarnicion']==row['Guarnicion']) & (df_p['Notas']!='')]['Notas'].tolist()
                        for n in notas: st.warning(f"⚠️ {n}")
                else: st.write("---")

            with col_barra:
                st.markdown("### 🥘 BARRA")
                df_b = df_edificio[df_edificio['Tipo'] == 'BARRA']
                if not df_b.empty:
                    conteo = df_b.groupby(['Plato', 'Guarnicion']).size().reset_index(name='Cant')
                    for _, row in conteo.iterrows():
                        st.success(f"**{row['Cant']}x** {row['Plato']} \n\n Guarn: {row['Guarnicion']}")
                        notas = df_b[(df_b['Plato']==row['Plato']) & (df_b['Guarnicion']==row['Guarnicion']) & (df_b['Notas']!='')]['Notas'].tolist()
                        for n in notas: st.warning(f"⚠️ {n}")
                else: st.write("---")

        with tab_empaque:
            st.write("📋 **Copiar para etiquetas:**")
            for _, row in df_edificio.iterrows():
                linea = f"{row['Cliente']}: {row['Plato']}/{row['Guarnicion']}/{row['Detalles']}"
                if row['Extras']: linea += f" [EXTRAS: {row['Extras']}]"
                if row['Notas']: linea += f" (Nota: {row['Notas']})"
                linea += f" [Total: ${row['Precio']}]"
                st.text(linea)