"""Conservative location normalization.

The original string is always stored. Structured fields are filled only when the string maps
unambiguously: a single known country, "City, US-State", or "City, Country". Multi-country
lists ("Canada, USA"), regions ("Europe", "APAC") and bare city names stay unstructured.
"""

import re
from dataclasses import dataclass

from backend.ingestion.transformations.text import clean_inline

COUNTRIES: dict[str, str] = {
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "united states": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "india": "India",
    "canada": "Canada",
    "germany": "Germany",
    "france": "France",
    "spain": "Spain",
    "portugal": "Portugal",
    "italy": "Italy",
    "netherlands": "Netherlands",
    "belgium": "Belgium",
    "ireland": "Ireland",
    "poland": "Poland",
    "sweden": "Sweden",
    "norway": "Norway",
    "denmark": "Denmark",
    "finland": "Finland",
    "switzerland": "Switzerland",
    "austria": "Austria",
    "czechia": "Czechia",
    "czech republic": "Czechia",
    "romania": "Romania",
    "bulgaria": "Bulgaria",
    "greece": "Greece",
    "hungary": "Hungary",
    "croatia": "Croatia",
    "serbia": "Serbia",
    "ukraine": "Ukraine",
    "estonia": "Estonia",
    "latvia": "Latvia",
    "lithuania": "Lithuania",
    "slovakia": "Slovakia",
    "slovenia": "Slovenia",
    "cyprus": "Cyprus",
    "israel": "Israel",
    "turkiye": "Türkiye",
    "turkey": "Türkiye",
    "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "australia": "Australia",
    "new zealand": "New Zealand",
    "singapore": "Singapore",
    "japan": "Japan",
    "china": "China",
    "hong kong": "Hong Kong",
    "south korea": "South Korea",
    "philippines": "Philippines",
    "vietnam": "Vietnam",
    "thailand": "Thailand",
    "malaysia": "Malaysia",
    "indonesia": "Indonesia",
    "pakistan": "Pakistan",
    "bangladesh": "Bangladesh",
    "sri lanka": "Sri Lanka",
    "brazil": "Brazil",
    "mexico": "Mexico",
    "argentina": "Argentina",
    "colombia": "Colombia",
    "chile": "Chile",
    "peru": "Peru",
    "costa rica": "Costa Rica",
    "south africa": "South Africa",
    "nigeria": "Nigeria",
    "kenya": "Kenya",
    "egypt": "Egypt",
}

US_STATES: dict[str, str] = {
    "al": "Alabama",
    "ak": "Alaska",
    "az": "Arizona",
    "ar": "Arkansas",
    "ca": "California",
    "co": "Colorado",
    "ct": "Connecticut",
    "de": "Delaware",
    "fl": "Florida",
    "ga": "Georgia",
    "hi": "Hawaii",
    "id": "Idaho",
    "il": "Illinois",
    "in": "Indiana",
    "ia": "Iowa",
    "ks": "Kansas",
    "ky": "Kentucky",
    "la": "Louisiana",
    "me": "Maine",
    "md": "Maryland",
    "ma": "Massachusetts",
    "mi": "Michigan",
    "mn": "Minnesota",
    "ms": "Mississippi",
    "mo": "Missouri",
    "mt": "Montana",
    "ne": "Nebraska",
    "nv": "Nevada",
    "nh": "New Hampshire",
    "nj": "New Jersey",
    "nm": "New Mexico",
    "ny": "New York",
    "nc": "North Carolina",
    "nd": "North Dakota",
    "oh": "Ohio",
    "ok": "Oklahoma",
    "or": "Oregon",
    "pa": "Pennsylvania",
    "ri": "Rhode Island",
    "sc": "South Carolina",
    "sd": "South Dakota",
    "tn": "Tennessee",
    "tx": "Texas",
    "ut": "Utah",
    "vt": "Vermont",
    "va": "Virginia",
    "wa": "Washington",
    "wv": "West Virginia",
    "wi": "Wisconsin",
    "wy": "Wyoming",
    "dc": "District of Columbia",
}
_STATE_NAMES = {name.lower(): name for name in US_STATES.values()}

