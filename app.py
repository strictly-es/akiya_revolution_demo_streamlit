import streamlit as st

class MarketFactors:
    """ 市場環境のデータを保持 """
    def __init__(self, area_type: str, factors: dict, epsilon: float = 0.0):
        self.area_type = area_type
        self.factors = factors
        self.epsilon = epsilon

class MarketPotentialCalculator:
    """ 市場ポテンシャル(Potential_score)を計算 """
    FACTOR_RANGES = {
        "kamakura": {
            "population": 1000000, "distance_from_station": 20,
            "tourist": 100000, "household_income": 10000000
        },
        "hayama": {
            "population": 500000, "distance_from_station": 40,
            "tourist": 3000, "household_income": 8000000
        }
    }

    WEIGHTS = {
        "kamakura": {
            "cafe": {"population": 0.4, "distance_from_station": 0.2, "tourist": 0.2, "household_income": 0.2},
            "accommodation": {"population": 0.2, "distance_from_station": 0.2, "tourist": 0.3, "household_income": 0.3},
            "shareAtelier": {"population": 0.25, "distance_from_station": 0.25, "tourist": 0.25, "household_income": 0.25}
        },
        "hayama": {
            "cafe": {"population": 0.2, "distance_from_station": 0.2, "tourist": 0.3, "household_income": 0.3},
            "accommodation": {"population": 0.4, "distance_from_station": 0.1, "tourist": 0.4, "household_income": 0.1},
            "shareAtelier": {"population": 0.25, "distance_from_station": 0.25, "tourist": 0.25, "household_income": 0.25}
        }
    }

    @classmethod
    def _normalize_factor(cls, area_type, factor_name, value):
        max_val = cls.FACTOR_RANGES[area_type].get(factor_name, 0)
        if factor_name == "distance_from_station":
            return max(0.0, 1.0 - (value / max_val)) if value < max_val else 0.0
        return min(1.0, value / max_val)

    @classmethod
    def calculate(cls, factors: MarketFactors, business_type: str):
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

st.title("AKIYA Revolution!")

# ラベル（表示名）と対応する値の辞書
area_options = {
    "鎌倉市由比ヶ浜 / 小売店": "kamakura",
    "葉山町堀内 / 戸建住宅": "hayama"
}

# ユーザーに表示する選択肢（キーのリスト）
selected_label = st.selectbox("住所 / 従前の利用用途", list(area_options.keys()))

# 選択された値を取得（辞書から対応する value を取得）
area_type = area_options[selected_label]
area_type = "kamakura" if "kamakura" in area_type else "hayama"
#st.write(f"選択されたエリア: {area_type}")

if area_type == "kamakura":
    market_factors = MarketFactors(
        area_type="kamakura",
        factors={
            "population": 800000, 
            "distance_from_station": 10, 
            "tourist": 90000, 
            "household_income": 7_000_000
        },
        epsilon=0.5
    )

    businesses = {
        "cafe": Business(
            name="カフェ",
            initial_investment=25_000_000, 
            users=2_500,
            unit_price=1_300, 
            other_revenue=50_000,
            costs={
                "人件費": 1_500_000,
                "水道光熱費": 50_000,
                "通信費": 6_000,
                "清掃費": 70_000,
                "消耗品費": 150_000,
                "保険料": 5_000,
                "修繕費": 0, 
                "地代家賃": 150_000,
                "その他経費": 821_500
            }
        ),
        "accommodation": Business(
            name="宿泊施設",
            initial_investment=65_000_000,
            users=150,
            unit_price=25_000,
            other_revenue=500_000,
            costs={
                "人件費": 3_000_000,
                "水道光熱費": 50_000,
                "通信費": 6_000,
                "清掃費": 500_000,
                "消耗品費": 700_000,
                "保険料": 2_000,
                "修繕費": 0,
                "地代家賃": 200_000,
                "その他経費": 192_000
            },
        ),
        "shareAtelier": Business(
            name="シェアアトリエ",
            initial_investment=40_000_000,
            users=30,
            unit_price=65_000,
            other_revenue=500_000,
            costs={
                "人件費": 2_000_000,
                "水道光熱費": 30_000,
                "通信費": 6_000,
                "清掃費": 100_000,
                "消耗品費": 50_000,
                "保険料": 2_000,
                "修繕費": 0,
                "地代家賃": 100_000,
                "その他経費": 100_000
            }
        )
    }

