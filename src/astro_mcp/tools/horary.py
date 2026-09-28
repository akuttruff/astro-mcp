"""Horary astrology: the chart of a question, its considerations before
judgment, and the judgment itself -- do the significators come together?

immanuel supplies the astronomy and the traditional tables: positions and
speeds, Regiomontanus houses, essential dignities under traditional
rulerships with Lilly's triplicities and Ptolemy's terms, the Part of
Fortune. This module applies the horary rules to them: combustion, strictures
before judgment, perfection, prohibition, translation and collection of light,
refranation, reception, and the traditional timing of an event.

The rule code reads positions through a small Ephemeris interface, so tests
can drive it with invented planetary motion and check each rule directly.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Protocol

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from astro_mcp.tools.timing import (
    SIGNS, _jd, _local, _place_note, _position, _resolve_place, _zone, hour_at, void_periods,
)
from astro_mcp.utils import error_response, validate_date_string

PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
ASPECTS = {"conjunction": 0.0, "sextile": 60.0, "square": 90.0, "trine": 120.0, "opposition": 180.0}
EASY = {"conjunction", "sextile", "trine"}

# Search steps (days) by the fastest body involved; horizon for any search.
STEP = {"Moon": 1 / 24, "Mercury": 0.25, "Venus": 0.25, "Sun": 0.25, "Mars": 0.5, "Jupiter": 1.0, "Saturn": 1.0}
HORIZON_DAYS = 400

COMBUST_ORB = 8.5
CAZIMI_ORB = 17 / 60
UNDER_BEAMS_ORB = 17.0

MODALITY = ["cardinal", "fixed", "mutable"]  # Aries, Taurus, Gemini, then repeating
ELEMENT = ["fire", "earth", "air", "water"]  # Aries, Taurus, Gemini, Cancer, then repeating


def _dumps(data: dict) -> str:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _sign_index(lon: float) -> int:
    return int((lon % 360) // 30)


# ---------------------------------------------------------------------------
# Ephemeris access
# ---------------------------------------------------------------------------

class Ephemeris(Protocol):
    def lon(self, planet: str, jd: float) -> float: ...
    def speed(self, planet: str, jd: float) -> float: ...


class ImmanuelEphemeris:
    """Positions and speeds from immanuel's Swiss Ephemeris wrapper."""

    def _get(self, planet: str, jd: float) -> dict:
        from immanuel.const import chart
        from immanuel.tools import sweph
        return sweph.planet(getattr(chart, planet.upper()), jd)

    def lon(self, planet: str, jd: float) -> float:
        return self._get(planet, jd)["lon"] % 360

    def speed(self, planet: str, jd: float) -> float:
        return self._get(planet, jd)["speed"]


def _step(*planets: str) -> float:
    return min(STEP.get(p, 0.25) for p in planets)


def _offset(eph: Ephemeris, a: str, b: str, target: float, jd: float) -> float:
    """Signed distance (degrees) of a's elongation from b away from `target`."""
    elong = (eph.lon(a, jd) - eph.lon(b, jd)) % 360
    return (elong - target + 180) % 360 - 180


def _bisect(f, lo: float, hi: float, iterations: int = 40) -> float:
    flo = f(lo)
    for _ in range(iterations):
        mid = (lo + hi) / 2
        fmid = f(mid)
        if flo * fmid <= 0:
            hi = mid
        else:
            lo, flo = mid, fmid
    return (lo + hi) / 2


@dataclass
class Contact:
    """An exact Ptolemaic aspect between two planets."""
    a: str
    b: str
    aspect: str
    jd: float


def next_perfection(eph: Ephemeris, a: str, b: str, start: float, end: float) -> Contact | None:
    """The first exact Ptolemaic aspect between a and b in (start, end]."""
    return _scan_perfection(eph, a, b, start, end, forward=True)


def last_perfection(eph: Ephemeris, a: str, b: str, start: float, end: float) -> Contact | None:
    """The most recent exact Ptolemaic aspect between a and b in [start, end)."""
    return _scan_perfection(eph, a, b, start, end, forward=False)