# Indian states / UTs, so "Bengaluru, Karnataka" resolves to India without a city gazetteer.
INDIA_STATES = {
    s.lower(): s
    for s in [
        "Andhra Pradesh",
        "Assam",
        "Bihar",
        "Delhi",
        "Goa",
        "Gujarat",
        "Haryana",
        "Karnataka",
        "Kerala",
        "Madhya Pradesh",
        "Maharashtra",
        "Odisha",
        "Punjab",
        "Rajasthan",
        "Tamil Nadu",
        "Telangana",
        "Uttar Pradesh",
        "West Bengal",
        "Chandigarh",
    ]
}

# Multi-country regions. A string mentioning one is never resolved to a single country/city.
REGIONS = {
    "europe",
    "eu",
    "emea",
    "apac",
    "latam",
    "americas",
    "north america",
    "south america",
    "central america",
    "asia",
    "africa",
    "middle east",
    "oceania",
    "nordics",
    "dach",
    "benelux",
    "cee",
    "mena",
    "anz",
}

_WORLDWIDE = re.compile(r"^(remote|anywhere|worldwide|global|earth|work from anywhere)$", re.I)
_HYBRID = re.compile(r"\bhybrid\b", re.I)
_ONSITE = re.compile(r"\b(on[- ]?site|in[- ]office|office[- ]based)\b", re.I)


@dataclass(frozen=True)
class NormalizedLocation:
    original: str | None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    worldwide: bool = False


def _lookup_country(token: str) -> str | None:
    return COUNTRIES.get(token.strip().strip(".").lower())


def normalize_location(raw: str | None) -> NormalizedLocation:
    original = clean_inline(raw)
    if not original:
        return NormalizedLocation(original=None)
    text = re.sub(r"\((?:remote|hybrid|on[- ]?site)\)", "", original, flags=re.I).strip(" ,;-")
    if not text or _WORLDWIDE.match(text):
        return NormalizedLocation(original=original, worldwide=True)
    # Lists of several places ("Canada,  USA", "Berlin; Munich") are kept unstructured.
    if ";" in text or "/" in text or " or " in text.lower():
        return NormalizedLocation(original=original)
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if any(p.lower() in REGIONS for p in parts):
        return NormalizedLocation(original=original)
    if len(parts) == 1:
        return NormalizedLocation(original=original, country=_lookup_country(parts[0]))
    if len(parts) in (2, 3):
        last = parts[-1].lower()
        country = _lookup_country(last)
        if len(parts) == 3 and country:
            region = parts[1]
            return NormalizedLocation(
                original=original, city=parts[0], region=region, country=country
            )
        if len(parts) == 2:
            state = US_STATES.get(last) or _STATE_NAMES.get(last)
            if state:
                return NormalizedLocation(
                    original=original, city=parts[0], region=state, country="United States"
                )
            india_state = INDIA_STATES.get(last)
            if india_state:
                return NormalizedLocation(
                    original=original, city=parts[0], region=india_state, country="India"
                )
            first_country = _lookup_country(parts[0])
            if country and not first_country:
                return NormalizedLocation(original=original, city=parts[0], country=country)
    return NormalizedLocation(original=original)


def classify_work_mode(
    *texts: str | None, source_default: str | None
) -> tuple[str | None, str | None]:
    """(work_mode, basis). Explicit hybrid/on-site wording wins; otherwise the source default
    (remote-only boards) is applied and recorded as such so it is never mistaken for evidence."""
    joined = " ".join(t for t in texts if t)
    if _HYBRID.search(joined):
        return "hybrid", "text"
    if _ONSITE.search(joined):
        return "onsite", "text"
    if source_default:
        return source_default, "source_default"
    return None, None
