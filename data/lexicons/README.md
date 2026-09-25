# Lexicons

Word lists used by the Iranian detector (`docs/04-iranian-detection.md`).
One entry per line; lines starting with `#` are comments. Matching is
case-insensitive and on whole words (Latin) or substrings (Persian script).
Edit these files to tune detection without touching code.

| File | Signal |
|---|---|
| `keywords_explicit.txt` | `explicit_keyword` |
| `product_terms.txt`, `product_adjectives.txt` | `persian_product_term` (downgrades "Persian Bokhara Rug", "Persian cat", ...) |
| `iranian_places.txt` | `iranian_place_name` |
| `iranian_places_ambiguous.txt` | `iranian_place_name` with weight 0.15 |
| `iranian_place_adjectives.txt` | `persian_personal_name` (Shirazi, Tehrani, ... are surnames) |
| `surname_suffixes.txt` | `persian_personal_name` |
| `persian_foods.txt` | `iranian_food_terms` |
| `occasions.txt` | `nowruz_yalda_mentions` |
| `negative_keywords.txt` | `negative_keyword` |