def _scan_perfection(eph: Ephemeris, a: str, b: str, start: float, end: float, forward: bool) -> Contact | None:
    if end <= start:
        return None
    step = _step(a, b)
    targets = []
    for name, angle in ASPECTS.items():
        for t in {angle % 360, (360 - angle) % 360}:
            targets.append((name, t))
    best: Contact | None = None
    jd = start if forward else end
    while (jd < end) if forward else (jd > start):
        nxt = min(jd + step, end) if forward else max(jd - step, start)
        lo, hi = (jd, nxt) if forward else (nxt, jd)
        for name, t in targets:
            f_lo, f_hi = _offset(eph, a, b, t, lo), _offset(eph, a, b, t, hi)
            if f_lo * f_hi <= 0 and abs(f_lo) < 90 and abs(f_hi) < 90 and not (f_lo == 0 and f_hi == 0):
                when = _bisect(lambda x: _offset(eph, a, b, t, x), lo, hi)
                if start < when <= end if forward else start <= when < end:
                    if best is None or (when < best.jd if forward else when > best.jd):
                        best = Contact(a, b, name, when)
        if best is not None:
            return best
        jd = nxt
    return None


def next_sign_change(eph: Ephemeris, planet: str, start: float, horizon: float = HORIZON_DAYS) -> float | None:
    """When the planet next leaves its current sign (either direction), or None within the horizon."""
    step = STEP.get(planet, 0.25)
    sign = _sign_index(eph.lon(planet, start))
    jd = start
    while jd < start + horizon:
        nxt = jd + step
        if _sign_index(eph.lon(planet, nxt)) != sign:
            lo, hi = jd, nxt
            for _ in range(40):
                mid = (lo + hi) / 2
                if _sign_index(eph.lon(planet, mid)) == sign:
                    lo = mid
                else:
                    hi = mid
            return hi
        jd = nxt
    return None


def next_station(eph: Ephemeris, planet: str, start: float, end: float) -> float | None:
    """When the planet next turns retrograde or direct before `end`, if it does."""
    if planet in ("Sun", "Moon"):
        return None
    step = STEP.get(planet, 0.25)
    jd = start
    s0 = eph.speed(planet, jd)
    while jd < end:
        nxt = min(jd + step, end)
        s1 = eph.speed(planet, nxt)
        # A turn: the speed changes sign, or reaches zero exactly on a sample.
        if (s0 > 0 >= s1) or (s0 < 0 <= s1):
            return nxt if s1 == 0 else _bisect(lambda x: eph.speed(planet, x), jd, nxt)
        jd, s0 = nxt, s1
    return None


def _window_end(eph: Ephemeris, jd: float, *planets: str) -> float:
    """The first moment any of these planets changes sign (or the horizon).
    Cached on the ephemeris object: every rule of a judgment asks again."""
    cache = eph.__dict__.setdefault("_sign_changes", {})
    ends = []
    for p in planets:
        if (p, jd) not in cache:
            cache[(p, jd)] = next_sign_change(eph, p, jd)
        ends.append(cache[(p, jd)])
    return min([e for e in ends if e is not None] or [jd + HORIZON_DAYS])


def degrees_between(eph: Ephemeris, a: str, b: str, aspect: str, jd: float) -> float:
    angle = ASPECTS[aspect]
    return min(abs(_offset(eph, a, b, t, jd)) for t in {angle % 360, (360 - angle) % 360})


# ---------------------------------------------------------------------------
# Rules of judgment
# ---------------------------------------------------------------------------

@dataclass
class Judgment:
    verdict: str
    summary: str
    perfection: Contact | None
    via: str | None
    testimonies: list[str]


def _phrase(c: Contact) -> str:
    return f"{c.a} {c.aspect} {c.b}"


