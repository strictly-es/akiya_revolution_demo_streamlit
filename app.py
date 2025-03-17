import streamlit as st
import requests
import json
import math
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

# ------------------------------
# ① 住所から座標取得
# ------------------------------
def get_coordinates_from_address(area: str, addr: str):
    url = f'https://jageocoder.info-proto.com/geocode?addr={addr}&area={area}&opts=all'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data and "node" in data[0]:
            lng = data[0]["node"]["x"]
            lat = data[0]["node"]["y"]
            return {"lng": lng, "lat": lat, "lng_4": round(lng, 4), "lat_4": round(lat, 4)}
    except requests.exceptions.RequestException:
        return None

# ------------------------------
# ② 緯度・経度 → タイル座標変換
# ------------------------------
def latlng_to_xyz(lat, lng, zoom):
    x = math.floor((lng + 180) / 360 * 2**zoom)
    y = math.floor((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * 2**zoom)
    return x, y

# ------------------------------
# ③ タイル座標から用途区分を取得
# ------------------------------
def is_point_in_polygon(point, polygon):
    return Polygon(polygon).contains(Point(point))

def get_use_area_ja(x, y, z, lng_4, lat_4, api_key):
    url = f'https://www.reinfolib.mlit.go.jp/ex-api/external/XKT002?response_format=geojson&z={z}&x={x}&y={y}&from=20223&to=20234'
    headers = {'Ocp-Apim-Subscription-Key': api_key}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        for feature in data.get("features", []):
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            if geometry.get("type") == "Polygon":
                for coordinates in geometry.get("coordinates", []):
                    if is_point_in_polygon((lng_4, lat_4), coordinates):
                        return properties.get("use_area_ja")
    except requests.exceptions.RequestException:
        return None

# ------------------------------
# ④ 用途地域 → 許可される事業を決定
# ------------------------------
def check_building_permissions(youto_chiiki, area_size):
    permissions = {
        "第１種低層住居専用地域": {"cafe": 150, "shareAtelier": 150, "accommodation": 0},
        "第２種低層住居専用地域": {"cafe": 150, "shareAtelier": 0, "accommodation": 0},
        "第１種中高層住居専用地域": {"cafe": 500, "shareAtelier": 150, "accommodation": 0},
        "第２種中高層住居専用地域": {"cafe": 1500, "shareAtelier": 150, "accommodation": 0},
        "第１種住居地域": {"cafe": 3000, "shareAtelier": 3000, "accommodation": 3000},
        "第２種住居地域": {"cafe": 10000, "shareAtelier": 3000, "accommodation": 10000},
        "準住居地域": {"cafe": 10000, "shareAtelier": 3000, "accommodation": 0},
        "近隣商業地域": {"cafe": float('inf'), "shareAtelier": float('inf'), "accommodation": float('inf')},
        "商業地域": {"cafe": float('inf'), "shareAtelier": float('inf'), "accommodation": float('inf')},
        "準工業地域": {"cafe": float('inf'), "shareAtelier": float('inf'), "accommodation": float('inf')},
        "工業地域": {"cafe": float('inf'), "shareAtelier": float('inf'), "accommodation": 0},
        "工業専用地域": {"cafe": 0, "shareAtelier": float('inf'), "accommodation": 0}
    }
    return [biz for biz, max_size in permissions.get(youto_chiiki, {}).items() if area_size <= max_size]

# ------------------------------
# ⑤ 人口データ取得
# ------------------------------
def get_PT0_values(x, y, z, lng_4, lat_4, api_key):
    url = f'https://www.reinfolib.mlit.go.jp/ex-api/external/XKT013?response_format=geojson&z={z}&x={x}&y={y}&from=20223&to=20234'
    headers = {'Ocp-Apim-Subscription-Key': api_key}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        for feature in data.get("features", []):
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            if geometry.get("type") == "Polygon":
                for coordinates in geometry.get("coordinates", []):
                    if is_point_in_polygon((lng_4, lat_4), coordinates):
                        return properties.get("PT00_2025")
    except requests.exceptions.RequestException:
        return None

# ------------------------------
# ⑥ 最寄り駅の距離を計算
# ------------------------------
def get_nearest_station_name(longitude, latitude, path= 'station_zenkoku.gpkg'):
    # 全国の駅データを読み込む
    gdf = gpd.read_file(path).to_crs(epsg=3857)

    # 指定座標の点を作成（WGS84 -> EPSG:3857 に変換）
    target_point = gpd.GeoDataFrame([{'geometry': Point(longitude, latitude)}], crs="EPSG:4326").to_crs(epsg=3857).geometry.iloc[0]

    # 各駅との距離を計算
    gdf['distance'] = gdf.geometry.distance(target_point)

    # 最短距離の駅を取得
    min_distance = gdf['distance'].min()
    nearest_stations = gdf[gdf['distance'] == min_distance]

    # 同じ駅名で複数レコードがある場合をまとめる
    result = nearest_stations.groupby('station_name').agg({
        'station_g_cd': 'first',
        'distance': 'first'
    }).reset_index()
    
    if result.empty:
        return None, None, None

    station_g_cd_val = result["station_g_cd"].values[0]
    station_name = result["station_name"].values[0]
    distance = result["distance"].values[0]

    # 該当する駅の路線情報を取得
    line_info = gdf[gdf['station_g_cd'] == station_g_cd_val]["line_name"].dropna().unique().tolist()

    return station_name, line_info, distance


# ------------------------------
# ⑦ 事業推薦・市場分析クラス
# ------------------------------
class MarketFactors:
    """ 市場環境のデータを保持 """
    def __init__(self, area_type: str, factors: dict, epsilon: float = 0.0):
        self.area_type = area_type
        self.factors = factors
        self.epsilon = epsilon

class MarketPotentialCalculator:
    """ 市場ポテンシャル(Potential_score)を計算 """
    FACTOR_RANGES = {
        "kamakura": {"population": 5000, "distance_from_station": 3200},
        "hayama": {"population": 1000, "distance_from_station": 3200},
        "zushi": {"population": 3000, "distance_from_station": 3200}
    }

    WEIGHTS = {
        "kamakura": {
            "cafe": {
                "population": 0.3,
                "distance_from_station": 0.7
            },
            "accommodation": {
                "population": 0.5,
                "distance_from_station": 0.5
            },
            "shareAtelier": {
                "population": 0.4,
                "distance_from_station": 0.6
            }
        },
        "hayama": {
             "cafe": {
                "population": 0.4,
                "distance_from_station": 0.6
            },
            "accommodation": {
                "population": 0.5,
                "distance_from_station": 0.5
            },
            "shareAtelier": {
                "population": 0.4,
                "distance_from_station": 0.6
            }
        },
        "zushi": {
             "cafe": {
                "population": 0.4,
                "distance_from_station": 0.6
            },
            "accommodation": {
                "population": 0.5,
                "distance_from_station": 0.5
            },
            "shareAtelier": {
                "population": 0.4,
                "distance_from_station": 0.6
            }
        }
    }

    @classmethod
    def _normalize_factor(cls, area_type, factor_name, value):
        max_val = cls.FACTOR_RANGES[area_type].get(factor_name, 0)
        
        if factor_name == "distance_from_station":
            return max(0.0, 1.0 - (value / max_val)) if value < max_val else 0.0
        return min(1.0, value / max_val)

    @classmethod
    def calculate(cls, factors, business_type):
        weights = cls.WEIGHTS[factors.area_type].get(business_type, {})
        weighted_sum = sum(weights.get(f, 0) * cls._normalize_factor(factors.area_type, f, v) for f, v in factors.factors.items())
        return weighted_sum + factors.epsilon

class Business:
    """ 事業の収支計算 """
    def __init__(self, name, initial_investment, users, unit_price, other_revenue, costs):
        self.name = name
        self.initial_investment = initial_investment
        self.users = users
        self.unit_price = unit_price
        self.other_revenue = other_revenue
        self.costs = costs

    def calc_monthly_revenue(self, market_score=1.0):
        return int(self.users * self.unit_price * market_score + self.other_revenue)

    def calc_monthly_cost(self):
        return sum(self.costs.values())

    def summary_dict(self, market_score):
        monthly_revenue = self.calc_monthly_revenue(market_score)
        monthly_cost = self.calc_monthly_cost()
        monthly_profit = monthly_revenue - monthly_cost
        profit_ratio = (monthly_profit / monthly_cost * 100) if monthly_cost else 0.0
        payback_period = (self.initial_investment / monthly_profit) / 12 if monthly_profit else float('inf')

        return {
            "name": self.name,
            "市場スコア": f"{market_score:.2f}",
            "初期投資額": f"{self.initial_investment:,}円",
            "月間売上": f"{monthly_revenue:,}円",
            "月間経費": f"{monthly_cost:,}円",
            "月間利益": f"{monthly_profit:,}円",
            "収益率": f"{profit_ratio:.1f}%",
            "回収期間": f"{payback_period:.2f}年"
        }

# ------------------------------
# Streamlit UI
# ------------------------------
st.title("AKIYA Revolution!")

# ユーザー入力
area = st.text_input("都道府県を入力", "神奈川県")
addr = st.text_input("住所を入力", "鎌倉市由比ケ浜1-12-8")
# initial_investment = st.number_input("初期投資額 (円)", min_value=1_000_000, max_value=100_000_000, value=10_000_000, step=500_000)
area_size = st.number_input("建物面積 (㎡)", min_value=50, max_value=10_000, value=100, step=50)

# st.write(f"initial_investment: {initial_investment}")

if st.button("事業を推薦"):
    # 1️⃣ 住所から座標を取得
    coordinates = get_coordinates_from_address(area, addr)
    if not coordinates:
        st.error("住所の緯度経度が取得できませんでした。")
        st.stop()

    lng, lat, lng_4, lat_4 = coordinates.values()

    # 2️⃣ タイル座標変換
    zoom = 15
    x, y = latlng_to_xyz(lat, lng, zoom)

    # 3️⃣ 用途地域取得
    api_key = '43f3468632cc42849065bd7e48eabe87'
    use_area_ja = get_use_area_ja(x, y, zoom, lng_4, lat_4, api_key)
    st.write(f"用途地域 (use_area_ja): {use_area_ja}")

    # 4️⃣ 許可される事業の判定
    #area_size = 2000
    allowed_buildings = check_building_permissions(use_area_ja, area_size)
    st.write(f"許可される事業 (allowed_buildings): {allowed_buildings}")

    # 5️⃣ 人口データ取得
    population = get_PT0_values(x, y, zoom, lng_4, lat_4, api_key)
    st.write(f"人口データ: {population}")

    # 6️⃣ 最寄り駅の距離取得
    station_name, line_name, distance = get_nearest_station_name(lng_4, lat_4)
    st.write(f"駅からの距離: {distance}")
    st.write(f"最寄り駅: {station_name}")

    # 7️⃣ 事業推薦
    area_type = "kamakura" if "鎌倉" in addr else "hayama"
    market_factors = MarketFactors(
        area_type=area_type,
        factors={
            "population": population,
            "distance_from_station": distance
        },
        epsilon=0.5
    )

    #入力値
    other_revenue=0

    businesses = {
    "cafe": Business(
        name="カフェ",
        initial_investment=10_000_000,
        users=200,
        unit_price=1500,
        other_revenue=other_revenue,
        costs={
            "人件費": 2_000_000,
            "水道光熱費": 50_000,
            "通信費": 6_000,
            "清掃費": 70_000,
            "消耗品費": 100_000,
            "保険料": 5_000,
            "修繕費": 0,
            "地代家賃": 150_000,
            "その他経費": 0
        }
    ),
    "accommodation": Business(
        name="宿泊施設",
        initial_investment=15_000_000,
        users=35,
        unit_price=60000,
        other_revenue=other_revenue,
        costs={
            "人件費": 200_000,
            "水道光熱費": 50_000,
            "通信費": 5_000,
            "清掃費": 50_000,
            "消耗品費": 700_000,
            "保険料": 2_000,
            "修繕費": 0,
            "地代家賃": 350_000,
            "その他経費": 192_000
        },
    ),
    "shareAtelier": Business(
        name="コワーキングスペース",
        initial_investment=12_000_000,
        users=15,
        unit_price=25000,
        other_revenue=other_revenue,
        costs={
            "人件費": 60_000,
            "水道光熱費": 20_000,
            "通信費": 7_000,
            "清掃費": 100_000,
            "消耗品費": 0,
            "保険料": 15_000,
            "修繕費": 0,
            "地代家賃": 30_000,
            "その他経費": 50_000
        }
    )
    }

    results = []
    for name in allowed_buildings:
        market_score = MarketPotentialCalculator.calculate(market_factors, name)
        results.append(businesses[name].summary_dict(market_score))

        # 収益率の最大値と回収期間の最小値を見つける
    best_profit = max(results, key=lambda r: float(r['収益率'].replace('%', '')))
    best_payback = min(results, key=lambda r: float(r['回収期間'].replace('年', '')))

    # ハイライト用のタイトル
    st.markdown("### 🏆 **おすすめの事業**")

    # 収益率最大と回収期間最小が同じなら1つだけ表示
    if best_profit == best_payback:
        st.success(f"🌟 **{best_profit['name']}** が最もおすすめです！ 収益率: {best_profit['収益率']}")
    else:
        st.success(f"💰 **収益率が最も高い:** {best_profit['name']} 収益率: {best_profit['収益率']}")
        #st.warning(f"⏳ **回収期間が最も短い:** {best_payback['name']}（{best_payback['回収期間']}）")


    # 結果表示
    st.markdown("### 📊 **全事業の分析結果**")
    for r in results:
        st.subheader(f"{r['name']} の結果")
        st.write(f"・市場スコア : {r['市場スコア']}")
        st.write(f"・初期投資額 : {r['初期投資額']}")
        st.write(f"・月間売上 : {r['月間売上']}")
        st.write(f"・月間経費 : {r['月間経費']}")
        st.write(f"・月間利益 : {r['月間利益']}")
        st.write(f"・収益率 : {r['収益率']}")
        #st.write(f"・回収期間 : {r['回収期間']}")