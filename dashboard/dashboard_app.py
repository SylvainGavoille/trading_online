"""
Dashboard Streamlit Interactif - Quantum Trader
Exploration et analyse d'actions avec intégration LLM DSPy
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta
import dspy
from typing import List, Dict, Optional
import yaml
import sys
import os

# Add parent directory to path for local imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data.download_history import fetch_batch, parquet_path, save_parquet
from src.data.dynamic_stocks import get_symbol_name_map
from src.api.ib_connector import IBClient
from src.agents.stock_search_agent import (
    simple_stock_search, StockSearchAgent, parse_stock_suggestions,
)

# Import portfolio and risk profile managers
from portfolio_manager import PortfolioManager, configure_ibkr_client as configure_pm_client
from risk_profile_manager import RiskProfileManager, RISK_PROFILES

# Page configuration
st.set_page_config(
    page_title="Quantum Trader - Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load configuration
@st.cache_resource
def load_config():
    """Charge la configuration du système"""
    try:
        # Chemin relatif depuis dashboard/
        config_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'config', 'config.yaml')
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        return {}


def save_risk_config_to_yaml(max_loss_per_trade_pct: float, max_portfolio_risk_pct: float):
    """
    Met à jour les paramètres de risque dans config.yaml (fichier utilisé par run_trader).
    Préserve les commentaires et l'ordre des clés existantes.

    Returns:
        True si succès, str d'erreur sinon.
    """
    import re
    config_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'config', 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        def replace_scalar(key: str, new_val: float, text: str) -> str:
            """Remplace la valeur d'une clé YAML scalaire en préservant les commentaires."""
            pattern = rf'^(\s*{re.escape(key)}:\s*)[\d.]+(.*)$'
            return re.sub(pattern, rf'\g<1>{new_val}\2', text, flags=re.MULTILINE)

        content = replace_scalar('max_loss_per_trade', round(max_loss_per_trade_pct / 100, 6), content)
        content = replace_scalar('max_portfolio_exposure', round(max_portfolio_risk_pct / 100, 6), content)

        with open(config_path, 'w', encoding='utf-8') as f:
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
        llm_config = config.get('multi_agent', {})

        # Lire la configuration du provider
        provider = llm_config.get('llm_provider', 'ollama')
        model = llm_config.get('model_name', 'deepseek-r1:14b')

        # Configuration selon le provider
        if provider == 'openai':
            # OpenAI (nécessite OPENAI_API_KEY)
            lm = dspy.LM(
                model=f'openai/{model}',
                api_key=os.getenv('OPENAI_API_KEY')
            )
        elif provider == 'anthropic':
            # Anthropic (nécessite ANTHROPIC_API_KEY)
            lm = dspy.LM(
                model=f'anthropic/{model}',
                api_key=os.getenv('ANTHROPIC_API_KEY')
            )
        else:
            # Ollama par défaut (local, gratuit)
            lm = dspy.LM(
                model=f'ollama/{model}',
                api_base='http://localhost:11434',
                api_key='ollama'
            )

        dspy.configure(lm=lm)
        return True
    except Exception as e:
        # Si échec, le dashboard fonctionnera sans IA
        return False

# Signature DSPy pour suggérer des actions
class StockSuggestion(dspy.Signature):
    """Suggère des actions à analyser basées sur une requête utilisateur"""
    user_query: str = dspy.InputField(desc="Requête de l'utilisateur (ex: 'tech stocks', 'energy sector')")
    suggestions: List[str] = dspy.OutputField(desc="Liste de 5-10 symboles d'actions suggérées")
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
    "5 Jours":  5,
    "1 Mois":   30,
    "3 Mois":   90,
    "6 Mois":   180,
    "1 An":     365,
}

PARQUET_ROOT = os.path.join(os.path.dirname(__file__), '..', 'price_historical')

# Liste de stocks populaires par catégorie
POPULAR_STOCKS = {
    "Tech": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "TSLA", "AMZN", "NFLX"],
    "Finance": ["JPM", "BAC", "WFC", "GS", "MS", "C", "USB"],
    "Energie": ["XOM", "CVX", "COP", "SLB", "OXY", "EOG"],
    "Santé": ["JNJ", "UNH", "PFE", "ABBV", "TMO", "LLY"],
    "Consommation": ["WMT", "PG", "KO", "PEP", "MCD", "NKE"],
    "Industrie": ["BA", "CAT", "GE", "MMM", "HON", "UPS"]
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