def judge(eph: Ephemeris, a: str, b: str, jd: float, describe_time) -> Judgment:
    """Whether the significators a (querent) and b (quesited) come together.

    In order: direct perfection before either changes sign (and whether a
    third planet prohibits it first); translation of light; collection of
    light; refranation. `describe_time` renders a jd for the text.
    """
    testimonies: list[str] = []
    others = [p for p in PLANETS if p not in (a, b)]
    end = _window_end(eph, jd, a, b)

    direct = next_perfection(eph, a, b, jd, end)
    if direct:
        # Prohibition: another planet perfects with a significator first.
        # Not the Moon, unless she is a significator: she aspects every planet
        # within days, and read strictly would forbid almost any perfection
        # more than a day off. Her contacts count as testimony instead.
        blockers = []
        for c in others:
            if c == "Moon":
                continue
            c_end = min(direct.jd, _window_end(eph, jd, c))
            for sig in (a, b):
                hit = next_perfection(eph, c, sig, jd, c_end)
                if hit and hit.jd < direct.jd:
                    blockers.append(hit)
        if blockers:
            first = min(blockers, key=lambda h: h.jd)
            testimonies.append(
                f"{first.a} perfects a {first.aspect} with {first.b} ({describe_time(first.jd)}) before "
                f"{_phrase(direct)} can: prohibition."
            )
            return Judgment(
                "prohibited",
                f"The significators would meet by {direct.aspect}, but {first.a} reaches {first.b} first and "
                "cuts it off: something intervenes before the matter comes together.",
                direct, first.a, testimonies,
            )
        ease = "easily" if direct.aspect in EASY else "but with difficulty or effort"
        testimonies.append(f"{_phrase(direct)} perfects {describe_time(direct.jd)}, before either changes sign.")
        return Judgment(
            "perfects",
            f"Yes: the significators come together by {direct.aspect} ({ease}).",
            direct, None, testimonies,
        )

    # Translation: a faster planet separates from one significator and carries
    # the light to the other.
    for t in others:
        if abs(eph.speed(t, jd)) <= max(abs(eph.speed(a, jd)), abs(eph.speed(b, jd))):
            continue
        t_end = min(_window_end(eph, jd, t), end)
        for frm, to in ((a, b), (b, a)):
            past = last_perfection(eph, t, frm, jd - 30, jd)
            if not past:
                continue
            # The separation must be recent: since the translator entered its sign.
            if _sign_index(eph.lon(t, past.jd)) != _sign_index(eph.lon(t, jd)):
                continue
            onward = next_perfection(eph, t, to, jd, t_end)
            if onward:
                testimonies.append(
                    f"{t} separated from {frm} ({past.aspect}) and applies to {to} ({onward.aspect}, "
                    f"{describe_time(onward.jd)}): translation of light."
                )
                return Judgment(
                    "perfects by translation",
                    f"Yes, through a go-between: {t} carries the connection from {frm} to {to}.",
                    onward, t, testimonies,
                )

    # Collection: a slower planet receives both significators' aspects.
    for c in others:
        if abs(eph.speed(c, jd)) >= min(abs(eph.speed(a, jd)), abs(eph.speed(b, jd))):
            continue
        hits = []
        for sig in (a, b):
            sig_end = min(_window_end(eph, jd, sig, c), jd + HORIZON_DAYS)
            hit = next_perfection(eph, sig, c, jd, sig_end)
            if hit:
                hits.append(hit)
        if len(hits) == 2:
            later = max(hits, key=lambda h: h.jd)
            testimonies.append(
                f"Both significators apply to {c}: {_phrase(hits[0])} and {_phrase(hits[1])}: collection of light."
            )
            return Judgment(
                "perfects by collection",
                f"Yes, through a third party: {c} gathers both significators' light.",
                later, c, testimonies,
            )

    # Refranation: applying now, but one turns before they meet.
    closest = min(ASPECTS, key=lambda asp: degrees_between(eph, a, b, asp, jd))
    gap_now = degrees_between(eph, a, b, closest, jd)
    gap_soon = degrees_between(eph, a, b, closest, jd + _step(a, b))
    if gap_now <= 12 and gap_soon < gap_now:
        for p in (a, b):
            station = next_station(eph, p, jd, end)
            if station:
                testimonies.append(
                    f"{a} and {b} are applying to a {closest} ({gap_now:.1f}° apart), but {p} turns "
                    f"{'retrograde' if eph.speed(p, jd) > 0 else 'direct'} {describe_time(station)} before it "
                    "perfects: refranation."
                )
                return Judgment(
                    "refranation",
                    "No: the matter gets under way, but one side backs out before it is concluded.",
                    None, p, testimonies,
                )

    testimonies.append(f"{a} and {b} make no aspect before one of them changes sign.")
    return Judgment(
        "no perfection",
        "No: the significators don't come together while this situation lasts.",
        None, None, testimonies,
    )


