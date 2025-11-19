#aktualisasi bintari

import re
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import folium
from folium import Map, CircleMarker, FeatureGroup, LayerControl
from branca.colormap import linear
from branca.element import Template, MacroElement

st.set_page_config(page_title="Peta Korelasi ENSO–Hujan–Produktivitas", layout="wide")
st.title("Peta Interaktif Korelasi (r) – ENSO, Curah Hujan, Produktivitas Padi")
st.caption("Upload Excel **Project_Aktualisasi.xlsx** (sheet **Gabung**). Pilih jenis korelasi di dropdown.")

# =========================
# 1) Upload Excel (wajib)
# =========================
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

# =========================
# 2) Parse sheet "Gabung"
# =========================
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

    if not blocks:
        return pd.DataFrame(columns=["Provinsi","Tahun","Anomali_SST","Anomali_Hujan","Anomali_Produktivitas"])

    df = pd.DataFrame(blocks, columns=["Provinsi","Tahun","Anomali_SST","Anomali_Hujan","Anomali_Produktivitas"])
    df["Provinsi"] = df["Provinsi"].astype(str).str.strip()
    df = df[df["Provinsi"] != ""].drop_duplicates().dropna(subset=["Tahun"])
    df["Tahun"] = df["Tahun"].astype(int)
    for c in ["Anomali_SST","Anomali_Hujan","Anomali_Produktivitas"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values(["Provinsi","Tahun"]).reset_index(drop=True)

tidy = parse_blocks(raw)
if tidy.empty:
    st.error("Parser tidak menemukan blok provinsi di sheet 'Gabung'.")
    st.stop()

# =========================
# 3) Korelasi Pearson per provinsi
# =========================
def pearson_r(a: pd.Series, b: pd.Series):
    sub = pd.DataFrame({"a": a, "b": b}).dropna()
    return sub["a"].corr(sub["b"]) if len(sub) >= 3 else np.nan

prov_list = list(dict.fromkeys(tidy["Provinsi"].tolist()))
rows = []
for prov in prov_list:
    sub = tidy[tidy["Provinsi"] == prov]
    rows.append([
        prov,
        pearson_r(sub["Anomali_SST"],   sub["Anomali_Produktivitas"]),  # SST–Prod
        pearson_r(sub["Anomali_SST"],   sub["Anomali_Hujan"]),          # SST–Hujan
        pearson_r(sub["Anomali_Hujan"], sub["Anomali_Produktivitas"]),  # Hujan–Prod
    ])
corr_df = pd.DataFrame(rows, columns=["Provinsi","Anomali SST & Anomali Produktivitas","Anomali SST & Anomali Curah Hujan","Anomali Curah Hujan & Anomali Produktivitas"])

with st.expander("Tabel korelasi (r) per provinsi"):
    st.dataframe(corr_df, use_container_width=True)

# =========================
# 4) Koordinat bawaan
# =========================
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

missing = corr_df[corr_df[["lon","lat"]].isna().any(axis=1)]["Provinsi"].tolist()
if missing:
    st.info("Provinsi tanpa koordinat (tidak tampil di peta): " + ", ".join(missing))

# =========================
# 5) Peta interaktif + legend bernomor
# =========================
st.subheader("Peta – pilih korelasi yang ditampilkan")
choice = st.selectbox(
    "Jenis korelasi:",
    ["Anomali SST ↔ Anomali Produktivitas", "Anomali SST ↔ Anomali Curah Hujan", "Anomali Curah Hujan ↔ Anomali Produktivitas"],
    index=0
)

colmap = {
    "Anomali SST ↔ Anomali Produktivitas": ("Anomali SST & Anomali Produktivitas", "Anomali SST vs Anomali Produktivitas"),
    "Anomali SST ↔ Anomali Curah Hujan": ("Anomali SST & Anomali Curah Hujan", "Anomali SST vs Anomali Curah Hujan"),
    "Anomali Curah Hujan ↔ Anomali Produktivitas": ("Anomali Curah Hujan & Anomali Produktivitas", "Anomali Curah Hujan vs Anomali Produktivitas"),
}
colname, layer_title = colmap[choice]

m = Map(location=[-2.2, 117.0], zoom_start=5, tiles="CartoDB positron", control_scale=True)
cmap = linear.RdBu_11.scale(-1, 1)

fg = FeatureGroup(name=layer_title, show=True)
for _, r in plot_df.iterrows():
    val = r[colname]
    color = cmap(val if np.isfinite(val) else 0.0)
    val_txt = "NaN" if not np.isfinite(val) else f"{val:.3f}"
    CircleMarker(
        location=(r["lat"], r["lon"]),
        radius=9, color="black", weight=1,
        fill=True, fill_opacity=0.88, fill_color=color,
        tooltip=f"{r['Provinsi']} | r={val_txt}",
        popup=folium.Popup(f"<b>{r['Provinsi']}</b><br>{layer_title}<br>r = {val_txt}", max_width=320),
    ).add_to(fg)
fg.add_to(m)
LayerControl(position="topleft").add_to(m)

# Legend dengan warna + angka yang kontras
def add_static_legend(m, title, cmap_obj):
    ticks = [-1.0, -0.6, -0.2, 0.0, 0.2, 0.6, 1.0]
    patches = "".join(
        f"<div style='display:flex;align-items:center;margin-bottom:6px;'>"
        f"<span style='display:inline-block;width:22px;height:14px;background:{cmap_obj(t)};"
        f"border:1px solid #888;margin-right:8px;'></span>"
        f"<span style='min-width:42px;display:inline-block;color:#111;font-weight:600;'>{t:+.1f}</span></div>"
        for t in ticks
    )
    legend_html = f"""
    {{% macro html(this, kwargs) %}}
    <div style="
        position: fixed; top: 10px; right: 10px; z-index: 9999;
        background: #ffffff; border: 1px solid #888; border-radius: 6px;
        box-shadow: 0 1px 4px rgba(0,0,0,.25);
        padding: 10px 12px; font-size: 13px; color:#111;">
      <div style="font-weight:700; margin-bottom:6px;">Legenda</div>
      <div style="margin-bottom:6px;">Koefisien Korelasi (r)</div>
      <div>{patches}</div>
    </div>
    {{% endmacro %}}
    """
    macro = MacroElement(); macro._template = Template(legend_html)
    m.get_root().add_child(macro)

def add_map_title(m, text):
    title_html = f'''
      <div style="position: fixed; top: 15px; left: 50%; transform: translateX(-50%);
                  background: rgba(255,255,255,0.95); border: 1px solid #888; border-radius: 8px;
                  padding: 8px 16px; font-size: 18px; font-weight: 700; color: #111; z-index: 9999;">
        {text}
      </div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))

add_map_title(m, layer_title)
add_static_legend(m, "Legenda", cmap)

st_folium(m, width=None, height=650)

# =========================
# 6) Grafik deret waktu per provinsi
# =========================
st.subheader("Grafik Deret Waktu Anomali per Provinsi")
prov_pick = st.selectbox("Pilih provinsi:", prov_list)
sub = tidy[tidy["Provinsi"] == prov_pick].sort_values("Tahun")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Anomali SST**")
    st.bar_chart(sub.set_index("Tahun")[["Anomali_SST"]])
with c2:
    st.markdown("**Anomali Curah Hujan (CH)**")
    st.bar_chart(sub.set_index("Tahun")[["Anomali_Hujan"]])

st.markdown("**Anomali Produktivitas**")
st.bar_chart(sub.set_index("Tahun")[["Anomali_Produktivitas"]])