def load_from_parquet(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    """Charge tous les fichiers Parquet du symbole dans la plage de dates."""
    frames = []
    day = start_date
    while day <= end_date:
        path = parquet_path(PARQUET_ROOT, day, symbol)
        if os.path.exists(path):
            frames.append(pd.read_parquet(path))
        day += timedelta(days=1)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').set_index('date')
    df.index.name = 'Date'
    df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
    return df[['Open', 'High', 'Low', 'Close', 'Volume']]


def ensure_parquet_up_to_date(symbol: str, start_date: date, end_date: date) -> int:
    """Télécharge les jours ouvrés manquants et les sauvegarde en Parquet."""
    missing = []
    day = start_date
    while day <= end_date:
        if day.weekday() < 5:  # jours ouvrés seulement
            path = parquet_path(PARQUET_ROOT, day, symbol)
            if not os.path.exists(path):
                missing.append(day)
        day += timedelta(days=1)

    if not missing:
        return 0

    results = fetch_batch([symbol], start_date, end_date)
    df = results.get(symbol)
    if df is None or df.empty:
        return 0

    saved = 0
    for day_val, group in df.groupby('date'):
        path = parquet_path(PARQUET_ROOT, day_val, symbol)
        save_parquet(group.reset_index(drop=True), path)
        saved += 1
    return saved


@st.cache_data(ttl=300)
def get_stock_data(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Charge les données depuis Parquet, en téléchargeant les jours manquants si nécessaire."""
    end_date   = get_last_trading_date()
    start_date = end_date - timedelta(days=days)

    # Mise à jour silencieuse si des jours manquent
    ensure_parquet_up_to_date(symbol, start_date, end_date)

    df = load_from_parquet(symbol, start_date, end_date)
    if df is not None and not df.empty:
        return df
    return None


@st.cache_data(ttl=3600)
def get_parquet_symbols() -> set:
    """Retourne l'ensemble des symboles disponibles dans le store Parquet (lecture du dernier jour disponible)."""
    for offset in range(7):
        day = get_last_trading_date() - timedelta(days=offset)
        day_dir = os.path.join(
            PARQUET_ROOT,
            f"year={day.year}",
            f"month={day.month:02}",
            f"day={day.isoformat()}",
        )
        if os.path.isdir(day_dir):
            symbols = {f[:-8] for f in os.listdir(day_dir) if f.endswith('.parquet')}
            if symbols:
                return symbols
    return set()


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
        if industry and industry not in ('Unknown', 'N/A', ''):
            label += f" ({industry})"
        elif sec_type and sec_type not in ('', 'Unknown'):
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

    close_prices = df['Close']

    stats = {
        'min': close_prices.min(),
        'max': close_prices.max(),
        'mean': close_prices.mean(),
        'current': close_prices.iloc[-1],
        'start': close_prices.iloc[0],
        'change': close_prices.iloc[-1] - close_prices.iloc[0],
        'change_pct': ((close_prices.iloc[-1] - close_prices.iloc[0]) / close_prices.iloc[0] * 100),
        'volatility': close_prices.std(),
        'volume_avg': df['Volume'].mean(),
        'volume_total': df['Volume'].sum()
    }

    return stats

def create_candlestick_chart(df: pd.DataFrame, symbol: str, period_name: str) -> go.Figure:
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
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f'{symbol} - Prix ({period_name})', 'Volume')
    )

    # Chandelier pour les prix
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='Prix',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350'
        ),
        row=1, col=1
    )

    # Barre de volume
    colors = ['#26a69a' if close > open else '#ef5350'
              for close, open in zip(df['Close'], df['Open'])]

    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['Volume'],
            name='Volume',
            marker_color=colors,
            showlegend=False
        ),
        row=2, col=1
    )

    # Mise en forme
    fig.update_layout(
        height=700,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        template='plotly_dark',
        margin=dict(l=50, r=50, t=50, b=50)
    )

    fig.update_xaxes(tickformat='%d/%m/%Y', title='Date', row=2, col=1)
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