def traditional_timing(eph: Ephemeris, contact: Contact, jd: float, houses: dict[str, int]) -> dict:
    """Degrees still to travel, and the unit the tradition reads them in:
    cardinal signs and angular houses count days, mutable signs and
    succedent houses weeks, fixed signs and cadent houses months."""
    mover = contact.a if abs(eph.speed(contact.a, jd)) >= abs(eph.speed(contact.b, jd)) else contact.b
    degrees = round(degrees_between(eph, contact.a, contact.b, contact.aspect, jd), 1)
    modality = MODALITY[_sign_index(eph.lon(mover, jd)) % 3]
    house = houses.get(mover)
    place = None if house is None else ("angular" if house in (1, 4, 7, 10) else "succedent" if house in (2, 5, 8, 11) else "cadent")
    by_sign = {"cardinal": "days", "mutable": "weeks", "fixed": "months"}[modality]
    by_house = {"angular": "days", "succedent": "weeks", "cadent": "months"}.get(place or "", by_sign)
    unit = by_sign if by_sign == by_house else f"{by_sign} or {by_house}"
    return {
        "degrees_to_perfection": degrees,
        "moving_planet": mover,
        "sign_quality": modality,
        "house_place": place,
        "reading": f"about {degrees:g} {unit}",
    }


# ---------------------------------------------------------------------------
# The chart
# ---------------------------------------------------------------------------

def _horary_config():
    from immanuel.const import chart, dignities
    from immanuel.settings import Config
    cfg = Config()
    cfg.house_system = chart.REGIOMONTANUS
    cfg.rulerships = dignities.TRADITIONAL_RULERSHIPS.copy()
    cfg.triplicities = dignities.LILLEAN_TRIPLICITIES.copy()
    cfg.terms = dignities.PTOLEMAIC_TERMS.copy()
    # Essential dignity alone: receptions are reported separately, not added
    # into the score (immanuel's default would score a planet in its fall +4
    # if it were in mutual reception).
    cfg.include_mutual_receptions = False
    # immanuel computes dignities only when every planet is present; the
    # outer planets are then left out of the report.
    cfg.objects = list(chart.PLANETS) + [chart.NORTH_NODE, chart.PART_OF_FORTUNE, chart.ASC, chart.MC]
    return cfg


def _ruler_of(sign_index: int) -> str:
    """Traditional domicile ruler of a sign (0 = Aries), from immanuel's table."""
    from immanuel.const import dignities, names
    return names.PLANETS[dignities.TRADITIONAL_RULERSHIPS[sign_index + 1]]


def _exaltation_sign(planet: str) -> int | None:
    from immanuel.const import chart, dignities
    pid = getattr(chart, planet.upper())
    for sign, ruler in dignities.EXALTATIONS.items():
        if ruler == pid:
            return sign - 1
    return None


def receptions(positions: dict[str, float], a: str, b: str) -> list[str]:
    """Reception between two planets by domicile or exaltation, from immanuel's tables."""
    def receives(host: str, guest: str) -> str | None:
        sign = _sign_index(positions[guest])
        if _ruler_of(sign) == host:
            return "domicile"
        if _exaltation_sign(host) == sign:
            return "exaltation"
        return None

    ab, ba = receives(a, b), receives(b, a)
    if ab and ba:
        return [f"{a} and {b} are in mutual reception ({b} in {a}'s {ab}, {a} in {b}'s {ba})."]
    out = []
    if ab:
        out.append(f"{a} receives {b} ({b} is in {a}'s {ab}).")
    if ba:
        out.append(f"{b} receives {a} ({a} is in {b}'s {ba}).")
    return out


