"""
Agent DSPy ReAct pour la recherche d'instruments financiers via la base SQLite locale.

Architecture :
  - Outil unique : sqlite_symbol_search -> ibkr_us.sqlite (recherche principale)
  - Fallback     : simple_stock_search  -> search_by_keywords() sans LLM

Toutes les donnees proviennent de la base SQLite locale (ibkr_us.sqlite).
"""

from __future__ import annotations

import sys
import os
from typing import List

import dspy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.data.dynamic_stocks import search_by_keywords


# ---------------------------------------------------------------------------
# Outil ReAct — SQLite uniquement
# ---------------------------------------------------------------------------


def sqlite_symbol_search(query: str) -> str:
    """
    Recherche des instruments financiers dans la base SQLite locale (ibkr_us.sqlite).
    Retourne les symboles correspondants avec leur nom, type et bourse principale.
    Utiliser pour trouver des instruments precis et tradables sur IBKR.
    Exemples : 'QLD', 'nasdaq 100', 'AAPL', 'healthcare', 'ETF tech'.
    """
    try:
        results = search_by_keywords(query, max_results=15)
        if not results:
            return f"Aucun resultat pour '{query}' dans la base SQLite."

        lines = [f"Resultats pour '{query}' ({len(results)} trouves) :"]
        for r in results:
            exch = r.get("exchange") or "—"
            typ = r.get("type") or "—"
            ind = r.get("industry") or r.get("sector") or ""
            detail = f" | {ind}" if ind and ind not in ("Unknown", "N/A") else ""
            lines.append(f"  {r['symbol']} | {r['name']} | {typ} | {exch}{detail}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Erreur recherche SQLite : {exc}"


# ---------------------------------------------------------------------------
# Signature DSPy
# ---------------------------------------------------------------------------


class StockSuggestionSignature(dspy.Signature):
    """
    Agent de recherche d'instruments financiers via la base SQLite locale.
    Utilise l'outil disponible pour trouver les instruments les plus pertinents
    a la requete, puis retourne une liste structuree.
    IMPORTANT : tu dois UNIQUEMENT selectionner des symboles presents dans
    available_symbols. Ne jamais inventer ni proposer un symbole absent de cette liste.
    """

    user_query: str = dspy.InputField(
        desc=(
            "Requete libre decrivant l'instrument recherche. "
            "Exemples : 'ETF nasdaq 2x', 'actions tech', 'ETF obligations', 'QLD'."
        )
    )
    available_symbols: str = dspy.InputField(
        desc=(
            "Liste des instruments disponibles dans le store de donnees local, "
            "pre-filtres par la base SQLite pour correspondre a la requete. "
            "Format : une ligne par instrument -> SYMBOLE|NOM|TYPE. "
            "Tu dois UNIQUEMENT choisir parmi ces instruments."
        )
    )
    selected_stocks: str = dspy.OutputField(
        desc=(
            "Instruments selectionnes parmi available_symbols uniquement, un par ligne, "
            "au format strict :\n"
            "SYMBOLE|NOM|DESCRIPTION\n"
            "Exemple : QLD|ProShares Ultra QQQ|ETF 2x NASDAQ-100 de ProShares"
        )
    )
    explanation: str = dspy.OutputField(
        desc="Explication concise (2-3 phrases) des resultats et de la pertinence des instruments choisis."
    )


# ---------------------------------------------------------------------------
# Agent principal
# ---------------------------------------------------------------------------


class StockSearchAgent(dspy.Module):
    """
    Agent ReAct de recherche d'instruments financiers via SQLite exclusivement.
    """

    def __init__(self):
        super().__init__()
        self.react = dspy.ReAct(
            StockSuggestionSignature,
            tools=[sqlite_symbol_search],
            max_iters=5,
        )

    def forward(
        self, user_query: str, max_results: int = 10, parquet_symbols: set = None
    ):
        """
        Recherche et selectionne les instruments les plus pertinents.

        Args:
            user_query      : requete libre de l'utilisateur
            max_results     : nombre de resultats souhaites (hint pour le LLM)
            parquet_symbols : ensemble des symboles disponibles dans le store Parquet.
                              Si fourni, seuls les instruments presents dans cet ensemble
                              sont proposes au LLM via available_symbols.

        Returns:
            Resultat DSPy avec selected_stocks et explanation
        """
        words = _query_words(user_query)

        # Aucune limite — retourne tous les résultats correspondants
        raw_results = search_by_keywords(user_query, max_results=None)

        # Garder uniquement les resultats dont la description contient un mot de la requete
        if words:
            raw_results = [r for r in raw_results if _matches_query_words(r, words)]

        # Filtrer aux symboles ayant des donnees Parquet
        if parquet_symbols:
            raw_results = [r for r in raw_results if r["symbol"] in parquet_symbols]

        # Limiter le contexte LLM a 50 candidats (eviter de depasser la fenetre)
        candidates = raw_results[:50]

        # Formater la liste de candidats pour le contexte LLM
        if candidates:
            lines = [
                f"{r['symbol']}|{r['name']}|{r.get('type', '')}" for r in candidates
            ]
            available_str = "\n".join(lines)
        else:
            available_str = "Aucun instrument disponible pour cette requete."

        hint = f"{user_query} (max {max_results} results)"
        result = self.react(user_query=hint, available_symbols=available_str)

        # Garde-fou anti-injection : ne garder que les symboles réellement présents
        # dans les candidats. Le LLM ne peut pas introduire de symbole arbitraire,
        # même si le prompt est manipulé.
        allowed_symbols = {r["symbol"] for r in candidates}
        if allowed_symbols and getattr(result, "selected_stocks", None):
            kept_lines = []
            for line in result.selected_stocks.strip().split("\n"):
                symbol = line.split("|")[0].strip()
                if symbol in allowed_symbols:
                    kept_lines.append(line)
            result.selected_stocks = "\n".join(kept_lines)

        return result


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse_stock_suggestions(selected_stocks_text: str) -> List[dict]:
    """
    Parse la sortie de l'agent au format SYMBOLE|NOM|DESCRIPTION.

    Returns:
        Liste de dicts {symbol, name, description}
    """
    stocks = []
    for line in selected_stocks_text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            stocks.append(
                {
                    "symbol": parts[0].strip(),
                    "name": parts[1].strip(),
                    "description": parts[2].strip(),
                }
            )
        elif len(parts) == 2:
            stocks.append(
                {
                    "symbol": parts[0].strip(),
                    "name": parts[1].strip(),
                    "description": "",
                }
            )
    return stocks


# ---------------------------------------------------------------------------
# Helpers de filtrage
# ---------------------------------------------------------------------------


def _query_words(query: str) -> list[str]:
    """Retourne les mots significatifs (>=2 chars) de la requete, en minuscules."""
    return [w.lower() for w in query.split() if len(w) >= 2]


def _matches_query_words(result: dict, words: list[str]) -> bool:
    """
    Retourne True si au moins un mot de la requete apparait dans les champs
    textuels du resultat (symbol, name, description, sector, industry, type).
    """
    if not words:
        return True
    text = " ".join(
        filter(
            None,
            [
                result.get("symbol", ""),
                result.get("name", ""),
                result.get("description", ""),
                result.get("sector", ""),
                result.get("industry", ""),
                result.get("type", ""),
            ],
        )
    ).lower()
    return any(word in text for word in words)


# ---------------------------------------------------------------------------
# Fallback sans LLM
# ---------------------------------------------------------------------------


def simple_stock_search(
    query: str,
    max_results: int = 10,
    fast_mode: bool = True,
    parquet_symbols: set = None,
) -> tuple[List[dict], str]:
    """
    Recherche sans LLM via la base SQLite locale.

    Retourne TOUS les resultats dont la description contient au moins un mot
    de la requete (pas de cap artificiel). max_results n'est utilise que comme
    hint pour le fetch SQLite initial.

    Args:
        query          : Requete de recherche
        max_results    : Hint pour le fetch SQLite (la liste finale peut depasser)
        fast_mode      : Ignore (conserve pour compatibilite de l'interface)
        parquet_symbols: Si fourni, filtre les resultats aux symboles ayant des donnees Parquet.

    Returns:
        (liste de stocks, explication)
    """
    words = _query_words(query)

    # Aucune limite — retourne tous les résultats correspondants
    raw = search_by_keywords(query, max_results=None)

    # Garder uniquement les resultats dont la description contient un mot de la requete
    if words:
        raw = [r for r in raw if _matches_query_words(r, words)]

    # Filtrer aux symboles avec donnees Parquet

    if parquet_symbols:
        raw = [r for r in raw if r["symbol"] in parquet_symbols]

    if not raw:
        return [], f"Aucun instrument trouve pour '{query}'"

    stocks = [
        {
            "symbol": s["symbol"],
            "name": s["name"],
            "description": s["description"],
            "type": s.get("type", "Unknown"),
            "sector": s.get("sector", "N/A"),
            "industry": s.get("industry"),
            "exchange": s.get("exchange"),
            "market_cap": s.get("market_cap"),
        }
        for s in raw
    ]

    sectors = {s["sector"] for s in stocks if s.get("sector") and s["sector"] != "N/A"}
    if sectors:
        explanation = (
            f"Found {len(stocks)} instrument(s) for '{query}'. "
            f"Sectors: {', '.join(list(sectors)[:3])}"
        )
    else:
        explanation = f"Found {len(stocks)} instrument(s) for '{query}'"

    return stocks, explanation


# ---------------------------------------------------------------------------
# Tests CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Test de l'agent de recherche (SQLite local) ===\n")

    for q in ["nasdaq 100", "healthcare", "AAPL", "ETF tech"]:
        print(f"Recherche : '{q}'")
        r, expl = simple_stock_search(q, max_results=5)
        print(f"  {expl}")
        for s in r:
            print(f"    - {s['symbol']}: {s['name']}")
        print()
