import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="Pferderennen",
    page_icon="🏇",
    layout="centered",
    
)

# ---------------------------------------------------------
# Pferdenamen aus dem <title> extrahieren
# ---------------------------------------------------------
def extract_horse_name(soup):
    title = soup.find("title").get_text(strip=True)
    name = title.split(",")[0]  # Alles vor dem ersten Komma
    return name

import altair as alt
from PIL import Image
from io import BytesIO
import base64
import re
import streamlit.components.v1 as components


alt.themes.enable('none')
alt.renderers.set_embed_options(locale='de-DE')


def render_horse_image_from_layers(style_string):
    # Alle URLs extrahieren
    urls = re.findall(r'url\((.*?)\)', style_string)
    urls = [u.strip('"').strip("'") for u in urls]

    # Absolute URLs erzeugen
    urls = [
        "https://www.howrse.de" + u if u.startswith("/") else u
        for u in urls
    ]

    # Alle Layer herunterladen
    layers = []
    for url in urls:
        try:
            response = requests.get(url)
            img = Image.open(BytesIO(response.content)).convert("RGBA")
            layers.append(img)
        except:
            pass

    if not layers:
        return None

    # Layer übereinanderlegen
    final = layers[0]
    for layer in layers[1:]:
        final = Image.alpha_composite(final, layer)

    # Als Base64 zurückgeben
    buffer = BytesIO()
    final.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return "data:image/png;base64," + encoded




def extract_all_layer_urls(soup):
    urls = []

    # Nur im Pferdebereich suchen
    horse_container = soup.find(id="imageCheval") or soup.find("div", class_="js-horse-view")
    if not horse_container:
        return []

    for tag in horse_container.find_all(style=True):
        style = tag["style"]
        found = re.findall(r'url\((.*?)\)', style)
        for u in found:
            u = u.strip('"').strip("'")
            urls.append(u)

    # Duplikate entfernen
    urls = list(dict.fromkeys(urls))

    # Absolute URLs
    urls = ["https://www.howrse.de" + u if u.startswith("/") else u for u in urls]

    # Reihenfolge umdrehen (shadow → body → mane → forelock)
    return urls[::-1]


def render_layers(urls):
    layers = []

    for url in urls:
        try:
            img = Image.open(BytesIO(requests.get(url).content)).convert("RGBA")
            layers.append(img)
        except:
            pass

    if not layers:
        return None

    base_w, base_h = layers[0].size

    normalized = []
    for layer in layers:
        if layer.size != (base_w, base_h):
            layer = layer.resize((base_w, base_h), Image.LANCZOS)
        normalized.append(layer)

    final = normalized[0]
    for layer in normalized[1:]:
        final = Image.alpha_composite(final, layer)

    return final



def get_horse_image(soup):
    # 1. Normales PNG
    img_tag = soup.find("img", class_="js-horse-image")
    if img_tag and img_tag.get("src"):
        url = img_tag["src"]
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = "https://www.howrse.de" + url
        return url

    # 2. Animiertes Pferd → statisches PNG
    iframe = soup.find("iframe", class_="js-horse-image")
    if iframe and iframe.get("data-image-url"):
        url = iframe["data-image-url"]
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = "https://www.howrse.de" + url
        return url

    # 3. Layer-Pferd
    urls = extract_all_layer_urls(soup)
    final = render_layers(urls)

    if final is None:
        return None

    buffer = BytesIO()
    final.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return "data:image/png;base64," + encoded




# ---------------------------------------------------------
# Wettbewerbsdaten extrahieren
# ---------------------------------------------------------
def extract_competition_data(url):
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    horse_id = url.split("id=")[-1]

    horse_name = extract_horse_name(soup)

   # Pferdebild extrahieren



# 1. Versuch: normales PNG-Bild
    horse_image = get_horse_image(soup)
   
    # Besitzer extrahieren
    owner_box = soup.find("div", id="ownerBoite")

    if owner_box:
        owner_tag = owner_box.find("a")
        if owner_tag:
            owner_name = owner_tag.get_text(strip=True)
        else:
            owner_name = None
    else:
        owner_name = None
        
    # Geschlecht ermitteln

    geschlecht = None

    match = re.search(r"var chevalSexe\s*=\s*'(masculin|feminin)'", r.text)

    if match:
        geschlecht = match.group(1)
    else:
        text = soup.get_text(" ", strip=True)

        if "Geschlecht: männlich" in text:
            geschlecht = "masculin"
        elif "Geschlecht: weiblich" in text:
            geschlecht = "feminin"


    data = []

    rows = soup.find_all("tr", class_="dashed")

    for row in rows:
        discipline_cell = row.find("td", class_="first")
        if not discipline_cell:
            continue

        discipline = discipline_cell.get_text(strip=True)

        numbers = []
        for s in row.find_all("strong"):
            text = s.get_text(strip=True)
            if text.isdigit():
                numbers.append(int(text))

        if len(numbers) == 4:
            data.append({
                "pferd": horse_name,
                "horse_id": horse_id,
                "discipline": discipline,
                "schleifen": numbers[0],
                "gold": numbers[1],
                "silber": numbers[2],
                "bronze": numbers[3],
                "image": horse_image,
                "owner": owner_name,
                "geschlecht": geschlecht

            })

    return data