@dataclass
class HoraryChart:
    jd: float
    lat: float
    lon: float
    tz: object
    asc: float
    cusps: list[float]
    positions: dict[str, float]
    speeds: dict[str, float]
    houses: dict[str, int]
    dignities: dict[str, dict]
    fortune: float
    node: float


ESSENTIAL = [
    ("ruler", "domicile", 5), ("exalted", "exaltation", 4), ("triplicity_ruler", "triplicity", 3),
    ("term_ruler", "term", 2), ("face_ruler", "face", 1),
]
DEBILITIES = [("detriment", "detriment", -5), ("fall", "fall", -4)]
PEREGRINE_SCORE = -5


def essential_dignity(flags) -> dict:
    """Lilly's essential dignity from immanuel's flags. Peregrine means none
    of the five essential dignities -- immanuel also spares a planet "in its
    rulership element", a modern minor dignity the horary tradition doesn't use."""
    held = [(label, score) for attr, label, score in ESSENTIAL if getattr(flags, attr, False)]
    held += [(label, score) for attr, label, score in DEBILITIES if getattr(flags, attr, False)]
    if not any(getattr(flags, attr, False) for attr, _, _ in ESSENTIAL):
        held.append(("peregrine", PEREGRINE_SCORE))
    return {"held": [label for label, _ in held], "score": sum(score for _, score in held)}


def cast(when: str, lat: float, lon: float) -> HoraryChart:
    """A horary chart via immanuel, with traditional settings."""
    from immanuel import charts

    natal = charts.Natal(charts.Subject(date_time=when, latitude=lat, longitude=lon), config=_horary_config())
    objs = {o.name: o for o in natal.objects.values()}
    cusps = [h.longitude.raw for h in sorted(natal.houses.values(), key=lambda h: h.number)]
    dignities = {p: essential_dignity(objs[p].dignities) for p in PLANETS}
    return HoraryChart(
        jd=natal.native.date_time.julian,
        lat=float(lat), lon=float(lon), tz=_zone(lat, lon),
        asc=objs["Asc"].longitude.raw % 360,
        cusps=cusps,
        positions={p: objs[p].longitude.raw % 360 for p in PLANETS},
        speeds={p: objs[p].speed for p in PLANETS},
        houses={p: objs[p].house.number for p in PLANETS},
        dignities=dignities,
        fortune=objs["Part of Fortune"].longitude.raw % 360,
        node=objs["North Node"].longitude.raw % 360,
    )


def house_of(lon: float, cusps: list[float]) -> int:
    for i in range(12):
        a, b = cusps[i] % 360, cusps[(i + 1) % 12] % 360
        if (lon - a) % 360 < (b - a) % 360:
            return i + 1
    return 12


def condition(c: HoraryChart, planet: str) -> dict:
    """A planet's essential and accidental state, in words."""
    from immanuel.const import calc, chart
    lon = c.positions[planet]
    speed = c.speeds[planet]
    house = c.houses[planet]
    mean = calc.MEAN_MOTIONS.get(getattr(chart, planet.upper()))
    notes = []
    if speed < 0:
        notes.append("retrograde")
    if mean and planet not in ("Sun",):
        notes.append("fast" if abs(speed) > mean else "slow")
    if planet != "Sun":
        from_sun = abs((lon - c.positions["Sun"] + 180) % 360 - 180)
        if from_sun <= CAZIMI_ORB:
            notes.append("cazimi (in the heart of the Sun: strengthened)")
        elif from_sun <= COMBUST_ORB:
            notes.append("combust (burned up by the Sun: weakened, hidden)")
        elif from_sun <= UNDER_BEAMS_ORB:
            notes.append("under the Sun's beams")
    place = "angular" if house in (1, 4, 7, 10) else "succedent" if house in (2, 5, 8, 11) else "cadent"
    d = c.dignities[planet]
    return {
        "position": _position(lon),
        "house": house,
        "house_place": place,
        "essential_dignity": d["held"] or ["none"],
        "dignity_score": d["score"],
        "condition": notes,
    }


