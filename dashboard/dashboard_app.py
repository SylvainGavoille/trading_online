"""
Dashboard Streamlit Interactif - Quantum Trader
Exploration et analyse d'actions avec intégration LLM DSPy
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta, datetime, timezone
import hashlib
import dspy
import feedparser
import requests
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from dateutil import parser as dtparser
from typing import List, Dict, Optional, Tuple
import yaml
import sys
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load .env from project root (one level above dashboard/)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Add parent directory to path for local imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data.dynamic_stocks import get_symbol_name_map
from src.api.ib_connector import IBClient
from src.agents.stock_search_agent import (
    simple_stock_search,
    StockSearchAgent,
    parse_stock_suggestions,
)

# Import portfolio and risk profile managers
from portfolio_manager import (
    PortfolioManager,
    configure_ibkr_client as configure_pm_client,
)
from risk_profile_manager import RiskProfileManager, RISK_PROFILES
from modeling_tab import render_modeling_tab
from gcs_data import read_price_history_from_gcs, get_gcs_data_uri, list_price_symbols_from_gcs

# Page configuration
st.set_page_config(
    page_title="Quantum Trader - Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Load configuration
@st.cache_resource
def load_config():
    """Charge la configuration du système"""
    try:
        # Chemin relatif depuis dashboard/
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "config", "config.yaml"
        )
        with open(config_path, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        return {}


def save_risk_config_to_yaml(
    max_loss_per_trade_pct: float, max_portfolio_risk_pct: float
):
    """
    Met à jour les paramètres de risque dans config.yaml (fichier utilisé par run_trader).
    Préserve les commentaires et l'ordre des clés existantes.

    Returns:
        True si succès, str d'erreur sinon.
    """
    import re

    config_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "config", "config.yaml"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        def replace_scalar(key: str, new_val: float, text: str) -> str:
            """Remplace la valeur d'une clé YAML scalaire en préservant les commentaires."""
            pattern = rf"^(\s*{re.escape(key)}:\s*)[\d.]+(.*)$"
            return re.sub(pattern, rf"\g<1>{new_val}\2", text, flags=re.MULTILINE)

        content = replace_scalar(
            "max_loss_per_trade", round(max_loss_per_trade_pct / 100, 6), content
        )
        content = replace_scalar(
            "max_portfolio_exposure", round(max_portfolio_risk_pct / 100, 6), content
        )

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        return str(e)


# Connexion IBKR (partagée pour toute la session Streamlit)
@st.cache_resource
def get_ib_client() -> Optional[IBClient]:
    """Initialise et connecte le client IBKR. Retourne None si la connexion échoue."""
    try:
        config = load_config()
        client = IBClient(config)
        if client.connect_and_run():
            configure_pm_client(client)
            return client
        return None
    except Exception:
        return None


# Configuration DSPy pour l'interaction LLM
@st.cache_resource
def setup_dspy():
    """Configure DSPy avec le LLM par défaut (Ollama)"""
    try:
        config = load_config()
        llm_config = config.get("multi_agent", {})

        # Lire la configuration du provider
        provider = llm_config.get("llm_provider", "ollama")
        model = llm_config.get("model_name", "deepseek-r1:14b")

        # Configuration selon le provider
        if provider == "openai":
            # OpenAI (nécessite OPENAI_API_KEY)
            lm = dspy.LM(model=f"openai/{model}", api_key=os.getenv("OPENAI_API_KEY"))
        elif provider == "anthropic":
            # Anthropic (nécessite ANTHROPIC_API_KEY)
            lm = dspy.LM(
                model=f"anthropic/{model}", api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        else:
            # Ollama par défaut (local, gratuit)
            lm = dspy.LM(
                model=f"ollama/{model}",
                api_base="http://localhost:11434",
                api_key="ollama",
            )

        dspy.configure(lm=lm)
        return True
    except Exception as e:
        # Si échec, le dashboard fonctionnera sans IA
        return False


# Signature DSPy pour suggérer des actions
class StockSuggestion(dspy.Signature):
    """Suggère des actions à analyser basées sur une requête utilisateur"""

    user_query: str = dspy.InputField(
        desc="Requête de l'utilisateur (ex: 'tech stocks', 'energy sector')"
    )
    suggestions: List[str] = dspy.OutputField(
        desc="Liste de 5-10 symboles d'actions suggérées"
    )
    explanation: str = dspy.OutputField(desc="Brève explication des suggestions")


class StockAnalysis(dspy.Signature):
    """Analyse une action et fournit des insights"""

    symbol: str = dspy.InputField(desc="Symbole de l'action")
    price_data: str = dspy.InputField(desc="Données de prix récentes")
    period: str = dspy.InputField(desc="Période d'analyse")
    analysis: str = dspy.OutputField(desc="Analyse détaillée de l'action")
    key_insights: List[str] = dspy.OutputField(desc="Points clés à retenir")


# Modules DSPy
suggest_stocks = dspy.ChainOfThought(StockSuggestion)
analyze_stock = dspy.ChainOfThought(StockAnalysis)

# Period definitions (days of history to load from Parquet)
PERIODS = {
    "5 Jours": 5,
    "1 Mois": 30,
    "3 Mois": 90,
    "6 Mois": 180,
    "1 An": 365,
}

# Liste de stocks populaires par catégorie
POPULAR_STOCKS = {
    "Tech": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "TSLA", "AMZN", "NFLX"],
    "Finance": ["JPM", "BAC", "WFC", "GS", "MS", "C", "USB"],
    "Energie": ["XOM", "CVX", "COP", "SLB", "OXY", "EOG"],
    "Santé": ["JNJ", "UNH", "PFE", "ABBV", "TMO", "LLY"],
    "Consommation": ["WMT", "PG", "KO", "PEP", "MCD", "NKE"],
    "Industrie": ["BA", "CAT", "GE", "MMM", "HON", "UPS"],
}

