"""
Système de recherche d'instruments financiers via la base SQLite locale.

Source : ibkr_us.sqlite
  - us_symbols_raw      : symboles bruts NASDAQ Trader (~12 000)
  - ibkr_verification   : symboles vérifiés IBKR avec métadonnées complètes
"""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Optional, List
from cachetools import TTLCache
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

instrument_cache = TTLCache(maxsize=5000, ttl=6 * 60 * 60)   # 6 heures
search_cache     = TTLCache(maxsize=1000, ttl=30 * 60)        # 30 minutes


# ---------------------------------------------------------------------------
# Modèle
# ---------------------------------------------------------------------------

class Instrument(BaseModel):
    """Modèle d'un instrument financier"""
    symbol: str
    name: Optional[str] = None
    type: Optional[str] = Field(default=None, description="equity, etf, index, crypto, forex, etc.")
    sector: Optional[str] = None
    industry: Optional[str] = None
    currency: Optional[str] = None
    exchange: Optional[str] = None
    country: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    market_cap: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            'symbol':      self.symbol,
            'name':        self.name or self.symbol,
            'type':        self.type or 'Unknown',
            'sector':      self.sector or 'Unknown',
            'description': self.description or f"{self.name or self.symbol} ({self.type or '?'})",
            'industry':    self.industry,
            'currency':    self.currency,
            'exchange':    self.exchange,
            'country':     self.country,
            'website':     self.website,
            'market_cap':  self.market_cap,
        }


# ---------------------------------------------------------------------------
# Chemin de la base SQLite
# ---------------------------------------------------------------------------

def _get_db_path() -> str:
    """Retourne le chemin absolu de la base SQLite ibkr_us.sqlite."""
    env_path = os.environ.get('IBKR_SQLITE_PATH')
    if env_path and os.path.exists(env_path):
        return env_path

    # Chercher depuis le dossier de ce fichier (src/data/ → ../../)
    this_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(this_dir, '..', '..'))
    candidate = os.path.join(project_root, 'ibkr_us.sqlite')
    if os.path.exists(candidate):
        return candidate

    # Chercher depuis le répertoire courant
    cwd_candidate = os.path.join(os.getcwd(), 'ibkr_us.sqlite')
    if os.path.exists(cwd_candidate):
        return cwd_candidate

    return candidate  # Retourner le chemin par défaut même s'il n'existe pas


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _is_valid_symbol(symbol: str) -> bool:
    """
    Autorise les symboles typiques US et européens :
      "AAPL", "QQQ", "LQQ:FP", "LQQ.PA", "^GSPC", "EUR=X", "GC=F", "BTC-USD"
    """
    if not symbol:
        return False
    symbol = symbol.strip()
    if " " in symbol:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789^=.-:")
    if any(ch.upper() not in allowed for ch in symbol):
        return False
    base = (
        symbol.upper()
        .replace("-USD", "")
        .replace("=X", "")
        .replace("=F", "")
        .lstrip("^")
    )
    return 1 <= len(base) <= 20


def _build_description(row: dict) -> str:
    """Construit une description lisible depuis une ligne SQLite."""
    parts = []
    if row.get('name'):
        parts.append(row['name'])
    cat = row.get('category') or ''
    ind = row.get('industry') or ''
    if cat and ind and cat != ind:
        parts.append(f"{ind} / {cat}")
    elif cat:
        parts.append(cat)
    elif ind:
        parts.append(ind)
    exch = row.get('exchange') or ''
    cur  = row.get('currency') or ''
    if exch or cur:
        parts.append(f"({exch} {cur})".strip())
    return ' — '.join(parts) if parts else (row.get('symbol') or '')


def _score_instrument(query_lower: str, symbol: str, instrument: Instrument) -> int:
    """Score de pertinence requête ↔ instrument."""
    score = 0
    sym  = (symbol or "").lower()
    name = (instrument.name or "").lower()
    desc = (instrument.description or "").lower()

    # Matching direct
    if query_lower in sym:
        score += 12
    if query_lower in name:
        score += 10

    # Mots-clés
    for kw in query_lower.split():
        if len(kw) < 2:
            continue
        if kw in sym:
            score += 8
        if kw in name:
            score += 6
        if kw in desc:
            score += 4

    # Détection intentions
    wants_nasdaq = any(x in query_lower for x in ["nasdaq", "ndx", "qqq"])
    wants_100    = "100" in query_lower
    wants_2x     = bool(re.search(r"(\b2x\b|\bx2\b|\bdouble\b)", query_lower))
    wants_3x     = bool(re.search(r"(\b3x\b|\bx3\b|\btriple\b)", query_lower))

    has_nasdaq = any(k in name or k in desc for k in ["nasdaq", "ndx", "qqq", "nasdaq-100", "nasdaq 100"])
    has_100    = "100" in name or "100" in desc
    has_2x     = any(k in name or k in desc for k in ["2x", "x2", "daily 2x", "2x leveraged", "double leverage"])
    has_3x     = any(k in name or k in desc for k in ["3x", "x3", "daily 3x", "3x leveraged"])

    if wants_nasdaq and has_nasdaq:
        score += 20
    if wants_100 and has_100:
        score += 10
    if wants_2x and has_2x:
        score += 35
    if wants_3x and has_3x:
        score += 35

    # Exact symbol match → priorité absolue
    if sym == query_lower:
        score += 50

    return score


