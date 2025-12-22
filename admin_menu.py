import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Editor de Menú", page_icon="📝")

# 🔒 SEGURIDAD
pwd = st.sidebar.text_input("🔑 Contraseña de Admin:", type="password")
if pwd != "Comedor2026": 
    st.warning("⚠️ Ingresa la contraseña para editar.")
    st.stop()

st.title("📝 Editor de Menú y Precios")

# --- CONEXIÓN HÍBRIDA ---
def conectar_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
            
        client = gspread.authorize(creds)
        sheet = client.open("Base_Datos_Comedor").worksheet("Menu")
        return sheet
    except Exception as e:
        st.error(f"Error: {e}")
        return None

sheet = conectar_google_sheets()

if sheet:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    st.info("Modifica disponibilidad y precios. ¡Recuerda GUARDAR al final!")

    df_editado = st.data_editor(
        df,
        num_rows="dynamic",
        column_config={
            "Categoria": st.column_config.SelectboxColumn(
                "Categoría",
                options=["PLANCHA", "BARRA", "EXTRAS", "GUARNICION", "ENTRADA", "ACOMPANAMIENTO", "BEBIDA", "POSTRE"],
                required=True
            ),
            "Precio": st.column_config.NumberColumn("Precio ($)", min_value=0, format="$%d"),
            "Disponible": st.column_config.CheckboxColumn("¿Disponible?", help="Check = A la venta")
        },
        use_container_width=True
    )

    if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary"):
        with st.spinner("Guardando..."):
            try:
                sheet.clear()
                sheet.update(range_name='A1', values=[df_editado.columns.values.tolist()])
                sheet.update(range_name='A2', values=df_editado.values.tolist())
                st.success("¡Menú actualizado!")
                st.balloons()
            except Exception as e:
                st.error(f"Error al guardar: {e}")