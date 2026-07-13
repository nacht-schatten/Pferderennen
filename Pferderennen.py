import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

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
                "owner": owner_name

            })

    return data



# ---------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------
st.title("Rocky's Pferderennen")



all_data = []

urls = ["https://www.howrse.de/elevage/fiche/?id=106862838",
        "https://www.howrse.de/elevage/fiche/?id=108115577",
        "https://www.howrse.de/elevage/fiche/?id=108180445",
        "https://www.howrse.de/elevage/fiche/?id=107497259",
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
            "owner": "first"
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




        
       
        # Top 3 nach Punkten
        top3 = ranking_points.head(3)

        if len(top3) >= 3:
            p1_id, p2_id, p3_id = top3.index[0], top3.index[1], top3.index[2]

            p1 = horse_info.loc[horse_info["horse_id"] == p1_id, "pferd"].iloc[0]
            p2 = horse_info.loc[horse_info["horse_id"] == p2_id, "pferd"].iloc[0]
            p3 = horse_info.loc[horse_info["horse_id"] == p3_id, "pferd"].iloc[0]

            v1, v2, v3 = top3.iloc[0], top3.iloc[1], top3.iloc[2]

            col1, col2, col3 = st.columns([1, 1, 1])

            with col2:
                st.write(f"#### 🥇 {p1}")
                st.write(f"**{v1} Punkte**")

            with col1:
                st.write(f"#### 🥈 {p2}")
                st.write(f"**{v2} Punkte**")

            with col3:
                st.write(f"#### 🥉 {p3}")
                st.write(f"**{v3} Punkte**")
        else:
            st.info("Für ein Podest werden mindestens 3 Pferde benötigt.")
        
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
        


# Unsichtbare Y-Achse
        y_axis = alt.Y(
            "unique:N",
            sort=alt.SortField(field="punkte"),
            axis=None
        )
        
        max_punkte = chart_data["punkte"].max()
        x_max = max_punkte * 1.05

# Balken
        bar = alt.Chart(chart_data).mark_bar(
            color="#e7f9e4"
        ).encode(
            x=alt.X("bar_x:Q", title="Punkte",  scale=alt.Scale(domain=[0, x_max])),
            y=y_axis,
        )

# Text (eigene X-Achse, links vom Balken)
        text = alt.Chart(chart_data).mark_text(
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
        icons = alt.Chart(chart_data).mark_image(
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

        html = chart.to_html(embed_options={"renderer": "svg"})

        

        components.html(
            html,
            height=60 * len(chart_data) + 100,
            scrolling=False
        )








        st.subheader("Gesamtübersicht pro Pferd (alle Disziplinen)")
        overview = totals_per_horse_sorted.reset_index().merge(
            horse_info,
            on="horse_id",
            how="left"
        )
        

        overview = overview.reset_index(drop=True)
        overview.index = overview.index + 1

        st.dataframe(overview[["pferd", "schleifen", "gold", "silber", "bronze", "punkte"]])


        
        

       
        
        #Pferdekarten:

        for horse_id, row in totals_per_horse.iterrows():
            
            horse_name = df[df["horse_id"] == horse_id]["pferd"].iloc[0]
            owner_name = df[df["horse_id"] == horse_id]["owner"].iloc[0]
            img_url = df[df["horse_id"] == horse_id]["image"].dropna().iloc[0]

            st.write(f"## {horse_name}")

            st.write(f"**Besitzer:** {owner_name}")
            


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
                
                st.markdown(f"**Schleifen:** {row['schleifen']}")
                st.markdown(f"**Gold:** {row['gold']}")
                st.markdown(f"**Silber:** {row['silber']}")
                st.markdown(f"**Bronze:** {row['bronze']}")
                st.markdown(f"**Punkte:** {row['punkte']}")
                
    
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