def llm_stock_analysis(symbol: str, df: pd.DataFrame, period: str) -> tuple[str, List[str]]:
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

        result = analyze_stock(
            symbol=symbol,
            price_data=price_summary,
            period=period
        )
        return result.analysis, result.key_insights
    except Exception as e:
        st.error(f"Erreur analyse LLM: {e}")
        return "", []

# ==================== INTERFACE STREAMLIT ====================

def main():
    """Application principale"""

    # Titre principal
    st.title("📈 Quantum Trader - Dashboard Interactif")

    # Initialiser IBKR dès le démarrage (connexion partagée)
    ib = get_ib_client()

    # Sidebar - Menu de navigation
    st.sidebar.title("Navigation")

    MENU_ITEMS = [
        "🔍 Exploration",
        "📊 Portfolio",
        "📰 Actualités",
        "⚙️ Configuration",
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
    ib = get_ib_client()   # already cached — no new connection attempt
    if ib is not None and ib.isConnected():
        st.sidebar.success("🟢 IBKR connecté")
        n_rec = getattr(ib, 'reconnect_attempts', 0)
        last_rec = getattr(ib, 'last_reconnect_at', None)
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
                    key="llm_query"
                )

            with col_btn:
                st.write("")  # Spacer
                st.write("")  # Spacer
                search_button = st.button("🔍 Search", use_container_width=True)

            use_ai_search = st.checkbox(
                "🤖 AI-assisted search (much slower — requires Ollama)",
                value=False,
                help="Uses the local LLM (deepseek-r1:14b) to interpret and rank results. "
                     "Can take 1-5 minutes. Leave unchecked for fast Yahoo Finance search."
            )

            if search_button:
                if user_query:
                    spinner_msg = "🔎 AI search in progress (this may take several minutes)..." \
                        if use_ai_search else "🔎 Searching via Yahoo Finance..."
                    with st.spinner(spinner_msg):
                        stocks, explanation = llm_stock_suggestions(
                            user_query, use_llm=(use_ai_search and dspy_ready)
                        )
                        if use_ai_search and not dspy_ready:
                            st.warning("⚠️ Ollama not available — fell back to Yahoo Finance search.")

                    # Persist results in session state so selections survive reruns
                    if stocks:
                        st.session_state['search_stocks'] = stocks
                        st.session_state['search_explanation'] = explanation
                    else:
                        st.session_state['search_stocks'] = []
                        st.session_state['search_explanation'] = ''
                        st.warning(f"No instruments found for '{user_query}' in the local Parquet database.")
                        st.info("💡 Try keywords like: tech, finance, ETF, bitcoin, energy, dividends...")
                else:
                    st.warning("⚠️ Please enter a search query")

            # Display results from session state (persist across reruns / row selection)
            _search_stocks = st.session_state.get('search_stocks', [])
            _search_expl   = st.session_state.get('search_explanation', '')

            if _search_stocks:
                st.success(f"✅ {len(_search_stocks)} result(s) found")

                with st.expander("💡 Search Analysis", expanded=False):
                    st.info(_search_expl)

                st.write("**📊 Instruments Found — click a row to select it:**")

                display_df = pd.DataFrame({
                    '📌 Symbol':      [s['symbol']      for s in _search_stocks],
                    '🏢 Name':        [s['name']        for s in _search_stocks],
                    '📝 Description': [s['description'] for s in _search_stocks],
                })

                # Interactive table: single-row selection triggers rerun
                event = st.dataframe(
                    display_df,
                    on_select="rerun",
                    selection_mode="single-row",
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        '📌 Symbol': st.column_config.TextColumn(
                            width="small",
                            help="Click a row to select this instrument"
                        ),
                        '🏢 Name': st.column_config.TextColumn(
                            width="medium",
                        ),
                        '📝 Description': st.column_config.TextColumn(
                            width="large",
                        )
                    }
                )

                # Row selected → show confirm bar
                if event.selection.rows:
                    sel_idx  = event.selection.rows[0]
                    sel      = _search_stocks[sel_idx]
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        st.info(f"**Selected:** {sel['symbol']} — {sel['name']}")
                    with col_btn:
                        if st.button("📈 Analyze", use_container_width=True, type="primary"):
                            st.session_state['quick_selected_symbol'] = sel['symbol']
                            st.session_state['auto_load_data'] = True
                            st.rerun()

        st.divider()

        # Section 2: Symbol selection from available Parquet symbols
        st.subheader("Stock Selection")

        # Check if quick select was used
        quick_selected = st.session_state.get('quick_selected_symbol', None)
        auto_load = st.session_state.get('auto_load_data', False)

        if quick_selected:
            st.success(f"✅ Quick selected: **{quick_selected}**")
            st.caption("Data will load automatically below")

        # Full sorted list of symbols available in the Parquet store
        all_parquet_symbols = sorted(get_parquet_symbols())
        symbol_labels = get_symbol_labels()

        default_symbol = quick_selected if quick_selected else "AAPL"
        default_index = all_parquet_symbols.index(default_symbol) if default_symbol in all_parquet_symbols else 0

        selected_symbol = st.selectbox(
            f"Choose a symbol ({len(all_parquet_symbols)} available — type to filter)",
            options=all_parquet_symbols,
            index=default_index,
            format_func=lambda s: symbol_labels.get(s, s),
            key="symbol_selectbox",
        )

        # Determine final symbol (priority: quick select > dropdown)
        final_symbol = quick_selected if quick_selected else selected_symbol

        st.divider()

        # Section 3: Period selection
        st.subheader("Analysis Period")

        selected_period = st.select_slider(
            "Choose time period",
            options=list(PERIODS.keys()),
            value="1 Mois"
        )

        days = PERIODS[selected_period]

        st.divider()

        # Section 4: Data download and display
        # Auto-load data if quick select was used
        load_button_clicked = st.button("📥 Load Data", type="primary", use_container_width=True)

        if load_button_clicked or auto_load:
            with st.spinner(f"Downloading data for {final_symbol}..."):
                df = get_stock_data(final_symbol, days)

                if df is not None and not df.empty:
                    # Store in session state
                    st.session_state['current_data'] = df
                    st.session_state['current_symbol'] = final_symbol
                    st.session_state['current_period'] = selected_period
                    st.success(f"✅ Data loaded: {len(df)} data points")

                    # Clear auto-load flag and quick selection
                    st.session_state['auto_load_data'] = False
                    st.session_state['quick_selected_symbol'] = None
                else:
                    st.error(f"❌ No data found for **{final_symbol}**. Check the symbol and try again.")
                    st.session_state['auto_load_data'] = False

        # Display data if available
        if 'current_data' in st.session_state:
            df = st.session_state['current_data']
            symbol = st.session_state['current_symbol']
            period_name = st.session_state['current_period']

            st.divider()

            # Statistics
            st.subheader("📊 Statistics")

            stats = calculate_statistics(df)

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric(
                    "Current Price",
                    f"${stats['current']:.2f}",
                    f"{stats['change_pct']:.2f}%"
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
                max_value=len(df)-1,
                value=len(df)-1,
                key="data_slider"
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
                        st.write(f"- Managed accounts: ⚠️ Not yet received (may take a moment)")
                except AttributeError:
                    st.write(f"- Managed accounts: ⚠️ Restart dashboard to see account IDs")

                st.write("")
                st.write("**Attempting to retrieve account data...**")

                # Test account summary
                try:
                    test_account = ib_client.get_account_summary(timeout=5.0)
                    if test_account:
                        st.write(f"- Account summary: ✅ Retrieved {len(test_account)} fields")
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
                        st.write(f"- Positions: ✅ Retrieved {len(test_positions)} positions")
                    else:
                        st.write("- Positions: ⚠️ No positions found (account may be empty)")
                except Exception as e:
                    st.write(f"- Positions: ❌ Error: {e}")
        else:
            st.info("📡 Connect to IBKR (TWS or IB Gateway) to view your portfolio.", icon="📡")
            st.stop()

        # Fetch account data from IBKR
        available_cash = None
        buying_power = None
        try:
            account = ib_client.get_account_summary(timeout=10.0)
            if account:
                if account.get('TotalCashValue') is not None:
                    available_cash = float(account['TotalCashValue'])
                if account.get('BuyingPower') is not None:
                    buying_power = float(account['BuyingPower'])
        except Exception as e:
            st.warning(f"⚠️ IBKR account data error: {e}")

        # Portfolio summary
        summary = portfolio_manager.get_portfolio_summary(available_cash=available_cash or 0)

        # Display main metrics
        st.subheader("📈 Global Summary")

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric(
                "🏦 Available Capital",
                f"${available_cash:,.2f}" if available_cash is not None else "N/A",
                help="TotalCashValue (IBKR)"
            )

        with col2:
            st.metric(
                "💰 Invested Capital",
                f"${summary['total_invested']:,.2f}",
                help="Amount invested in positions"
            )

        with col3:
            st.metric(
                "📊 Position Value",
                f"${summary['total_value']:,.2f}",
                help="Current value of all positions"
            )

        with col4:
            st.metric(
                "💎 Buying Power",
                f"${buying_power:,.2f}" if buying_power is not None else "N/A",
                help="BuyingPower from IBKR account"
            )

        with col5:
            pnl_color = "normal" if summary['total_pnl'] >= 0 else "inverse"
            st.metric(
                "💵 Net Gain",
                f"${summary['total_pnl']:,.2f}",
                f"{summary['total_gain_pct']:.2f}%",
                delta_color=pnl_color,
                help="Gain/loss after fees"
            )

        with col6:
            st.metric(
                "📦 Positions",
                f"{summary['num_positions']}",
                help="Nombre de positions ouvertes"
            )

        st.divider()

        # Capital Allocation (IBKR only — no manual entry)
        st.subheader("📊 Capital Allocation")

        if available_cash is not None and summary['total_capitalization'] > 0:
            col1, col2 = st.columns([2, 1])

            with col1:
                invested_pct = (summary['total_invested'] / summary['total_capitalization']) * 100
                cash_pct = (available_cash / summary['total_capitalization']) * 100

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
            st.info("No open positions — allocation will appear once positions are held.", icon="ℹ️")

        st.divider()

        # Tableau des positions
        if summary['num_positions'] > 0:
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
                        width="small",
                        help="Stock symbol"
                    ),
                    "Actions": st.column_config.NumberColumn(
                        format="%d",
                        help="Number of shares held"
                    ),
                    "Prix Achat": st.column_config.NumberColumn(
                        format="$%.2f",
                        help="Average purchase price"
                    ),
                    "Prix Actuel": st.column_config.NumberColumn(
                        format="$%.2f",
                        help="Current market price"
                    ),
                    "Valeur Investie": st.column_config.NumberColumn(
                        format="$%.2f",
                        help="Invested capital (shares × purchase price)"
                    ),
                    "Valeur Actuelle": st.column_config.NumberColumn(
                        format="$%.2f",
                        help="Current position value"
                    ),
                    "Frais Achat": st.column_config.NumberColumn(
                        format="$%.2f",
                        help="Fees paid at purchase"
                    ),
                    "Frais Vente (est.)": st.column_config.NumberColumn(
                        format="$%.2f",
                        help="Estimated fees for sale"
                    ),
                    "Frais Totaux": st.column_config.NumberColumn(
                        format="$%.2f",
                        help="Total fees (purchase + estimated sale)"
                    ),
                    "Plus-Value ($)": st.column_config.NumberColumn(
                        format="$%.2f",
                        help="Net gain after fees"
                    ),
                    "Gain IBKR (%)": st.column_config.NumberColumn(
                        format="%.2f%%",
                        help="Gain percentage shown in IBKR (without fees)"
                    ),
                    "Gain Réel (%)": st.column_config.NumberColumn(
                        format="%.2f%%",
                        help="Real gain percentage after fees"
                    ),
                    "Plan IBKR": st.column_config.TextColumn(
                        width="small",
                        help="IBKR plan used (Lite, Pro Fixed, Pro Tiered)"
                    ),
                    "Date Achat": st.column_config.DateColumn(
                        format="DD/MM/YYYY",
                        help="Position purchase date"
                    )
                }
            )

            # Explanatory legend
            with st.expander("ℹ️ Understanding gain differences"):
                st.markdown("""
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
                """)

        else:
            st.info("📭 No open positions in your IBKR account.", icon="📡")

    # ==================== TAB: ACTUALITES ====================
    elif tab_selection == "📰 Actualités":
        st.header("📰 Actualités IBKR")

        ib_client = get_ib_client()

        if ib_client is None or not ib_client.isConnected():
            st.error("❌ IBKR non connecté — démarrez TWS ou IB Gateway pour accéder aux actualités.")
            st.info("Port 7497 (TWS paper) ou 7496 (TWS live) — puis redémarrez le dashboard.")
        else:
            st.success("✅ Connecté à IBKR", icon="📡")

            # --- Filter bar ---
            col_filter, col_type, col_btn = st.columns([3, 1, 1])

            with col_filter:
                news_filter = st.text_input(
                    "Filtrer les actualités",
                    placeholder="Mot-clé (ex : Fed, earnings, inflation…)",
                    key="news_filter",
                )

            with col_type:
                bulletin_type = st.selectbox(
                    "Type",
                    options=["Tous", "Actualités (1)", "Bulletins bourse (2)"],
                    key="news_type_filter",
                )

            with col_btn:
                st.write("")
                st.write("")
                load_news = st.button("🔄 Charger / Actualiser", use_container_width=True, type="primary")

            # --- Load bulletins ---
            if load_news:
                with st.spinner("Collecte des actualités IBKR (4 sec.)…"):
                    bulletins = ib_client.get_news_bulletins(collect_secs=4.0)

                st.session_state['news_bulletins'] = bulletins

            # --- Display ---
            bulletins = st.session_state.get('news_bulletins', [])

            if not bulletins and not load_news:
                st.info(
                    "Cliquez sur **🔄 Charger / Actualiser** pour récupérer les actualités "
                    "diffusées par IBKR (bulletins de marché, avis des bourses, communiqués).",
                    icon="ℹ️",
                )
            elif not bulletins:
                st.warning(
                    "Aucun bulletin reçu d'IBKR.\n\n"
                    "Cela signifie généralement que votre compte n'a pas d'abonnement "
                    "aux flux de news IBKR, ou qu'aucune actualité n'a été diffusée récemment.\n\n"
                    "💡 Activez un abonnement News dans *IBKR Account Management → Market Data*.",
                    icon="⚠️",
                )
            else:
                # Apply type filter
                type_map = {"Tous": None, "Actualités (1)": 1, "Bulletins bourse (2)": 2}
                type_filter = type_map[bulletin_type]
                visible = [b for b in bulletins if type_filter is None or b['type'] == type_filter]

                # Apply keyword filter
                kw = news_filter.strip().lower()
                if kw:
                    visible = [b for b in visible if kw in b['message'].lower() or kw in b['exchange'].lower()]

                st.subheader(f"📋 {len(visible)} actualité(s){' filtrée(s)' if kw or type_filter else ''}")

                if not visible:
                    st.info("Aucune actualité ne correspond aux filtres sélectionnés.")
                else:
                    for b in visible:
                        exch_tag = f" — {b['exchange']}" if b['exchange'] else ""
                        type_tag = "📰 Actualité" if b['type'] == 1 else "🏛️ Bulletin bourse"
                        label    = f"{type_tag}{exch_tag}  •  {b['received_at']}"

                        # Show first 120 chars of message as expander header
                        preview = b['message'][:120].replace("\n", " ")
                        if len(b['message']) > 120:
                            preview += "…"

                        with st.expander(preview, expanded=False):
                            st.caption(label)
                            st.markdown(b['message'])

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

        st.markdown(f"""
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
        """, unsafe_allow_html=True)

        # Profile metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("🎯 Risk Tolerance", current_details['risk_tolerance'])

        with col2:
            st.metric("⏳ Time Horizon", current_details['time_horizon'])

        with col3:
            st.metric("📊 Volatility Acceptance", current_details['volatility_acceptance'])

        with col4:
            st.metric("📉 Loss Tolerance", current_details['loss_tolerance'])

        st.divider()

        # Profile details
        st.subheader("📋 Profile Details")

        tab1, tab2, tab3, tab4 = st.tabs([
            "💼 Recommended Allocation",
            "✅ Recommended Instruments",
            "❌ Instruments to Avoid",
            "⚙️ Settings"
        ])

        with tab1:
            st.write("**Recommended asset allocation:**")
            allocation = current_details['recommended_allocation']

            # Create bar chart for allocation
            allocation_df = pd.DataFrame({
                'Asset Class': list(allocation.keys()),
                'Allocation': list(allocation.values())
            })

            for asset_class, alloc in allocation.items():
                st.progress(0.5, text=f"{asset_class}: {alloc}")

        with tab2:
            st.write("**Recommended financial instruments for this profile:**")
            for instrument in current_details['recommended_instruments']:
                st.write(f"✅ {instrument}")

        with tab3:
            st.write("**Instruments to avoid with this profile:**")
            for avoid in current_details['avoid']:
                st.write(f"❌ {avoid}")

            # Special warnings for very aggressive profile
            if 'warnings' in current_details:
                st.warning("**⚠️ Important warnings:**")
                for warning in current_details['warnings']:
                    st.write(warning)

        with tab4:
            st.write("**Management settings:**")
            st.write(f"📦 **Max position size:** {current_details['max_position_size']}")
            st.write(f"🔄 **Rebalancing frequency:** {current_details['rebalancing_frequency']}")

            # Calculated risk metrics
            metrics = risk_manager.get_risk_metrics()
            st.write(f"📉 **Max loss per trade:** {metrics['max_loss_per_trade']}%")
            st.write(f"📊 **Max portfolio risk:** {metrics['max_portfolio_risk']}%")

            st.caption("✏️ These settings are modifiable below and apply to run_trader via config.yaml.")

        st.divider()

        # Change profile
        st.subheader("🔄 Change Profile")

        st.write("**Compare available profiles:**")

        # Create comparison table
        comparison_data = []
        for profile_name, profile_data in RISK_PROFILES.items():
            comparison_data.append({
                'Profile': profile_name,
                'Tolerance': profile_data['risk_tolerance'],
                'Horizon': profile_data['time_horizon'],
                'Max Position': profile_data['max_position_size'],
                'Rebalancing': profile_data['rebalancing_frequency']
            })

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
                "Rebalancing": st.column_config.TextColumn(width="medium")
            }
        )

        st.write("")
        st.write("**Select a new profile:**")

        # Profile change form
        with st.form("change_profile_form"):
            new_profile = st.selectbox(
                "Choose a profile",
                list(RISK_PROFILES.keys()),
                index=list(RISK_PROFILES.keys()).index(current_profile)
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
                    value=float(risk_manager.config.get('max_loss_per_trade', 2.0)),
                    step=0.1,
                    help="Maximum acceptable loss percentage on a single trade"
                )

            with col2:
                max_portfolio_risk = st.number_input(
                    "Max portfolio risk (%)",
                    min_value=1.0,
                    max_value=100.0,
                    value=float(risk_manager.config.get('max_portfolio_risk', 10.0)),
                    step=1.0,
                    help="Maximum overall portfolio risk percentage"
                )

            submit_button = st.form_submit_button("💾 Save Changes", use_container_width=True)

            if submit_button:
                # Save profile to user_config.json (UI preference)
                risk_manager.set_risk_profile(new_profile)
                risk_manager.update_config(
                    max_loss_per_trade=max_loss_per_trade,
                    max_portfolio_risk=max_portfolio_risk
                )
                # Write max_loss_per_trade and max_portfolio_exposure to config.yaml (run_trader)
                result = save_risk_config_to_yaml(max_loss_per_trade, max_portfolio_risk)
                if result is True:
                    st.success(
                        f"✅ Profile **{new_profile}** saved — "
                        f"risk parameters updated in config.yaml (run_trader)"
                    )
                else:
                    st.warning(f"⚠️ Profile changed, but config.yaml error: {result}")
                st.rerun()

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