def considerations(c: HoraryChart, eph: Ephemeris) -> list[dict]:
    """The traditional checks before judgment, each flagged with a reason."""
    out = []
    asc_deg = c.asc % 30
    if asc_deg < 3:
        out.append({"check": "early ascendant", "flag": True,
                    "why": f"The Ascendant is at {_position(c.asc)}: the matter is too new, or the question premature."})
    elif asc_deg >= 27:
        out.append({"check": "late ascendant", "flag": True,
                    "why": f"The Ascendant is at {_position(c.asc)}: the matter is already settled, or it's too late to change."})
    else:
        out.append({"check": "ascendant degree", "flag": False, "why": f"The Ascendant is at {_position(c.asc)}: fine."})

    moon = c.positions["Moon"]
    void = next((p for p in void_periods(c.jd - 3, c.jd + 1 / 1440) if p["start"] <= c.jd < p["end"]), None)
    if void:
        sign = SIGNS[_sign_index(moon)]
        exception = sign in ("Taurus", "Cancer", "Sagittarius", "Pisces")
        out.append({"check": "void-of-course Moon", "flag": True, "why": (
            f"The Moon is void of course until {_local(void['end'], c.tz)}: traditionally, nothing comes of the matter"
            + (f" -- though Lilly allows that she 'performs somewhat' in {sign}." if exception else ".")
        )})
    else:
        out.append({"check": "void-of-course Moon", "flag": False, "why": "The Moon is not void of course."})

    if 195 <= moon < 225:
        out.append({"check": "via combusta", "flag": True,
                    "why": "The Moon is in the Via Combusta (15° Libra to 15° Scorpio): an unsettled, unpredictable situation."})
    if moon % 30 >= 29:
        out.append({"check": "Moon in the last degree", "flag": True,
                    "why": "The Moon is in the last degree of her sign: events are already turning."})
    for h in (1, 7):
        if c.houses["Saturn"] == h:
            who = "the querent" if h == 1 else "the astrologer's judgment"
            out.append({"check": f"Saturn in the {'1st' if h == 1 else '7th'}", "flag": True,
                        "why": f"Saturn in the {'1st' if h == 1 else '7th'} house afflicts {who}: judge with caution."})

    hour = hour_at(c.jd, c.lat, c.lon, c.tz)
    asc_ruler = _ruler_of(_sign_index(c.asc))
    if hour:
        same = hour["ruler"] == asc_ruler
        asc_element = ELEMENT[_sign_index(c.asc) % 4]
        hour_signs = [i for i in range(12) if _ruler_of(i) == hour["ruler"]]
        same_element = any(ELEMENT[i % 4] == asc_element for i in hour_signs)
        agrees = same or same_element
        out.append({"check": "radicality (hour ruler)", "flag": not agrees, "why": (
            f"The hour belongs to {hour['ruler']}; the Ascendant ruler is {asc_ruler}. "
            + ("They agree: the chart is radical, fit to judge." if agrees else
               "They don't agree by planet or triplicity: by the strict rule the chart may not be radical.")
        )})
    return out


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

HOUSE_GUIDE = (
    "Houses: 1 querent, body, life | 2 money, possessions | 3 siblings, neighbours, messages, short trips | "
    "4 home, property, father, endings | 5 children, pregnancy, romance, fun | 6 illness, employees, pets | "
    "7 partner, spouse, any named other person, opponent | 8 debts, partner's money, death | "
    "9 long journeys, education, law, religion | 10 career, job, reputation, mother | 11 friends, hopes | "
    "12 hidden enemies, confinement, self-undoing."
)


