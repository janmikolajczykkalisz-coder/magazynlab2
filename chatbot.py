# from dotenv import load_dotenv
# import os
# import json
# import re
# from typing import Dict, Any, List, Optional
# import streamlit as st
# import pandas as pd
# from openai import OpenAI
#
# # Wczytaj zmienne środowiskowe z .env (HF_TOKEN)
# load_dotenv()
#
# client = OpenAI(
#     base_url="https://router.huggingface.co/v1",
#     api_key=os.environ.get("HF_TOKEN")
# )
#
# # Dozwolone operacje
# AGG_OPS = {"count", "sum", "avg", "min", "max"}
# FILTER_OPS = {"eq", "neq", "contains", "gt", "lt", "gte", "lte"}
#
# # Twoje nazwy kolumn
# STOCK_COL_CANDIDATES = ["Ilość", "Stan", "Stan_mag", "Quantity", "Stock", "Qty"]
#
# def _qty_col(df: pd.DataFrame) -> Optional[str]:
#     """Znajdź kolumnę z ilością/stokiem."""
#     for c in STOCK_COL_CANDIDATES:
#         if c in df.columns:
#             return c
#     for c in df.columns:
#         if pd.api.types.is_numeric_dtype(df[c]):
#             return c
#     return None
#
# def _extract_json(text: str) -> Optional[Dict[str, Any]]:
#     """Wyciągnij pierwszy blok JSON-a z odpowiedzi modelu."""
#     m = re.search(r"\{.*\}", text, re.DOTALL)
#     if not m:
#         return None
#     try:
#         return json.loads(m.group(0))
#     except json.JSONDecodeError:
#         return None
#
# def _llm_plan(
#     question: str,
#     columns: List[str],
#     qty_col: Optional[str]
# ) -> Optional[Dict[str, Any]]:
#     """Poproś LLM o plan (JSON)."""
#     schema_hint = {
#         "action": "filter_list | count | aggregate | low_stock | out_of_stock",
#         "filters": [{"column": "nazwa_kolumny", "op": "eq|neq|contains|gt|lt|gte|lte", "value": "wartość"}],
#         "aggregate": {"op": "count|sum|avg|min|max", "column": "nazwa_kolumny"},
#         "columns": ["kolumna1", "kolumna2"],
#         "limit": 50,
#         "threshold": 0
#     }
#
#     system_msg = (
#         "Jesteś parserem zapytań magazynowych. "
#         "Zwracasz wyłącznie JEDEN obiekt JSON zgodny ze schematem. "
#         "Nie dodawaj żadnego opisu poza JSON-em."
#     )
#     user_msg = (
#         f"Pytanie użytkownika: {question}\n"
#         f"Dostępne kolumny: {', '.join(columns)}\n"
#         f"Sugerowana kolumna ilości: {qty_col or '(brak)'}\n\n"
#         f"Schemat przykładowy: {json.dumps(schema_hint, ensure_ascii=False)}\n"
#         "Zwróć tylko surowe JSON."
#     )
#
#     try:
#         resp = client.chat.completions.create(
#             model="mistralai/Mistral-7B-Instruct-v0.2:featherless-ai",
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg}
#             ],
#             temperature=0
#         )
#         raw = resp.choices[0].message.content.strip()
#         return _extract_json(raw)
#     except Exception:
#         return None
#
# def _apply_filters(
#     df: pd.DataFrame,
#     filters: List[Dict[str, Any]]
# ) -> pd.DataFrame:
#     """Nakłada filtry na DataFrame."""
#     out = df.copy()
#     for f in filters or []:
#         col = f.get("column")
#         op = (f.get("op") or "").lower()
#         val = f.get("value")
#
#         if col not in out.columns or op not in FILTER_OPS:
#             continue
#
#         if op == "contains":
#             out = out[out[col].astype(str).str.contains(str(val), case=False, na=False)]
#         elif op == "eq":
#             out = out[out[col].astype(str).str.lower() == str(val).lower()]
#         elif op == "neq":
#             out = out[out[col].astype(str).str.lower() != str(val).lower()]
#         else:
#             # porównania numeryczne
#             try:
#                 num = pd.to_numeric(out[col], errors="coerce")
#                 v = float(val)
#                 if op == "gt":
#                     out = out[num > v]
#                 elif op == "lt":
#                     out = out[num < v]
#                 elif op == "gte":
#                     out = out[num >= v]
#                 elif op == "lte":
#                     out = out[num <= v]
#             except ValueError:
#                 pass
#     return out
#
# def _fmt_table_md(
#     df: pd.DataFrame,
#     columns: Optional[List[str]],
#     limit: int = 20
# ) -> str:
#     """Stwórz tabelę Markdown z wyników."""
#     if df.empty:
#         return "Brak wyników."
#
#     if columns:
#         cols = [c for c in columns if c in df.columns]
#         if cols:
#             df = df[cols]
#
#     df = df.head(limit)
#
#     headers = "| " + " | ".join(df.columns) + " |"
#     sep = "| " + " | ".join("---" for _ in df.columns) + " |"
#     rows = ["| " + " | ".join(str(x) for x in row) + " |" for _, row in df.iterrows()]
#
#     return "\n".join([headers, sep] + rows)
#
# def _answer_from_df(
#     df: pd.DataFrame,
#     plan: Dict[str, Any],
#     qty_col: Optional[str]
# ) -> str:
#     """Na podstawie planu zwróć gotową odpowiedź."""
#     action = (plan.get("action") or "").lower()
#     filters = plan.get("filters", [])
#     aggregate = plan.get("aggregate")
#     columns = plan.get("columns")
#     limit = int(plan.get("limit", 50))
#     threshold = float(plan.get("threshold", 0))
#
#     data = _apply_filters(df, filters)
#
#     if action == "out_of_stock":
#         if not qty_col:
#             return "Nie znaleziono kolumny ilości — nie mogę sprawdzić braków."
#         q = pd.to_numeric(data[qty_col], errors="coerce").fillna(0)
#         data = data[q == 0]
#         return _fmt_table_md(data, columns, limit)
#
#     if action == "low_stock":
#         if not qty_col:
#             return "Nie znaleziono kolumny ilości — nie mogę sprawdzić niskich stanów."
#         q = pd.to_numeric(data[qty_col], errors="coerce").fillna(0)
#         data = data[q <= threshold]
#         return _fmt_table_md(data, columns, limit)
#
#     if action == "count":
#         return f"Liczba pozycji: {len(data)}"
#
#     if action == "aggregate":
#         if not aggregate:
#             return "Brak zdefiniowanej agregacji."
#         op = (aggregate.get("op") or "").lower()
#         col = aggregate.get("column")
#
#         if op not in AGG_OPS:
#             return f"Nieobsługiwana agregacja: {op}"
#         if op == "count":
#             return f"Liczba pozycji: {len(data)}"
#         if not col or col not in data.columns:
#             return f"Kolumna do agregacji nieznana: {col}"
#
#         series = pd.to_numeric(data[col], errors="coerce").dropna()
#         if series.empty:
#             return "Brak danych liczbowych do agregacji."
#
#         if op == "sum":
#             val = series.sum()
#         elif op == "avg":
#             val = series.mean()
#         elif op == "min":
#             val = series.min()
#         elif op == "max":
#             val = series.max()
#         else:
#             val = None
#
#         return f"{op.upper()}({col}) = {val}"
#
#     # domyślnie: wypisz listę po filtrach
#     return _fmt_table_md(data, columns, limit)
#
# def _ask_with_context(question: str, csv_snippet: str) -> str:
#     """Fallback – zapytaj AI z małym fragmentem CSV."""
#     try:
#         resp = client.chat.completions.create(
#             model="meta-llama/Llama-3.1-8B-Instruct:fireworks-ai",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": "Jesteś asystentem do danych magazynowych. "
#                 },
#                 {
#                     "role": "user",
#                     "content": f"Oto fragment CSV:\n{csv_snippet}\n\nPytanie:\n{question}"
#                 }
#             ],
#             temperature=0
#         )
#         return resp.choices[0].message.content.strip()
#     except Exception as e:
#         return f"Błąd AI: {e}"
#
# def ask(df, history):
#     try:
#         system_prompt = (
#             "Jesteś interaktywnym asystentem w aplikacji magazynowej. "
#             "Twoim zadaniem jest pomagać użytkownikowi w zarządzaniu produktami, "
#             "podpowiadać gdzie znajdują się przyciski, przypominać o zapisie zmian, "
#             "a także odpowiadać na pytania w prostym języku."
#         )
#
#         state_summary = (
#             f"Aktualny stan: {len(df)} produktów. "
#             f"Oczekujące zmiany: {len(st.session_state.pending_deltas)}. "
#             f"Do usunięcia: {len(st.session_state.to_delete)}."
#         )
#
#         # jeśli history to string, zamień na listę
#         if isinstance(history, str):
#             history = [{"role": "user", "content": history}]
#
#         messages = [
#             {"role": "system", "content": system_prompt},
#             {"role": "system", "content": state_summary}
#         ] + history
#
#         completion = client.chat.completions.create(
#             model="mistralai/Mistral-7B-Instruct-v0.2:featherless-ai",
#             messages=messages,
#             temperature=0.6
#         )
#         return completion.choices[0].message.content.strip()
#     except Exception as e:
#         return f"Błąd połączenia z AI: {e}"