def _row_to_instrument(row: dict) -> Instrument:
    """Convertit une ligne SQLite en Instrument."""
    sec_type = (row.get('sec_type') or '').upper()
    inst_type = 'etf' if sec_type == 'ETF' else 'stock'
    return Instrument(
        symbol=row['symbol'],
        name=row.get('name') or row['symbol'],
        type=inst_type,
        sector=row.get('category') or row.get('industry'),
        industry=row.get('industry'),
        currency=row.get('currency'),
        exchange=row.get('exchange'),
        description=_build_description(row),
    )


# ---------------------------------------------------------------------------
# Recherche SQLite
# ---------------------------------------------------------------------------

def _search_sqlite(query: str, max_results: int = 40) -> List[dict]:
    """
    Recherche dans ibkr_us.sqlite :
      1. ibkr_verification (symboles vérifiés, métadonnées complètes)
      2. us_symbols_raw    (couverture étendue, moins de métadonnées)

    Supporte les requêtes multi-mots : chaque mot est cherché indépendamment (OR).

    Returns:
        Liste de dicts bruts avec les colonnes de la DB.
    """
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return []

    words = [w for w in query.strip().upper().split() if len(w) >= 2]
    if not words:
        return []

    q_upper = query.strip().upper()
    q_start = f"{q_upper}%"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # Construire les conditions OR pour chaque mot sur chaque colonne
        # ibkr_verification : symbol, longName, industry, category
        v_conditions = " OR ".join(
            "UPPER(v.symbol) LIKE ? OR UPPER(v.longName) LIKE ?"
            " OR UPPER(v.industry) LIKE ? OR UPPER(v.category) LIKE ?"
            for _ in words
        )
        v_params = []
        for w in words:
            like = f"%{w}%"
            v_params.extend([like, like, like, like])

        # --- Table ibkr_verification (vérifiés + métadonnées complètes) ---
        cur.execute(
            f"""
            SELECT
                v.symbol,
                v.longName        AS name,
                v.secType         AS sec_type,
                v.primaryExchange AS exchange,
                v.currency,
                v.industry,
                v.category,
                v.subcategory,
                1 AS verified
            FROM ibkr_verification v
            WHERE v.verified = 1
              AND ({v_conditions})
            ORDER BY
                CASE
                    WHEN UPPER(v.symbol) = ?    THEN 0
                    WHEN UPPER(v.symbol) LIKE ? THEN 1
                    ELSE 2
                END,
                v.symbol
            LIMIT ?
            """,
            v_params + [q_upper, q_start, max_results],
        )
        verified_rows = [dict(r) for r in cur.fetchall()]
        verified_syms = {r['symbol'] for r in verified_rows}

        # us_symbols_raw : symbol, security_name
        r_conditions = " OR ".join(
            "UPPER(r.symbol) LIKE ? OR UPPER(r.security_name) LIKE ?"
            for _ in words
        )
        r_params = []
        for w in words:
            like = f"%{w}%"
            r_params.extend([like, like])

        # --- Table us_symbols_raw (couverture étendue, sans doublon avec verified) ---
        cur.execute(
            f"""
            SELECT
                r.symbol,
                r.security_name AS name,
                CASE WHEN r.is_etf = 1 THEN 'ETF' ELSE 'STK' END AS sec_type,
                NULL AS exchange,
                NULL AS currency,
                NULL AS industry,
                NULL AS category,
                NULL AS subcategory,
                0    AS verified
            FROM us_symbols_raw r
            WHERE ({r_conditions})
            ORDER BY
                CASE
                    WHEN UPPER(r.symbol) = ?    THEN 0
                    WHEN UPPER(r.symbol) LIKE ? THEN 1
                    ELSE 2
                END,
                r.symbol
            LIMIT ?
            """,
            r_params + [q_upper, q_start, max_results],
        )
        raw_rows = [dict(r) for r in cur.fetchall() if r['symbol'] not in verified_syms]

    finally:
        conn.close()

    return verified_rows + raw_rows


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def fetch_instrument(symbol: str, use_cache: bool = True) -> Optional[Instrument]:
    """
    Récupère les informations d'un instrument depuis la base SQLite.

    Args:
        symbol:    Symbole de l'instrument
        use_cache: Utiliser le cache si True

    Returns:
        Instrument ou None si non trouvé dans la base
    """
    symbol = symbol.strip().upper()

    if use_cache and symbol in instrument_cache:
        return instrument_cache[symbol]

    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT symbol, longName AS name, secType AS sec_type,
                   primaryExchange AS exchange, currency, industry, category, subcategory
            FROM ibkr_verification
            WHERE symbol = ? AND verified = 1
            """,
            (symbol,),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute(
                """
                SELECT symbol, security_name AS name,
                       CASE WHEN is_etf = 1 THEN 'ETF' ELSE 'STK' END AS sec_type,
                       NULL AS exchange, NULL AS currency,
                       NULL AS industry, NULL AS category, NULL AS subcategory
                FROM us_symbols_raw
                WHERE symbol = ?
                """,
                (symbol,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    instrument = _row_to_instrument(dict(row))
    if use_cache:
        instrument_cache[symbol] = instrument
    return instrument


def search_by_keywords(query: str, max_results: int = 20, fast_mode: bool = False) -> List[dict]:
    """
    Recherche dynamique d'instruments financiers dans la base SQLite locale.

    Args:
        query:       Requête libre ('AAPL', 'nasdaq 100', 'healthcare', 'ETF tech'…)
        max_results: Nombre maximum de résultats
        fast_mode:   Ignoré (conservé pour compatibilité de l'interface)

    Returns:
        Liste de dicts triés par pertinence
    """
    cache_key = f"{query.lower().strip()}:{max_results}"
    if cache_key in search_cache:
        return search_cache[cache_key]

    query_lower = query.lower().strip()
    raw_rows = _search_sqlite(query, max_results=max_results * 2)

    results: List[dict] = []
    seen: set = set()

    for row in raw_rows:
        symbol = row['symbol']
        if symbol in seen or not _is_valid_symbol(symbol):
            continue
        seen.add(symbol)

        instrument = _row_to_instrument(row)
        res = instrument.to_dict()
        res['relevance_score'] = _score_instrument(query_lower, symbol, instrument)
        results.append(res)

    results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    final = results[:max_results]
    search_cache[cache_key] = final
    return final


def get_popular_by_category(category: str) -> List[str]:
    """Retourne des symboles vérifiés IBKR pour une catégorie donnée."""
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cat_like = f"%{category.upper()}%"
        cur.execute(
            """
            SELECT symbol FROM ibkr_verification
            WHERE verified = 1
              AND (UPPER(industry) LIKE ? OR UPPER(category) LIKE ?)
            ORDER BY symbol
            LIMIT 50
            """,
            (cat_like, cat_like),
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def get_all_popular_symbols() -> List[str]:
    """Retourne tous les symboles vérifiés IBKR (dédupliqués, triés)."""
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT symbol FROM ibkr_verification WHERE verified = 1 ORDER BY symbol")
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def get_symbol_name_map() -> dict[str, tuple[str, str, str]]:
    """
    Retourne un dict {symbol: (name, sec_type, industry)} pour tous les symboles
    des deux tables SQLite.  Utilisé pour enrichir l'affichage sans passer par
    search_by_keywords (pas de filtre, parcours complet des tables).

    Returns:
        {symbol: (name, sec_type, industry)}  — les trois champs peuvent être vides.
    """
    db_path = _get_db_path()
    result: dict[str, tuple[str, str, str]] = {}
    if not os.path.exists(db_path):
        return result

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT symbol, COALESCE(longName, symbol), COALESCE(secType, ''), COALESCE(industry, '')
            FROM ibkr_verification
            WHERE verified = 1
            """
        )
        for sym, name, sec_type, industry in cur.fetchall():
            result[sym] = (name, sec_type, industry)

        cur.execute(
            """
            SELECT symbol,
                   COALESCE(security_name, symbol),
                   CASE WHEN is_etf = 1 THEN 'ETF' ELSE 'STK' END
            FROM us_symbols_raw
            """
        )
        for sym, name, sec_type in cur.fetchall():
            if sym not in result:
                result[sym] = (name, sec_type, '')
    finally:
        conn.close()

    return result


def get_categories() -> List[str]:
    """Retourne les catégories d'instruments disponibles dans la base."""
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT industry FROM ibkr_verification
            WHERE verified = 1 AND industry IS NOT NULL AND industry != ''
            ORDER BY industry
            """
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    print(f"Base SQLite : {_get_db_path()}")
    print(f"Symboles vérifiés : {len(get_all_popular_symbols())}")
    print(f"Catégories : {get_categories()[:10]}")
    print()
    for q in ["AAPL", "nasdaq 100", "healthcare", "ETF tech"]:
        print(f"Recherche : '{q}'")
        r = search_by_keywords(q, max_results=5)
        for item in r:
            print(f"  - {item['symbol']}: {item['name']} (score={item.get('relevance_score', 0)})")
        print()