# ---------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------
st.title("- Das Große Pferderennen! -")
st.header("🌀Hengste vs 🌸Stuten")



all_data = []

urls = ["https://www.howrse.de/elevage/fiche/?id=106862838",
        "https://www.howrse.de/elevage/fiche/?id=108115577",
        "https://www.howrse.de/elevage/fiche/?id=108180445",
        "https://www.howrse.de/elevage/fiche/?id=107497259",
        "https://www.howrse.de/elevage/fiche/?id=105749136",
        "https://www.howrse.de/elevage/fiche/?id=106238423",
        #"https://www.howrse.de/elevage/fiche/?id=104820933",
        #"https://www.howrse.de/elevage/fiche/?id=104820934",
        #"https://www.howrse.de/elevage/fiche/?id=104820941",
        #"https://www.howrse.de/elevage/fiche/?id=104820942"
        #"https://www.howrse.de/elevage/fiche/?id=99501547"
        ]

for url in urls:
    try:
        extracted = extract_competition_data(url)
        all_data.extend(extracted)
    except Exception as e:
            st.error(f"Fehler beim Auslesen von {url}: {e}")

if all_data:
        df = pd.DataFrame(all_data)
    
        horse_info = df.groupby("horse_id").agg({
            "pferd": "first",
            "image": "first",
            "owner": "first",
            "geschlecht": "first"
        }).reset_index()

                
        # st.subheader("Ausgelesene Daten")
        # st.dataframe(df)
       
        # st.subheader("Gesamtübersicht pro Pferd (alle Disziplinen)")

        # totals_per_horse = df.groupby("pferd")[["schleifen", "gold", "silber", "bronze"]].sum()

        # st.dataframe(totals_per_horse)
        # st.bar_chart(totals_per_horse)


        # st.subheader("Diagramm")
        # st.bar_chart(totals_per_horse)

    


        # st.subheader("Pferd‑für‑Pferd‑Vergleich")

        # selected_metric = st.selectbox(
        #     "Welche Kennzahl möchtest du vergleichen?",
        #     ["schleifen", "gold", "silber", "bronze"]
        # )

        # comparison = df.pivot_table(
        #     index="discipline",
        #     columns="pferd",
        #     values=selected_metric,
        #     aggfunc="sum"
        # )

        # st.bar_chart(comparison)

        # st.subheader("Summenübersicht pro Pferd")

        # sum_per_horse = df.groupby("pferd")[["schleifen", "gold", "silber", "bronze"]].sum()

        # st.dataframe(sum_per_horse)
        # st.bar_chart(sum_per_horse)
        
        
        

        totals_per_horse = df.groupby("horse_id")[["schleifen", "gold", "silber", "bronze"]].sum()

        # Punktesystem anwenden
            
        totals_per_horse["punkte"] = (
            totals_per_horse["schleifen"] * 50 +
            totals_per_horse["gold"] * 10 +
            totals_per_horse["silber"] * 0 +
            totals_per_horse["bronze"] * 0
            )
       
        
        # st.subheader("🏆 Ranking nach Gesamtpunktzahl")

        ranking_points = totals_per_horse["punkte"].sort_values(ascending=False)
        totals_per_horse_sorted = totals_per_horse.sort_values("punkte", ascending=False)




        
       
    
        
            # Ranking-Daten vorbereiten
        chart_data = totals_per_horse_sorted.reset_index().merge(
           horse_info,
           on="horse_id",
           how="left"
        )
        
        

        chart_data["unique"] = chart_data["horse_id"]
        chart_data["label"] = chart_data["pferd"]
        import html

        chart_data["safe_label"] = chart_data["pferd"].apply(html.escape)