else:  # hayama
    market_factors = MarketFactors(
        area_type="hayama",
        factors={
            "population": 600000,
            "distance_from_station": 25,
            "tourist": 50000,
            "household_income": 6_000_000
        },
        epsilon=0.5
    )

    # 宿泊施設を最強: 初期投資下げ & 利用人数↑ & 単価↑
    businesses = {
        "cafe": Business(
            name="カフェ",
            initial_investment=30_000_000,
            users=2_500,
            unit_price=1_100,
            other_revenue=50_000,
            costs={
                "人件費": 1_500_000,
                "水道光熱費": 50_000,
                "通信費": 6_000,
                "清掃費": 70_000,
                "消耗品費": 150_000,
                "保険料": 5_000,
                "修繕費": 0, 
                "地代家賃": 150_000,
                "その他経費": 821_500
            }
        ),
        "accommodation": Business(
            name="宿泊施設",
            initial_investment=60_000_000, 
            users=150,                      
            unit_price=30_000,          
            other_revenue=500_000,
            costs={
                "人件費": 3_000_000,
                "水道光熱費": 50_000,
                "通信費": 6_000,
                "清掃費": 500_000,
                "消耗品費": 700_000,
                "保険料": 2_000,
                "修繕費": 0,
                "地代家賃": 200_000,
                "その他経費": 192_000
            },
        ),
        "shareAtelier": Business(
            name="シェアアトリエ",
            initial_investment=40_000_000,
            users=30,
            unit_price=65_000,
            other_revenue=500_000,
            costs={
                "人件費": 2_000_000,
                "水道光熱費": 30_000,
                "通信費": 6_000,
                "清掃費": 100_000,
                "消耗品費": 50_000,
                "保険料": 2_000,
                "修繕費": 0,
                "地代家賃": 100_000,
                "その他経費": 100_000
            }
        )
    }



# 分析実行ボタン
if st.button("事業を推薦"):
    results = []
    for name, business in businesses.items():
        market_score = MarketPotentialCalculator.calculate(market_factors, name)
        results.append(business.summary_dict(market_score))

    # 収益率の最大値と回収期間の最小値を見つける
    best_profit = max(results, key=lambda r: float(r['収益率'].replace('%', '')))
    best_payback = min(results, key=lambda r: float(r['回収期間'].replace('年', '')))

    # ハイライト用のタイトル
    st.markdown("### 🏆 **おすすめの事業**")

    # 収益率最大と回収期間最小が同じなら1つだけ表示
    if best_profit == best_payback:
        st.success(f"🌟 **{best_profit['name']}** が最もおすすめです！")
    else:
        st.success(f"💰 **収益率が最も高い:** {best_profit['name']}（{best_profit['収益率']}）")
        st.warning(f"⏳ **回収期間が最も短い:** {best_payback['name']}（{best_payback['回収期間']}）")

    # 通常の結果表示
    st.markdown("### 📊 **全事業の分析結果**")
    for r in results:
        #highlight = "🟢" if r == best_profit or r == best_payback else ""
        st.subheader(f"{r['name']} の結果")
        st.write(f"・市場スコア : {r['市場スコア']}")
        st.write(f"・初期投資額 : {r['初期投資額']}")
        st.write(f"・月間売上 : {r['月間売上']}")
        st.write(f"・月間経費 : {r['月間経費']}")
        st.write(f"・月間利益 : {r['月間利益']}")
        st.write(f"・収益率 : {r['収益率']}")
        st.write(f"・回収期間 : {r['回収期間']}")