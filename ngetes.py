# cek_peta_gabung.py (diperbarui untuk menampilkan 3 grafik variabel terpisah dalam popup)

import re
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import folium
from folium import Map, CircleMarker, FeatureGroup, LayerControl, Popup, IFrame
from branca.colormap import linear
from branca.element import Template, MacroElement
import matplotlib.pyplot as plt
import base64
from io import BytesIO

st.set_page_config(page_title="Peta Korelasi ENSO–Hujan–Produktivitas", layout="wide")
st.title("Peta Interaktif Korelasi (r) – ENSO, Curah Hujan, Produktivitas Padi")
st.caption("Upload Excel **Project_Aktualisasi.xlsx** (sheet **Gabung**). Pilih jenis korelasi di dropdown.")

uploaded = st.file_uploader("Upload file Excel (.xlsx) – gunakan file *Project_Aktualisasi.xlsx*", type=["xlsx"])
if uploaded is None:
    st.info("Silakan upload file Excel terlebih dahulu.")
    st.stop()

SHEET_NAME = "Gabung"

@st.cache_data(show_spinner=False)
def load_raw(uploaded_file, sheet_name):
    return pd.read_excel(uploaded_file, sheet_name=sheet_name, header=None)

try:
    raw = load_raw(uploaded, SHEET_NAME)
except Exception as e:
    st.error(f"Gagal membaca sheet **{SHEET_NAME}** dari file yang diupload.\n\nDetail: {e}")
    st.stop()