def _setup(when, latitude, longitude, city, state, country):
    lat, lon, matched = _resolve_place(latitude, longitude, city, state, country, required=True)
    tz = _zone(lat, lon)
    if when:
        valid, err = validate_date_string(when)
        if not valid:
            raise ValueError(err)
        moment = when.replace("T", " ")
    else:
        moment = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    return lat, lon, matched, tz, moment


def _chart_summary(c: HoraryChart) -> dict:
    return {
        "ascendant": _position(c.asc),
        "ascendant_ruler": _ruler_of(_sign_index(c.asc)),
        "houses": [
            {"house": i + 1, "cusp": _position(cusp), "ruler": _ruler_of(_sign_index(cusp))}
            for i, cusp in enumerate(c.cusps)
        ],
        "part_of_fortune": {"position": _position(c.fortune), "house": house_of(c.fortune, c.cusps)},
        "north_node": _position(c.node),
    }


def cast_horary_chart(
    question: Annotated[str, Field(description="The question as the person asked it.")],
    when: Annotated[str | None, Field(description="When the question was asked, local 'YYYY-MM-DD HH:MM'. Omit for now.")] = None,
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    city: Annotated[str | None, Field(description="Where the astrologer received the question. Use instead of latitude/longitude.")] = None,
    state: str | None = None,
    country: str | None = None,
) -> str:
    """The chart of a horary question, cast the traditional way, with each
    planet's condition and the considerations before judgment.

    Use to show or discuss a horary chart. To answer the question itself
    ("will I get the job?"), call judge_question instead -- it includes this.
    """
    try:
        lat, lon, matched, tz, moment = _setup(when, latitude, longitude, city, state, country)
        c = cast(moment, lat, lon)
    except ValueError as e:
        return error_response("Invalid input", str(e))
    except RuntimeError as e:
        return error_response("Geocoding failed", str(e))
    except Exception as e:
        return error_response("Chart calculation failed", str(e))

    eph = ImmanuelEphemeris()
    result = {
        "question": question,
        "asked": moment,
        "settings": "Regiomontanus houses, traditional rulers, Lilly's triplicities, Ptolemy's terms",
        **_chart_summary(c),
        "planets": {p: condition(c, p) for p in PLANETS},
        "considerations": considerations(c, eph),
        "how_to_read": (
            "dignity_score is essential dignity only (domicile +5, exaltation +4, triplicity +3, term +2, face +1, "
            "detriment -5, fall -4, peregrine -5). Flagged considerations are cautions to state before judging."
        ),
        **_place_note(lat, lon, matched, tz),
    }
    return _dumps(result)