# Drei getrennte X-Achsen
        chart_data["bar_x"] = chart_data["punkte"]
        chart_data["text_x"] = chart_data["punkte"].max() * 0.02
        chart_data["icon_x"] = chart_data["punkte"]
        chart_data["farbe"] = chart_data["geschlecht"].map({
                "masculin": "#b9d9ff",  # zart blau
                    "feminin": "#ffd6e8"    # zart rosa
        })
        
        all_chart_data = chart_data.copy()

        hengste_data = chart_data[
            chart_data["geschlecht"] == "masculin"
        ].copy()

        stuten_data = chart_data[
            chart_data["geschlecht"] == "feminin"
        ].copy()
        

        def build_chart(data):
# Unsichtbare Y-Achse
            y_axis = alt.Y(
                "unique:N",
                #sort=alt.SortField(field="punkte"),
                axis=None
            )
        
            max_punkte = data["punkte"].max()
            x_max = max_punkte * 1.05

# Balken
            bar = alt.Chart(data).mark_bar().encode(
                x=alt.X("bar_x:Q", title="Punkte",
                    scale=alt.Scale(domain=[0, x_max])),
                y=y_axis,
                color=alt.Color(
                    "geschlecht:N",
                    scale=alt.Scale(
                        domain=["masculin", "feminin"],
                        range=["#b9d9ff", "#ffd6e8"]
                    ),
                    legend=None
                )
            )

# Text (eigene X-Achse, links vom Balken)
            text = alt.Chart(data).mark_text(
                align="left",
                baseline="middle",
                dx=-5,
                color="#20ad4e",
                fontSize=14
            ).encode(
                x="text_x:Q",
                y=y_axis,
                text="label:N"
            )           

# Icons (eigene X-Achse)
            icons = alt.Chart(data).mark_image(
                width=40,
                height=40
            ).encode(
                x="icon_x:Q",
                y=y_axis,
                url="image:N",
                tooltip=["pferd:N", "punkte:Q"]
            )

        




            chart = (bar + text + icons).properties(
                width=700,
                height=60 * len(chart_data)
            ).configure_view(
                stroke=None,
                clip=False
            )

            
            
            return chart
        
        def build_chart_geteilt(data):
# Unsichtbare Y-Achse
            y_axis = alt.Y(
                "unique:N",
                #sort=alt.SortField(field="punkte"),
                axis=None
            )
        
            max_punkte = data["punkte"].max()
            x_max = max_punkte * 1.05

# Balken
            bar = alt.Chart(data).mark_bar().encode(
                x=alt.X("bar_x:Q", title="Punkte",
                    scale=alt.Scale(domain=[0, x_max])),
                y=y_axis,
                color=alt.Color(
                    "geschlecht:N",
                    scale=alt.Scale(
                        domain=["masculin", "feminin"],
                        range=["#b9d9ff", "#ffd6e8"]
                    ),
                    legend=None
                )
            )

# Text (eigene X-Achse, links vom Balken)
            text = alt.Chart(data).mark_text(
                align="left",
                baseline="middle",
                dx=-5,
                color="#20ad4e",
                fontSize=14
            ).encode(
                x="text_x:Q",
                y=y_axis,
                text="label:N"
            )           