def parse_blocks(raw_df: pd.DataFrame) -> pd.DataFrame:
    blocks = []
    i, n = 0, len(raw_df)

    def is_year_like(x):
        try:
            xi = int(str(x).strip()); return 1900 <= xi <= 2100
        except: return False

    def clean_prov(s: str) -> str:
        s = str(s).strip()
        s = re.sub(r"\s+", " ", s)
        return s

    while i < n:
        val = raw_df.iloc[i, 0]
        next_is_tahun = (i+1 < n and isinstance(raw_df.iloc[i+1, 0], str)
                         and raw_df.iloc[i+1, 0].strip().lower() == "tahun")
        if isinstance(val, str) and val.strip() and next_is_tahun:
            prov = clean_prov(val)
            j = i + 2
            while j < n:
                first = raw_df.iloc[j, 0]
                if pd.isna(first): break
                if isinstance(first, str) and "anomali sst" in str(first).lower(): break
                if is_year_like(first):
                    tahun = int(str(first).strip())
                    sst   = pd.to_numeric(raw_df.iloc[j, 1], errors="coerce")
                    hujan = pd.to_numeric(raw_df.iloc[j, 2], errors="coerce")
                    prod  = pd.to_numeric(raw_df.iloc[j, 3], errors="coerce")
                    blocks.append([prov, tahun, sst, hujan, prod])
                    j += 1
                else:
                    break
            i = j + 1
        else:
            i += 1

    df = pd.DataFrame(blocks, columns=["Provinsi","Tahun","ENSO","Curah Hujan","Produktivitas"])
    df["Provinsi"] = df["Provinsi"].astype(str).str.strip()
    df = df[df["Provinsi"] != ""].drop_duplicates().dropna(subset=["Tahun"])
    df["Tahun"] = df["Tahun"].astype(int)
    for c in ["ENSO","Curah Hujan","Produktivitas"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values(["Provinsi","Tahun"]).reset_index(drop=True)

tidy = parse_blocks(raw)
if tidy.empty:
    st.error("Parser tidak menemukan blok provinsi di sheet 'Gabung'.")
    st.stop()

def pearson_r(a: pd.Series, b: pd.Series):
    sub = pd.DataFrame({"a": a, "b": b}).dropna()
    return sub["a"].corr(sub["b"]) if len(sub) >= 3 else np.nan

prov_list = list(dict.fromkeys(tidy["Provinsi"].tolist()))
rows = []
for prov in prov_list:
    sub = tidy[tidy["Provinsi"] == prov]
    rows.append([
        prov,
        pearson_r(sub["ENSO"], sub["Produktivitas"]),
        pearson_r(sub["ENSO"], sub["Curah Hujan"]),
        pearson_r(sub["Curah Hujan"], sub["Produktivitas"]),
    ])
corr_df = pd.DataFrame(rows, columns=["Provinsi","ENSO & Produktivitas","ENSO & Curah Hujan","Curah Hujan & Produktivitas"])

coords = {
    # Sumatera
    "Aceh": (95.3, 5.5), "Sumatera Utara": (99.1, 2.5), "Sumatera Barat": (100.5, -0.5),
    "Riau": (101.8, 0.5), "Jambi": (103.6, -1.6), "Sumatera Selatan": (104.7, -3.2),
    "Bengkulu": (102.3, -3.8), "Lampung": (105.3, -5.2), "Kepulauan Bangka Belitung": (106.0, -2.3),
    # Jawa-Bali
    "Banten": (106.1, -6.2), "DKI Jakarta": (106.8, -6.2), "Jawa Barat": (107.5, -6.8),
    "Jawa Tengah": (110.0, -7.0), "DI Yogyakarta": (110.4, -7.8), "Jawa Timur": (112.0, -7.5), "Bali": (115.2, -8.4),
    # Nusa Tenggara
    "NTB": (117.0, -8.6), "Nusa Tenggara Barat": (117.0, -8.6),
    "NTT": (121.1, -8.6), "Nusa Tenggara Timur": (121.1, -8.6),
    # Kalimantan
    "Kalimantan Barat": (110.0, 0.0), "Kalimantan Tengah": (113.9, -1.6),
    "Kalimantan Selatan": (114.9, -3.0), "Kalimantan Timur": (117.1, 0.0), "Kalimantan Utara": (116.8, 2.8),
    # Sulawesi
    "Sulawesi Utara": (124.8, 1.3), "Gorontalo": (123.1, 0.6), "Sulawesi Tengah": (121.3, -1.0),
    "Sulawesi Barat": (119.3, -2.7), "Sulawesi Selatan": (120.5, -4.5), "Sulawesi Tenggara": (122.2, -4.1),
    # Maluku-Papua
    "Maluku": (129.0, -3.2), "Maluku Utara": (127.8, 1.3),
    "Papua Barat": (133.5, -1.3), "Papua Barat Daya": (132.3, -0.9),
    "Papua": (138.5, -4.3), "Papua Tengah": (136.5, -3.8), "Papua Pegunungan": (139.4, -4.2), "Papua Selatan": (140.1, -7.1),
}

corr_df["lon"] = corr_df["Provinsi"].map(lambda x: coords.get(x, (np.nan, np.nan))[0])
corr_df["lat"] = corr_df["Provinsi"].map(lambda x: coords.get(x, (np.nan, np.nan))[1])
plot_df = corr_df.dropna(subset=["lon","lat"]).copy()

st.subheader("Peta – pilih korelasi yang ditampilkan")
choice = st.selectbox(
    "Jenis korelasi:",
    ["ENSO ↔ Produktivitas", "ENSO ↔ Curah Hujan", "Curah Hujan ↔ Produktivitas"],
    index=0
)

colmap = {
    "ENSO ↔ Produktivitas": ("ENSO & Produktivitas", "ENSO vs Produktivitas"),
    "ENSO ↔ Curah Hujan": ("ENSO & Curah Hujan", "ENSO vs Curah Hujan"),
    "Curah Hujan ↔ Produktivitas": ("Curah Hujan & Produktivitas", "Curah Hujan vs Produktivitas"),
}
colname, layer_title = colmap[choice]

m = Map(location=[-2.2, 117.0], zoom_start=5, tiles="CartoDB positron", control_scale=True)
cmap = linear.RdBu_11.scale(-1, 1)

fg = FeatureGroup(name=layer_title, show=True)
for _, r in plot_df.iterrows():
    val = r[colname]
    color = cmap(val if np.isfinite(val) else 0.0)
    sub = tidy[tidy["Provinsi"] == r["Provinsi"]]
    sub = sub.sort_values("Tahun")
    fig, axs = plt.subplots(nrows=3, ncols=1, figsize=(4, 6))
    axs[0].bar(sub["Tahun"], sub["ENSO"], color="steelblue"); axs[0].set_title("ENSO", fontsize=8)
    axs[1].bar(sub["Tahun"], sub["Curah Hujan"], color="forestgreen"); axs[1].set_title("Curah Hujan", fontsize=8)
    axs[2].bar(sub["Tahun"], sub["Produktivitas"], color="peru"); axs[2].set_title("Produktivitas", fontsize=8)
    for ax in axs: ax.tick_params(labelsize=6)
    plt.tight_layout()
    buf = BytesIO(); plt.savefig(buf, format="png"); plt.close(fig)
    data_uri = base64.b64encode(buf.getvalue()).decode("utf-8")
    html = f'<img src="data:image/png;base64,{data_uri}" width="300">'
    popup = Popup(IFrame(html, width=310, height=460), max_width=320)
    CircleMarker(
        location=(r["lat"], r["lon"]),
        radius=9, color="black", weight=1,
        fill=True, fill_opacity=0.88, fill_color=color,
        tooltip=f"{r['Provinsi']} | r={val:.3f}",
        popup=popup,
    ).add_to(fg)
fg.add_to(m)
LayerControl(position="topleft").add_to(m)

add_static_legend = lambda m, title, cmap_obj: ...  # isi tetap
add_map_title = lambda m, text: ...  # isi tetap
add_map_title(m, layer_title)
add_static_legend(m, "Legenda", cmap)
st_folium(m, width=None, height=650)

prov_pick = st.selectbox("Pilih provinsi:", prov_list)
sub = tidy[tidy["Provinsi"] == prov_pick].sort_values("Tahun")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**ENSO**")
    st.bar_chart(sub.set_index("Tahun")[["ENSO"]])
with c2:
    st.markdown("**Curah Hujan**")
    st.bar_chart(sub.set_index("Tahun")[["Curah Hujan"]])
st.markdown("**Produktivitas**")
st.bar_chart(sub.set_index("Tahun")[["Produktivitas"]])