ALL_STOCKS = []
for stocks in POPULAR_STOCKS.values():
    ALL_STOCKS.extend(stocks)
ALL_STOCKS = sorted(list(set(ALL_STOCKS)))


def get_last_trading_date() -> date:
    """Retourne la dernière date de trading attendue (dernier jour ouvré avant aujourd'hui)."""
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d -= timedelta(days=1)
    return d


def load_from_gcs(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    """Load OHLCV data for *symbol* from the GCS bucket."""
    df = read_price_history_from_gcs(symbol, start_date, end_date)
    return df if df is not None else pd.DataFrame()


@st.cache_data(ttl=300)
def get_stock_data(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Charge les données historiques depuis GCS."""
    end_date = get_last_trading_date()
    start_date = end_date - timedelta(days=days)
    df = load_from_gcs(symbol, start_date, end_date)
    if df is not None and not df.empty:
        return df
    return None


@st.cache_data(ttl=3600)
def get_parquet_symbols() -> set:
    """Retourne l'ensemble des symboles disponibles dans GCS (dernier jour disponible)."""
    return list_price_symbols_from_gcs()


@st.cache_data(ttl=3600)
def get_symbol_labels() -> dict:
    """
    Retourne un dict {symbol: label_affichage} pour enrichir le selectbox.
    Exemple : {'AAPL': 'AAPL — Apple Inc. (Technology)', ...}
    """
    name_map = get_symbol_name_map()
    labels = {}
    for sym, (name, sec_type, industry) in name_map.items():
        label = sym
        if name and name != sym:
            label += f" — {name}"
        if industry and industry not in ("Unknown", "N/A", ""):
            label += f" ({industry})"
        elif sec_type and sec_type not in ("", "Unknown"):
            label += f" [{sec_type}]"
        labels[sym] = label
    return labels


def calculate_statistics(df: pd.DataFrame) -> Dict:
    """
    Calcule les statistiques sur les données de prix

    Args:
        df: DataFrame avec les données OHLCV

    Returns:
        Dictionnaire avec les statistiques
    """
    if df is None or df.empty:
        return {}

    close_prices = df["Close"]

    first_close = close_prices.iloc[0]
    # Guard against a zero/NaN opening price (would yield inf/NaN change_pct)
    if pd.isna(first_close) or first_close == 0:
        change_pct = 0
    else:
        change_pct = (close_prices.iloc[-1] - first_close) / first_close * 100

    stats = {
        "min": close_prices.min(),
        "max": close_prices.max(),
        "mean": close_prices.mean(),
        "current": close_prices.iloc[-1],
        "start": first_close,
        "change": close_prices.iloc[-1] - first_close,
        "change_pct": change_pct,
        "volatility": close_prices.std(),
        "volume_avg": df["Volume"].mean(),
        "volume_total": df["Volume"].sum(),
    }

    return stats


def create_candlestick_chart(
    df: pd.DataFrame, symbol: str, period_name: str
) -> go.Figure:
    """
    Crée un graphique en chandelier interactif avec curseur

    Args:
        df: DataFrame avec les données OHLCV
        symbol: Symbole de l'action
        period_name: Nom de la période affichée

    Returns:
        Figure Plotly
    """
    # Créer le graphique avec 2 sous-graphiques (prix + volume)
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f"{symbol} - Prix ({period_name})", "Volume"),
    )

    # Chandelier pour les prix
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Prix",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1,
        col=1,
    )

    # Barre de volume
    colors = [
        "#26a69a" if close > open else "#ef5350"
        for close, open in zip(df["Close"], df["Open"])
    ]

    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["Volume"],
            name="Volume",
            marker_color=colors,
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    # Mise en forme
    fig.update_layout(
        height=700,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=50, r=50, t=50, b=50),
    )

    fig.update_xaxes(tickformat="%d/%m/%Y", title="Date", row=2, col=1)
    fig.update_yaxes(title_text="Prix ($)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig


def llm_stock_suggestions(query: str, use_llm: bool = False) -> tuple[List[dict], str]:
    """
    Recherche des actions basées sur la requête avec agent de recherche

    Args:
        query: Requête de l'utilisateur
        use_llm: Si True, utilise le LLM pour filtrer (nécessite Ollama)

    Returns:
        (liste de dictionnaires avec symbol/name/description, explication)
    """
    parquet_syms = get_parquet_symbols()

    try:
        if use_llm:
            # Version avec LLM (nécessite Ollama configuré)
            agent = StockSearchAgent()
            result = agent(query, max_results=10, parquet_symbols=parquet_syms)

            # Parser les résultats
            stocks = parse_stock_suggestions(result.selected_stocks)
            return stocks, result.explanation
        else:
            # Version simple sans LLM (toujours disponible)
            stocks, explanation = simple_stock_search(
                query, max_results=10, parquet_symbols=parquet_syms
            )
            return stocks, explanation

    except Exception as e:
        # Fallback sur recherche simple en cas d'erreur
        stocks, explanation = simple_stock_search(
            query, max_results=10, parquet_symbols=parquet_syms
        )
        return stocks, explanation


def llm_stock_analysis(
    symbol: str, df: pd.DataFrame, period: str
) -> tuple[str, List[str]]:
    """
    Utilise le LLM pour analyser une action

    Args:
        symbol: Symbole de l'action
        df: DataFrame avec les données
        period: Période d'analyse

    Returns:
        (analyse détaillée, points clés)
    """
    try:
        # Préparer un résumé des données
        stats = calculate_statistics(df)
        price_summary = f"""
        Prix actuel: ${stats.get('current', 0):.2f}
        Min: ${stats.get('min', 0):.2f}
        Max: ${stats.get('max', 0):.2f}
        Variation: {stats.get('change_pct', 0):.2f}%
        Volatilité: ${stats.get('volatility', 0):.2f}
        """

        result = analyze_stock(symbol=symbol, price_data=price_summary, period=period)
        return result.analysis, result.key_insights
    except Exception as e:
        st.error(f"Erreur analyse LLM: {e}")
        return "", []


# ==================== RSS NEWS ====================

RSS_FEEDS: List[Tuple[str, str]] = [
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("Investing.com", "https://www.investing.com/rss/news.rss"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
]


@dataclass
class NewsItem:
    source: str
    title: str
    link: str
    published_at: Optional[datetime]
    summary: str
    full_content: str = ""  # populated from RSS content:encoded when available

    @property
    def uid(self) -> str:
        return hashlib.sha256(self.link.encode()).hexdigest()


def _rss_to_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = dtparser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _html_to_text(html: str) -> str:
    """Strip HTML tags and return clean plain text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n\n", strip=True)


def _fetch_feed(source: str, url: str, timeout: int = 15) -> List[NewsItem]:
    headers = {"User-Agent": "Mozilla/5.0 (news-aggregator)"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    items: List[NewsItem] = []
    for e in feed.entries:
        title = (getattr(e, "title", "") or "").strip()
        link = (getattr(e, "link", "") or "").strip()
        summary = (getattr(e, "summary", "") or "").strip()
        pub_raw = getattr(e, "published", None) or getattr(e, "updated", None) or ""
        if not title or not link:
            continue

        # Try to get full content from RSS content:encoded / content field
        full_content = ""
        content_list = getattr(e, "content", None)
        if content_list:
            raw_html = content_list[0].get("value", "")
            if raw_html:
                full_content = _html_to_text(raw_html)

        items.append(
            NewsItem(
                source=source,
                title=title,
                link=link,
                published_at=_rss_to_dt(pub_raw),
                summary=summary,
                full_content=full_content,
            )
        )
    return items


def fetch_rss_news(
    keywords: List[str],
    tickers: List[str],
    sources: Optional[List[str]] = None,
) -> Tuple[List[NewsItem], List[str]]:
    feeds = [(s, u) for s, u in RSS_FEEDS if sources is None or s in sources]
    all_items: List[NewsItem] = []
    errors: List[str] = []
    for source, url in feeds:
        try:
            all_items.extend(_fetch_feed(source, url))
        except Exception as ex:
            errors.append(f"{source}: {ex}")

    # Deduplicate by uid
    seen: set = set()
    unique: List[NewsItem] = []
    for it in all_items:
        if it.uid not in seen:
            seen.add(it.uid)
            unique.append(it)

    # Filter
    def _matches(item: NewsItem) -> bool:
        if not keywords and not tickers:
            return True
        hay = f"{item.title}\n{item.summary}\n{item.link}".lower()
        kw_ok = any(k.lower() in hay for k in keywords) if keywords else True
        tk_ok = any(t.lower() in hay for t in tickers) if tickers else True
        return kw_ok and tk_ok

    filtered = [it for it in unique if _matches(it)]
    filtered.sort(
        key=lambda x: x.published_at.timestamp() if x.published_at else 0, reverse=True
    )
    return filtered, errors


def _fetch_article_text(url: str) -> str:
    """Fetch a URL and extract readable article text via BeautifulSoup.

    Tries curl_cffi (Chrome TLS impersonation) first to bypass Cloudflare/403,
    then falls back to plain requests.
    Returns empty string on failure (caller should fall back to RSS summary).

    SSRF guard: only http(s) URLs are fetched (RSS feeds are untrusted), and
    the downloaded body is capped to avoid pulling huge responses into memory.
    """
    # SSRF guard: reject anything that isn't a plain http(s) URL early.
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""

    # Cap how much of the response body we read (~1 MB).
    max_bytes = 1_000_000

    html = ""
    # 1st attempt: curl_cffi with Chrome impersonation (handles Cloudflare)
    try:
        r = cffi_requests.get(url, impersonate="chrome120", timeout=15)
        r.raise_for_status()
        html = r.text[:max_bytes]
    except Exception:
        pass

    # 2nd attempt: plain requests with browser-like headers
    if not html:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
            }
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            html = r.text[:max_bytes]
        except Exception:
            pass

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for tag in soup(
        [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "aside",
            "iframe",
            "noscript",
            "figure",
            "form",
            "button",
        ]
    ):
        tag.decompose()

    # Try semantic containers from most to least specific
    for selector in [
        "article",
        "main",
        "[role='main']",
        ".article-body",
        ".article-content",
        ".post-content",
        ".story-body",
        ".entry-content",
        "#article-body",
        ".body-copy",
    ]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n\n", strip=True)
            if len(text) > 300:
                return text

    # Fallback: collect all substantial paragraphs
    paras = [
        p.get_text(strip=True)
        for p in soup.find_all("p")
        if len(p.get_text(strip=True)) > 60
    ]
    if paras:
        return "\n\n".join(paras)

    return ""


# ==================== INTERFACE STREAMLIT ====================


def main():
    """Application principale"""

    # Titre principal
    st.title("📈 Quantum Trader - Dashboard Interactif")

    # Initialiser IBKR dès le démarrage (connexion partagée).
    # Le client est récupéré plus bas via get_ib_client() (ressource cachée).

    # Sidebar - Menu de navigation
    st.sidebar.title("Navigation")

    MENU_ITEMS = [
        "🔍 Exploration",
        "📊 Portfolio",
        "📰 Actualités",
        "⚙️ Configuration",
        "🤖 Modeling",
        "📚 Documentation",
    ]

    if "tab_selection" not in st.session_state:
        st.session_state["tab_selection"] = MENU_ITEMS[0]

    for item in MENU_ITEMS:
        is_active = st.session_state["tab_selection"] == item
        if st.sidebar.button(
            item,
            use_container_width=True,
            type="primary" if is_active else "secondary",
            key=f"nav_{item}",
        ):
            st.session_state["tab_selection"] = item
            st.rerun()

    tab_selection = st.session_state["tab_selection"]

    # --- IBKR connection status in sidebar ---
    st.sidebar.divider()
    ib = get_ib_client()  # cached resource — single shared connection
    if ib is not None and ib.isConnected():
        st.sidebar.success("🟢 IBKR connecté")
        n_rec = getattr(ib, "reconnect_attempts", 0)
        last_rec = getattr(ib, "last_reconnect_at", None)
        if n_rec > 0 and last_rec:
            st.sidebar.caption(
                f"Reconnexions : {n_rec} "
                f"(dernière : {last_rec.strftime('%H:%M:%S')})"
            )
    else:
        st.sidebar.error("🔴 IBKR déconnecté")
        st.sidebar.caption("Le watchdog tente de reconnecter automatiquement.")
        if st.sidebar.button("🔄 Reconnecter manuellement", use_container_width=True):
            # Clear the cached resource so get_ib_client() creates a fresh client
            get_ib_client.clear()
            st.rerun()

    # ==================== TAB: EXPLORATION ====================
    if tab_selection == "🔍 Exploration":
        st.header("🔍 Market Exploration")

        # Initialiser DSPy
        dspy_ready = setup_dspy()

        # Section 1: Stock search (Yahoo Finance primary, optional AI)
        with st.expander("💡 Stock Search", expanded=False):
            st.write("🔍 Search for stocks, ETFs, or indices by keywords")

            col_query, col_btn = st.columns([3, 1])

            with col_query:
                user_query = st.text_input(
                    "What are you looking for?",
                    placeholder="Ex: tech ETF, renewable energy, bitcoin, dividends...",
                    key="llm_query",
                )

            with col_btn:
                st.write("")  # Spacer
                st.write("")  # Spacer
                search_button = st.button("🔍 Search", use_container_width=True)

            use_ai_search = st.checkbox(
                "🤖 AI-assisted search (much slower — requires Ollama)",
                value=False,
                help="Uses the local LLM (deepseek-r1:14b) to interpret and rank results. "
                "Can take 1-5 minutes. Leave unchecked for fast Yahoo Finance search.",
            )

            if search_button:
                if user_query:
                    spinner_msg = (
                        "🔎 AI search in progress (this may take several minutes)..."
                        if use_ai_search
                        else "🔎 Searching via Yahoo Finance..."
                    )
                    with st.spinner(spinner_msg):
                        stocks, explanation = llm_stock_suggestions(
                            user_query, use_llm=(use_ai_search and dspy_ready)
                        )
                        if use_ai_search and not dspy_ready:
                            st.warning(
                                "⚠️ Ollama not available — fell back to Yahoo Finance search."
                            )

                    # Persist results in session state so selections survive reruns
                    if stocks:
                        st.session_state["search_stocks"] = stocks
                        st.session_state["search_explanation"] = explanation
                    else:
                        st.session_state["search_stocks"] = []
                        st.session_state["search_explanation"] = ""
                        st.warning(
                            f"No instruments found for '{user_query}' in the local Parquet database."
                        )
                        st.info(
                            "💡 Try keywords like: tech, finance, ETF, bitcoin, energy, dividends..."
                        )
                else:
                    st.warning("⚠️ Please enter a search query")

            # Display results from session state (persist across reruns / row selection)
            _search_stocks = st.session_state.get("search_stocks", [])
            _search_expl = st.session_state.get("search_explanation", "")

            if _search_stocks:
                st.success(f"✅ {len(_search_stocks)} result(s) found")

                with st.expander("💡 Search Analysis", expanded=False):
                    st.info(_search_expl)

                st.write("**📊 Instruments Found — click a row to select it:**")

                display_df = pd.DataFrame(
                    {
                        "📌 Symbol": [s["symbol"] for s in _search_stocks],
                        "🏢 Name": [s["name"] for s in _search_stocks],
                        "📝 Description": [s["description"] for s in _search_stocks],
                    }
                )

                # Interactive table: single-row selection triggers rerun
                event = st.dataframe(
                    display_df,
                    on_select="rerun",
                    selection_mode="single-row",
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "📌 Symbol": st.column_config.TextColumn(
                            width="small", help="Click a row to select this instrument"
                        ),
                        "🏢 Name": st.column_config.TextColumn(
                            width="medium",
                        ),
                        "📝 Description": st.column_config.TextColumn(
                            width="large",
                        ),
                    },
                )

                # Row selected → show confirm bar
                if event.selection.rows:
                    sel_idx = event.selection.rows[0]
                    sel = _search_stocks[sel_idx]
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        st.info(f"**Selected:** {sel['symbol']} — {sel['name']}")
                    with col_btn:
                        if st.button(
                            "📈 Analyze", use_container_width=True, type="primary"
                        ):
                            st.session_state["quick_selected_symbol"] = sel["symbol"]
                            st.session_state["auto_load_data"] = True
                            st.rerun()

        st.divider()

        # Section 2: Symbol from search results
        quick_selected = st.session_state.get("quick_selected_symbol", None)
        auto_load = st.session_state.get("auto_load_data", False)
        final_symbol = quick_selected

        if final_symbol:
            symbol_labels = get_symbol_labels()
            label = symbol_labels.get(final_symbol, final_symbol)
            st.success(f"✅ Selected: **{label}**")
        else:
            st.info("🔍 Use the Stock Search above to find and select an instrument.")
            st.stop()

        st.divider()

        # Section 3: Period selection
        st.subheader("Analysis Period")

        selected_period = st.select_slider(
            "Choose time period", options=list(PERIODS.keys()), value="1 Mois"
        )

        days = PERIODS[selected_period]

        st.divider()

        # Section 4: Data download and display
        # Auto-load data if quick select was used
        load_button_clicked = st.button(
            "📥 Load Data", type="primary", use_container_width=True
        )

        if load_button_clicked or auto_load:
            with st.spinner(f"Downloading data for {final_symbol}..."):
                df = get_stock_data(final_symbol, days)

                if df is not None and not df.empty:
                    # Store in session state
                    st.session_state["current_data"] = df
                    st.session_state["current_symbol"] = final_symbol
                    st.session_state["current_period"] = selected_period
                    st.success(f"✅ Data loaded: {len(df)} data points")

                    # Clear auto-load flag and quick selection
                    st.session_state["auto_load_data"] = False
                    st.session_state["quick_selected_symbol"] = None
                else:
                    st.error(
                        f"❌ No data found for **{final_symbol}**. Check the symbol and try again."
                    )
                    st.session_state["auto_load_data"] = False

        # Display data if available
        if "current_data" in st.session_state:
            df = st.session_state["current_data"]
            symbol = st.session_state["current_symbol"]
            period_name = st.session_state["current_period"]

            st.divider()

            # Statistics
            st.subheader("📊 Statistics")

            stats = calculate_statistics(df)

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric(
                    "Current Price",
                    f"${stats['current']:.2f}",
                    f"{stats['change_pct']:.2f}%",
                )

            with col2:
                st.metric("Minimum", f"${stats['min']:.2f}")

            with col3:
                st.metric("Maximum", f"${stats['max']:.2f}")

            with col4:
                st.metric("Average", f"${stats['mean']:.2f}")

            with col5:
                st.metric("Volatility", f"${stats['volatility']:.2f}")

            # Interactive chart
            st.subheader("📈 Interactive Chart")

            fig = create_candlestick_chart(df, symbol, period_name)
            st.plotly_chart(fig, use_container_width=True)

            # Date/time selection cursor
            st.subheader("🔍 Detailed Exploration")

            # Selection of a specific point
            selected_idx = st.slider(
                "Move cursor to explore values",
                min_value=0,
                max_value=len(df) - 1,
                value=len(df) - 1,
                key="data_slider",
            )

            selected_row = df.iloc[selected_idx]
            selected_date = df.index[selected_idx]

            col1, col2, col3 = st.columns(3)

            with col1:
                st.write(f"**Date:** {selected_date.strftime('%d/%m/%Y')}")

            with col2:
                st.write(f"**Open:** ${selected_row['Open']:.2f}")
                st.write(f"**Close:** ${selected_row['Close']:.2f}")

            with col3:
                st.write(f"**High:** ${selected_row['High']:.2f}")
                st.write(f"**Low:** ${selected_row['Low']:.2f}")
                st.write(f"**Volume:** {selected_row['Volume']:,.0f}")

            st.divider()

            # LLM Analysis
            if dspy_ready:
                st.subheader("🤖 AI Analysis")

                if st.button("Generate AI Analysis", use_container_width=True):
                    with st.spinner("AI is analyzing data..."):
                        analysis, insights = llm_stock_analysis(symbol, df, period_name)

                        if analysis:
                            st.write("**Detailed Analysis:**")
                            st.info(analysis)

                            if insights:
                                st.write("**Key Points:**")
                                for insight in insights:
                                    st.write(f"- {insight}")

            # Raw data table (optional)
            with st.expander("📋 View Raw Data"):
                st.dataframe(df, use_container_width=True)

    # ==================== TAB: PORTFOLIO ====================
    elif tab_selection == "📊 Portfolio":
        st.header("📊 My Portfolio")

        # Initialize managers
        ib_client = get_ib_client()
        portfolio_manager = PortfolioManager(use_ibkr=True)
        risk_manager = RiskProfileManager()

        # IBKR connection indicator
        if ib_client and ib_client.isConnected():
            st.success("✅ Connected to IBKR - Socket connection active", icon="📡")

            # Add diagnostic info
            with st.expander("🔍 IBKR Connection Diagnostics", expanded=False):
                st.write("**Connection Status:**")
                st.write(f"- Socket connected: ✅ Yes")
                st.write(f"- Host: {ib_client.host}")
                st.write(f"- Port: {ib_client.port}")
                st.write(f"- Client ID: {ib_client.clientId}")

                # Show managed accounts
                try:
                    managed_accounts = ib_client.get_managed_accounts()
                    if managed_accounts:
                        st.write(f"- Managed accounts: {', '.join(managed_accounts)}")
                    else:
                        st.write(
                            f"- Managed accounts: ⚠️ Not yet received (may take a moment)"
                        )
                except AttributeError:
                    st.write(
                        f"- Managed accounts: ⚠️ Restart dashboard to see account IDs"
                    )

                st.write("")
                st.write("**Attempting to retrieve account data...**")

                # Test account summary
                try:
                    test_account = ib_client.get_account_summary(timeout=5.0)
                    if test_account:
                        st.write(
                            f"- Account summary: ✅ Retrieved {len(test_account)} fields"
                        )
                        for key, value in test_account.items():
                            st.write(f"  - {key}: {value}")
                    else:
                        st.write("- Account summary: ❌ Empty response")
                except Exception as e:
                    st.write(f"- Account summary: ❌ Error: {e}")

                # Test positions
                try:
                    test_positions = ib_client.get_account_positions(timeout=5.0)
                    if test_positions:
                        st.write(
                            f"- Positions: ✅ Retrieved {len(test_positions)} positions"
                        )
                    else:
                        st.write(
                            "- Positions: ⚠️ No positions found (account may be empty)"
                        )
                except Exception as e:
                    st.write(f"- Positions: ❌ Error: {e}")
        else:
            st.info(
                "📡 Connect to IBKR (TWS or IB Gateway) to view your portfolio.",
                icon="📡",
            )
            st.stop()

        # Fetch account data from IBKR
        available_cash = None
        buying_power = None
        try:
            account = ib_client.get_account_summary(timeout=10.0)
            if account:
                if account.get("TotalCashValue") is not None:
                    available_cash = float(account["TotalCashValue"])
                if account.get("BuyingPower") is not None:
                    buying_power = float(account["BuyingPower"])
        except Exception as e:
            st.warning(f"⚠️ IBKR account data error: {e}")

        # Portfolio summary
        summary = portfolio_manager.get_portfolio_summary(
            available_cash=available_cash or 0
        )

        # Display main metrics
        st.subheader("📈 Global Summary")

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric(
                "🏦 Available Capital",
                f"${available_cash:,.2f}" if available_cash is not None else "N/A",
                help="TotalCashValue (IBKR)",
            )

        with col2:
            st.metric(
                "💰 Invested Capital",
                f"${summary['total_invested']:,.2f}",
                help="Amount invested in positions",
            )

        with col3:
            st.metric(
                "📊 Position Value",
                f"${summary['total_value']:,.2f}",
                help="Current value of all positions",
            )

        with col4:
            st.metric(
                "💎 Buying Power",
                f"${buying_power:,.2f}" if buying_power is not None else "N/A",
                help="BuyingPower from IBKR account",
            )

        with col5:
            pnl_color = "normal" if summary["total_pnl"] >= 0 else "inverse"
            st.metric(
                "💵 Net Gain",
                f"${summary['total_pnl']:,.2f}",
                f"{summary['total_gain_pct']:.2f}%",
                delta_color=pnl_color,
                help="Gain/loss after fees",
            )

        with col6:
            st.metric(
                "📦 Positions",
                f"{summary['num_positions']}",
                help="Nombre de positions ouvertes",
            )

        st.divider()

        # Capital Allocation (IBKR only — no manual entry)
        st.subheader("📊 Capital Allocation")

        if available_cash is not None and summary["total_capitalization"] > 0:
            col1, col2 = st.columns([2, 1])

            with col1:
                invested_pct = (
                    summary["total_invested"] / summary["total_capitalization"]
                ) * 100
                cash_pct = (available_cash / summary["total_capitalization"]) * 100

                st.write(f"💰 **Invested:** {invested_pct:.1f}%")
                st.progress(min(invested_pct / 100, 1.0))

                st.write(f"🏦 **Cash:** {cash_pct:.1f}%")
                st.progress(min(cash_pct / 100, 1.0))

            with col2:
                current_profile = risk_manager.get_risk_profile()
                if current_profile == "Conservative" and invested_pct > 40:
                    st.warning("⚠️ High investment rate for Conservative profile")
                elif current_profile == "Very Aggressive" and cash_pct > 20:
                    st.info("💡 Very Aggressive profile: You could invest more cash")
        else:
            st.info(
                "No open positions — allocation will appear once positions are held.",
                icon="ℹ️",
            )

        st.divider()

        # Tableau des positions
        if summary["num_positions"] > 0:
            st.subheader("📋 Position Details")

            # Get DataFrame with all stats
            df_portfolio = portfolio_manager.calculate_portfolio_stats()

            # Display table with formatting
            st.dataframe(
                df_portfolio,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Symbole": st.column_config.TextColumn(
                        width="small", help="Stock symbol"
                    ),
                    "Actions": st.column_config.NumberColumn(
                        format="%d", help="Number of shares held"
                    ),
                    "Prix Achat": st.column_config.NumberColumn(
                        format="$%.2f", help="Average purchase price"
                    ),
                    "Prix Actuel": st.column_config.NumberColumn(
                        format="$%.2f", help="Current market price"
                    ),
                    "Valeur Investie": st.column_config.NumberColumn(
                        format="$%.2f",
                        help="Invested capital (shares × purchase price)",
                    ),
                    "Valeur Actuelle": st.column_config.NumberColumn(
                        format="$%.2f", help="Current position value"
                    ),
                    "Frais Achat": st.column_config.NumberColumn(
                        format="$%.2f", help="Fees paid at purchase"
                    ),
                    "Frais Vente (est.)": st.column_config.NumberColumn(
                        format="$%.2f", help="Estimated fees for sale"
                    ),
                    "Frais Totaux": st.column_config.NumberColumn(
                        format="$%.2f", help="Total fees (purchase + estimated sale)"
                    ),
                    "Plus-Value ($)": st.column_config.NumberColumn(
                        format="$%.2f", help="Net gain after fees"
                    ),
                    "Gain IBKR (%)": st.column_config.NumberColumn(
                        format="%.2f%%",
                        help="Gain percentage shown in IBKR (without fees)",
                    ),
                    "Gain Réel (%)": st.column_config.NumberColumn(
                        format="%.2f%%", help="Real gain percentage after fees"
                    ),
                    "Plan IBKR": st.column_config.TextColumn(
                        width="small",
                        help="IBKR plan used (Lite, Pro Fixed, Pro Tiered)",
                    ),
                    "Date Achat": st.column_config.DateColumn(
                        format="DD/MM/YYYY", help="Position purchase date"
                    ),
                },
            )

            # Explanatory legend
            with st.expander("ℹ️ Understanding gain differences"):
                st.markdown(
                    """
                **📊 IBKR Gain (%)** vs **💰 Real Gain (%)**

                - **IBKR Gain (%)**: Percentage shown in your IBKR interface
                  - Formula: `(Current Price - Purchase Price) / Purchase Price × 100`
                  - ⚠️ Does NOT account for transaction fees

                - **Real Gain (%)**: Your actual gain after all fees
                  - Formula: `(Net Gain) / Invested Capital × 100`
                  - ✅ Includes purchase AND sale fees (estimated)
                  - This is your **true return**

                **Example:**
                - Purchase: 100 shares at $50 = $5000 (+ $5 fees)
                - Current price: $55
                - IBKR Gain: +10% (shown in IBKR)
                - Real Gain: +9.80% (after purchase and sale fees)

                **💡 Tip:** Always monitor **Real Gain** for your investment strategy.
                """
                )

        else:
            st.info("📭 No open positions in your IBKR account.", icon="📡")

    # ==================== TAB: ACTUALITES ====================
    elif tab_selection == "📰 Actualités":
        st.header("📰 Market News")

        if st.button("🔄 Refresh", type="primary"):
            st.session_state.pop("rss_news", None)
            st.session_state.pop("article_cache", None)
            st.rerun()

        if "rss_news" not in st.session_state:
            with st.spinner("Fetching RSS feeds…"):
                items, errors = fetch_rss_news([], [])
                st.session_state["rss_news"] = items
                st.session_state["rss_errors"] = errors

        items = st.session_state.get("rss_news", [])
        visible = items

        st.caption(f"{len(visible)} article(s)")

        if not visible:
            st.info("No articles found. Try broader keywords or click Refresh.")
        else:
            cache = st.session_state.setdefault("article_cache", {})

            # Pre-fetch all uncached articles before rendering
            uncached = [it for it in visible if it.uid not in cache]
            if uncached:
                with st.spinner(f"Loading {len(uncached)} article(s)…"):
                    for it in uncached:
                        if it.full_content:
                            cache[it.uid] = it.full_content
                        else:
                            cache[it.uid] = _fetch_article_text(it.link)

            # Only show articles with content
            readable = [it for it in visible if cache.get(it.uid)]
            st.caption(f"{len(readable)} readable article(s) out of {len(visible)}")

            for it in readable:
                pub = (
                    it.published_at.strftime("%d %b %Y %H:%M UTC")
                    if it.published_at
                    else "—"
                )
                with st.expander(it.title, expanded=False):
                    st.caption(f"**{it.source}** · {pub}")
                    st.markdown(f"[🔗 Open on source site]({it.link})")
                    st.divider()
                    st.markdown(cache[it.uid])

    # ==================== TAB: CONFIGURATION ====================
    elif tab_selection == "⚙️ Configuration":
        st.header("⚙️ Risk Profile Configuration")

        # Initialize profile manager
        risk_manager = RiskProfileManager()

        # Get current profile
        current_profile = risk_manager.get_risk_profile()
        current_details = risk_manager.get_profile_details()

        # Display current profile
        st.subheader("📊 Current Profile")

        # Couleur du profil
        profile_color = current_details.get("color", "#4CAF50")

        st.markdown(
            f"""
        <div style="
            background-color: {profile_color}22;
            border-left: 4px solid {profile_color};
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        ">
            <h2 style="color: {profile_color}; margin: 0;">{current_profile}</h2>
            <p style="margin: 10px 0 0 0; font-size: 1.1em;">{current_details['description']}</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Profile metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("🎯 Risk Tolerance", current_details["risk_tolerance"])

        with col2:
            st.metric("⏳ Time Horizon", current_details["time_horizon"])

        with col3:
            st.metric(
                "📊 Volatility Acceptance", current_details["volatility_acceptance"]
            )

        with col4:
            st.metric("📉 Loss Tolerance", current_details["loss_tolerance"])

        st.divider()

        # Profile details
        st.subheader("📋 Profile Details")

        tab1, tab2, tab3, tab4 = st.tabs(
            [
                "💼 Recommended Allocation",
                "✅ Recommended Instruments",
                "❌ Instruments to Avoid",
                "⚙️ Settings",
            ]
        )

        with tab1:
            st.write("**Recommended asset allocation:**")
            allocation = current_details["recommended_allocation"]

            # Create bar chart for allocation
            allocation_df = pd.DataFrame(
                {
                    "Asset Class": list(allocation.keys()),
                    "Allocation": list(allocation.values()),
                }
            )

            for asset_class, alloc in allocation.items():
                st.progress(0.5, text=f"{asset_class}: {alloc}")

        with tab2:
            st.write("**Recommended financial instruments for this profile:**")
            for instrument in current_details["recommended_instruments"]:
                st.write(f"✅ {instrument}")

        with tab3:
            st.write("**Instruments to avoid with this profile:**")
            for avoid in current_details["avoid"]:
                st.write(f"❌ {avoid}")

            # Special warnings for very aggressive profile
            if "warnings" in current_details:
                st.warning("**⚠️ Important warnings:**")
                for warning in current_details["warnings"]:
                    st.write(warning)

        with tab4:
            st.write("**Management settings:**")
            st.write(
                f"📦 **Max position size:** {current_details['max_position_size']}"
            )
            st.write(
                f"🔄 **Rebalancing frequency:** {current_details['rebalancing_frequency']}"
            )

            # Calculated risk metrics
            metrics = risk_manager.get_risk_metrics()
            st.write(f"📉 **Max loss per trade:** {metrics['max_loss_per_trade']}%")
            st.write(f"📊 **Max portfolio risk:** {metrics['max_portfolio_risk']}%")

            st.caption(
                "✏️ These settings are modifiable below and apply to run_trader via config.yaml."
            )

        st.divider()

        # Change profile
        st.subheader("🔄 Change Profile")

        st.write("**Compare available profiles:**")

        # Create comparison table
        comparison_data = []
        for profile_name, profile_data in RISK_PROFILES.items():
            comparison_data.append(
                {
                    "Profile": profile_name,
                    "Tolerance": profile_data["risk_tolerance"],
                    "Horizon": profile_data["time_horizon"],
                    "Max Position": profile_data["max_position_size"],
                    "Rebalancing": profile_data["rebalancing_frequency"],
                }
            )

        comparison_df = pd.DataFrame(comparison_data)

        st.dataframe(
            comparison_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Profile": st.column_config.TextColumn(width="medium"),
                "Tolerance": st.column_config.TextColumn(width="small"),
                "Horizon": st.column_config.TextColumn(width="medium"),
                "Max Position": st.column_config.TextColumn(width="small"),
                "Rebalancing": st.column_config.TextColumn(width="medium"),
            },
        )

        st.write("")
        st.write("**Select a new profile:**")

        # Profile change form
        with st.form("change_profile_form"):
            new_profile = st.selectbox(
                "Choose a profile",
                list(RISK_PROFILES.keys()),
                index=list(RISK_PROFILES.keys()).index(current_profile),
            )

            # Display preview of new profile
            if new_profile != current_profile:
                new_details = RISK_PROFILES[new_profile]
                st.info(f"**{new_profile}:** {new_details['description']}")

            col1, col2 = st.columns(2)

            with col1:
                max_loss_per_trade = st.number_input(
                    "Max loss per trade (%)",
                    min_value=0.1,
                    max_value=50.0,
                    value=float(risk_manager.config.get("max_loss_per_trade", 2.0)),
                    step=0.1,
                    help="Maximum acceptable loss percentage on a single trade",
                )

            with col2:
                max_portfolio_risk = st.number_input(
                    "Max portfolio risk (%)",
                    min_value=1.0,
                    max_value=100.0,
                    value=float(risk_manager.config.get("max_portfolio_risk", 10.0)),
                    step=1.0,
                    help="Maximum overall portfolio risk percentage",
                )

            submit_button = st.form_submit_button(
                "💾 Save Changes", use_container_width=True
            )

            if submit_button:
                # Save profile to user_config.json (UI preference)
                risk_manager.set_risk_profile(new_profile)
                risk_manager.update_config(
                    max_loss_per_trade=max_loss_per_trade,
                    max_portfolio_risk=max_portfolio_risk,
                )
                # Write max_loss_per_trade and max_portfolio_exposure to config.yaml (run_trader)
                result = save_risk_config_to_yaml(
                    max_loss_per_trade, max_portfolio_risk
                )
                if result is True:
                    st.success(
                        f"✅ Profile **{new_profile}** saved — "
                        f"risk parameters updated in config.yaml (run_trader)"
                    )
                else:
                    st.warning(f"⚠️ Profile changed, but config.yaml error: {result}")
                st.rerun()

    # ==================== TAB: MODELING ====================
    elif tab_selection == "🤖 Modeling":
        render_modeling_tab(ib)

    # ==================== TAB: DOCUMENTATION (Placeholder) ====================
    elif tab_selection == "📚 Documentation":
        st.header("📚 Documentation")
        st.info("🚧 Section under development - Interactive documentation coming soon")

    # Footer
    st.sidebar.divider()
    st.sidebar.caption("Quantum Trader v1.0")
    st.sidebar.caption("Powered by DSPy + Streamlit")


if __name__ == "__main__":
    main()