# Icons (eigene X-Achse)
            icons = alt.Chart(data).mark_image(
                width=40,
                height=40
            ).encode(
                x="icon_x:Q",
                y=y_axis,
                url="image:N",
                tooltip=["pferd:N", "punkte:Q"]
            )

        




            chart = (bar + text + icons).properties(
                width=700,
                height=25 * len(chart_data)
            ).configure_view(
                stroke=None,
                clip=False
            )

            
            
            return chart


        st.subheader("🏇 Gesamtrennen")

        chart = build_chart(all_chart_data)
        html = chart.to_html(embed_options={"renderer": "svg"})

    

        components.html(
            html,
            height=60 * len(all_chart_data) + 100,
            scrolling=True
        )

        

        st.subheader("🌀 Hengste")

        chart = build_chart_geteilt(hengste_data)
        html = chart.to_html(embed_options={"renderer": "svg"})
        
        components.html(
            html,
            height=25 * len(all_chart_data) + 100,
            scrolling=True
        )

        

        st.subheader("🌸 Stuten")

        chart = build_chart_geteilt(stuten_data)
        html = chart.to_html(embed_options={"renderer": "svg"})
        
        components.html(
            html,
            height=25 * len(all_chart_data) + 100,
            scrolling=True
        )

        



        st.subheader("Leaderboard")
        overview = totals_per_horse_sorted.reset_index().merge(
            horse_info,
            on="horse_id",
            how="left"
        )
        
        
        def color_rows(row):
            geschlecht = overview.loc[row.name, "geschlecht"]

            if geschlecht == "masculin":
                return ["background-color: #b9d9ff"] * len(row)
            elif geschlecht == "feminin":
                return ["background-color: #ffd6e8"] * len(row)
            else:
                return ["background-color: #ffffff"] * len(row)
        
        overview = overview.reset_index(drop=True)
        overview.index = overview.index + 1
        
        styled_overview = (
            overview[
                [
                    "pferd",
                    #"geschlecht",
                    "schleifen",
                    "gold",
                    "silber",
                    "bronze",
                    "punkte"
                ]
            ]
            .style
            .apply(color_rows, axis=1)
            
        )



        

        st.dataframe(styled_overview)


        gruppenwertung = chart_data.groupby(
            "geschlecht"
        )["punkte"].sum()
        
        hengste_punkte = gruppenwertung.get("masculin", 0)
        stuten_punkte = gruppenwertung.get("feminin", 0)

        st.subheader("🏆 Hengste vs Stuten")

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "🌀 Hengste",
                f"{hengste_punkte:,} Punkte"
            )

        with col2:
            st.metric(
                "🌸 Stuten",
                f"{stuten_punkte:,} Punkte"
            )


        if hengste_punkte > stuten_punkte:
            st.success("🌀 Die Hengste liegen vorne!")
        elif stuten_punkte > hengste_punkte:
            st.success("🌸 Die Stuten liegen vorne!")
        else:
            st.info("🤝 Unentschieden!")
       
        
        #Pferdekarten:
        st.subheader("Die Rennpferde")

        for horse_id, row in totals_per_horse.iterrows():
            
            horse_name = df[df["horse_id"] == horse_id]["pferd"].iloc[0]
            geschlecht = df[df["horse_id"] == horse_id]["geschlecht"].iloc[0]
            owner_name = df[df["horse_id"] == horse_id]["owner"].iloc[0]
            img_url = df[df["horse_id"] == horse_id]["image"].dropna().iloc[0]
            
            
            if geschlecht == "masculin":
                card_color = "#b9d9ff"
            elif geschlecht == "feminin":
                card_color = "#ffd6e8"
            else:
                card_color = "#ffffff"
            
            


            st.markdown(
                f"""
                <h4 style="
                    background-color:{card_color};
                    padding:10px;
                    border-radius:10px;
                ">
                    {horse_name}
                </h4>
                """,
                unsafe_allow_html=True
            )

            st.write(f"**Besitzer*in:** {owner_name}")
            


            col1, col2 = st.columns([1, 2])

        # Bild anzeigen
            with col1:
        # Erstes Bild aus df für dieses Pferd holen
                img_url = df[df["horse_id"] == horse_id]["image"].dropna().iloc[0]
                if img_url:
                    st.image(img_url, width=150)
                else:
                    st.write("Kein Bild gefunden")

    # Stats anzeigen
            with col2:
                
                st.markdown(
                    f"""
                    <div style="
                        background-color:{card_color};
                        padding:10px;
                        border-radius:10px;
                    ">
                        <b>Schleifen:</b> {row['schleifen']}<br>
                        <b>Gold:</b> {row['gold']}<br>
                        <b>Silber:</b> {row['silber']}<br>
                        <b>Bronze:</b> {row['bronze']}<br>
                        <b>Punkte:</b> {row['punkte']}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
    
        #st.bar_chart(ranking_points)

        
        # import altair as alt

        # st.subheader("Heatmap: Disziplinen × Pferde")

        # heatmap_df = df.copy()

        # heatmap = alt.Chart(heatmap_df).mark_rect().encode(
        #     x=alt.X("pferd:N", title="Pferd"),
        #     y=alt.Y("discipline:N", title="Disziplin"),
        #     color=alt.Color("schleifen:Q", title="Schleifen", scale=alt.Scale(scheme="blues")),
        #     tooltip=["pferd", "discipline", "schleifen", "gold", "silber", "bronze"]
        # )

        # st.altair_chart(heatmap, use_container_width=True)

        # st.subheader("Ranking der Pferde")

        # ranking_metric = st.selectbox(
        #     "Nach welcher Kennzahl sortieren?",
        #     ["schleifen", "gold", "silber", "bronze"]
        # )

        # ranking = df.groupby("pferd")[ranking_metric].sum().sort_values(ascending=False)

        # st.write(f"**Ranking nach {ranking_metric}:**")
        # st.dataframe(ranking)
        
        

else:
        st.warning("Keine Daten gefunden. Prüfe die Links oder den Seitenaufbau.")