def judge_question(
    question: Annotated[str, Field(description="The question as the person asked it.")],
    quesited_house: Annotated[int, Field(description="House of the thing asked about (1-12); see the house guide in the tool description.", ge=1, le=12)],
    relative_to: Annotated[int, Field(description="Count quesited_house from this house (derived houses). Default 1. E.g. a partner's money: quesited_house=2, relative_to=7.", ge=1, le=12)] = 1,
    querent_house: Annotated[int, Field(description="House of the person asking. Default 1 (the asker). For a question on someone else's behalf, their house: e.g. 11 for a friend.", ge=1, le=12)] = 1,
    when: Annotated[str | None, Field(description="When the question was asked, local 'YYYY-MM-DD HH:MM'. Omit for now.")] = None,
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    city: Annotated[str | None, Field(description="Where the question was asked. Use instead of latitude/longitude.")] = None,
    state: str | None = None,
    country: str | None = None,
) -> str:
    """Judge a horary question: do the significators of the asker and of the
    thing asked about come together, and when?

    Returns a verdict with the testimony behind it, the traditional timing,
    the significators' condition, supporting testimony from the Moon and
    reception, and the considerations before judgment.
    """
    try:
        lat, lon, matched, tz, moment = _setup(when, latitude, longitude, city, state, country)
        c = cast(moment, lat, lon)
    except ValueError as e:
        return error_response("Invalid input", str(e))
    except RuntimeError as e:
        return error_response("Geocoding failed", str(e))
    except Exception as e:
        return error_response("Chart calculation failed", str(e))

    eph = ImmanuelEphemeris()
    querent_cusp = c.cusps[querent_house - 1]
    target_house = (relative_to - 1 + quesited_house - 1) % 12 + 1
    quesited_cusp = c.cusps[target_house - 1]
    a = _ruler_of(_sign_index(querent_cusp))
    b = _ruler_of(_sign_index(quesited_cusp))
    describe = lambda jd: f"on {_local(jd, tz)}"  # noqa: E731

    notes: list[str] = []
    if a == b:
        # One planet signifies both: the Moon, co-significator of the querent, stands in for the asker.
        notes.append(f"{a} rules both houses, so the Moon stands in for the querent.")
        a = "Moon" if b != "Moon" else a
    try:
        verdict = judge(eph, a, b, c.jd, describe)
    except Exception as e:
        return error_response("Judgment failed", str(e))

    supporting = list(notes)
    supporting += receptions(c.positions, a, b)
    if "Moon" not in (a, b):
        moon_end = _window_end(eph, c.jd, "Moon")
        moon_next = next_perfection(eph, "Moon", b, c.jd, moon_end)
        if moon_next:
            effect = {
                "square": "brings the matter, but with obstacles",
                "opposition": "brings it only with opposition, or with regret",
            }.get(moon_next.aspect, "supports the matter")
            supporting.append(
                f"The Moon (co-significator of the querent) applies to {b} by {moon_next.aspect} "
                f"{describe(moon_next.jd)}: {effect}."
            )
        else:
            supporting.append(f"The Moon makes no aspect to {b} before leaving her sign.")

    result = {
        "question": question,
        "asked": moment,
        "significators": {
            "querent": {"planet": a, "rules_house": querent_house, **condition(c, a)},
            "quesited": {"planet": b, "rules_house": target_house, **condition(c, b)},
        },
        "verdict": verdict.verdict,
        "summary": verdict.summary,
        "testimony": verdict.testimonies,
        "supporting": supporting,
        "considerations": considerations(c, eph),
        **_place_note(lat, lon, matched, tz),
    }
    if verdict.perfection:
        result["perfects_at"] = _local(verdict.perfection.jd, tz)
        result["traditional_timing"] = traditional_timing(eph, verdict.perfection, c.jd, c.houses)
    result["how_to_read"] = (
        "Lead with summary and cite testimony. perfects_at is when the aspect is exact in the sky; "
        "traditional_timing is the symbolic reading (degrees to perfection counted in days, weeks or months). "
        "Mention any flagged considerations. Don't re-judge the chart or add calculations of your own."
    )
    return _dumps(result)


def register(mcp: MCPServer):
    mcp.add_tool(
        judge_question,
        name="judge_question",
        description=(
            "Answer a horary question -- 'will I get the job?', 'will he call?', 'will the sale go through?' -- "
            "from the chart of the moment it is asked. Choose quesited_house from the house guide; use "
            "relative_to for derived houses and querent_house when asking for someone else. Returns a verdict "
            "(perfects / perfects by translation / perfects by collection / prohibited / refranation / no "
            "perfection) with its testimony, when it happens, and the considerations before judgment. Report "
            "the verdict and testimony as returned; never judge the chart or compute aspects yourself. "
            + HOUSE_GUIDE
        ),
    )
    mcp.add_tool(
        cast_horary_chart,
        name="cast_horary_chart",
        description=(
            "Cast the chart of a horary question the traditional way (Regiomontanus, traditional rulers): each "
            "planet's essential dignity score, house, and condition (retrograde, fast/slow, combust, cazimi, "
            "under the beams), the house rulers, the Part of Fortune, and the considerations before judgment "
            "(early/late Ascendant, void Moon, Via Combusta, Saturn in the 1st/7th, hour ruler). Use to show or "
            "discuss the chart; to answer the question, use judge_question. Report values as returned; never "
            "compute them yourself."
        ),
    )
