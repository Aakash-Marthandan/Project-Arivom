"""Import constituency and district geometries into localities.geom (M2).

Sources:
- AC polygons: DataMeet's ECI-derived AC shapefile, keyed by numeric AC_NO
  (same source and vintage as the AC→PC linkage from M1).
- PC polygons: derived as the union of member-AC polygons, so point
  resolution can never disagree between an AC and its PC.
- District polygons: geoBoundaries gbOpen IND ADM2 (2021 — includes the
  post-2019 TN district splits), ODbL.

After geometry lands, ACs whose current district was withheld in M1
(DECISIONS.md D-009) are assigned one spatially: the district polygon with
the majority area overlap, recorded as a `facts` row with
extraction_method='spatial' and the overlap share as confidence. Existing
district assignments are audited the same way but never overwritten.

Every geometry gets a per-locality provenance fact (key='geometry'), which
also surfaces the geometry sources on /freshness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import shapefile  # pyshp

from .common import Db, fail, http_session, norm_name, now_utc

DATAMEET_BASE = (
    "https://raw.githubusercontent.com/datameet/maps/master/assembly-constituencies/India_AC"
)
GEOBOUNDARIES_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM2/"
    "geoBoundaries-IND-ADM2.geojson"
)
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"

# Loose Tamil Nadu bounding box (with padding for coastal islands).
TN_LON = (75.8, 80.8)
TN_LAT = (7.8, 13.8)

# Narrow, documented adjudications (DECISIONS.md D-011): ACs whose stored
# district traces only to a stale Wikidata P131 claim and where the 2021
# spatial source contradicts it at ≥97% overlap. Never a blanket rule —
# the same audit shows cases where the spatial source is the stale one
# (e.g. Chennai's 2018 expansion is missing from geoBoundaries).
SPATIAL_OVERRIDES = {"160"}  # Sirkazhi → Mayiladuthurai (2020 split)


def _cached_download(session: Any, url: str, filename: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / filename
    if not path.exists():
        print(f"  downloading {filename}…")
        resp = session.get(url, timeout=600)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


def load_tn_ac_shapes(session: Any) -> dict[int, dict[str, Any]]:
    """AC_NO → GeoJSON geometry for Tamil Nadu from the DataMeet shapefile."""
    for ext in ("shp", "shx", "dbf"):
        _cached_download(session, f"{DATAMEET_BASE}.{ext}", f"India_AC.{ext}")
    reader = shapefile.Reader(str(CACHE_DIR / "India_AC"), encoding="latin-1")
    shapes: dict[int, dict[str, Any]] = {}
    for rec in reader.iterShapeRecords():
        attrs = rec.record.as_dict()
        if (attrs.get("ST_NAME") or "").strip().upper() != "TAMIL NADU":
            continue
        ac_no = int(attrs["AC_NO"])
        shapes[ac_no] = rec.shape.__geo_interface__
    if set(shapes) != set(range(1, 235)):
        fail(f"DataMeet shapefile: expected ACs 1..234 for TN, got {len(shapes)}")
    return shapes


def load_district_shapes(session: Any, district_norms: set[str]) -> dict[str, dict[str, Any]]:
    """Normalized district name → GeoJSON geometry from geoBoundaries ADM2.

    The file is all-India with no state attribute; we take features whose
    name matches one of OUR 38 districts and verify full coverage. A small
    alias map covers geoBoundaries' spelling drift.
    """
    path = _cached_download(session, GEOBOUNDARIES_URL, "geoBoundaries-IND-ADM2.geojson")
    # geoBoundaries spelling → our LGD-derived district name (normalized).
    aliases = {
        "chengalputtu": "chengalpattu",  # geoBoundaries typo
        "nilgiris": "the nilgiris",
        "tuticorin": "thoothukkudi",
        "thoothukudi": "thoothukkudi",
        "villupuram": "viluppuram",
        "virudunagar": "virudhunagar",
        "kanyakumari": "kanniyakumari",
    }
    result: dict[str, dict[str, Any]] = {}
    data = json.loads(path.read_text())
    for feature in data["features"]:
        raw = (feature["properties"].get("shapeName") or "").strip()
        key = norm_name(raw.removesuffix(" district").removesuffix(" District"))
        key = aliases.get(key, key)
        if key in district_norms:
            # Same-named districts exist in other states (e.g. Bilaspur);
            # keep only shapes that actually sit inside the TN bbox.
            lons, lats = _geometry_bounds(feature["geometry"])
            if not (
                TN_LON[0] <= lons[0] and lons[1] <= TN_LON[1]
                and TN_LAT[0] <= lats[0] and lats[1] <= TN_LAT[1]
            ):
                continue
            if key in result:
                fail(f"geoBoundaries: two TN-bbox features match district '{raw}'")
            result[key] = feature["geometry"]
    missing = district_norms - set(result)
    if missing:
        fail(f"geoBoundaries: no geometry for districts: {sorted(missing)}")
    return result


def _geometry_bounds(geom: dict[str, Any]) -> tuple[tuple[float, float], tuple[float, float]]:
    lons: list[float] = []
    lats: list[float] = []

    def walk(coords: Any) -> None:
        if isinstance(coords[0], (int, float)):
            lons.append(coords[0])
            lats.append(coords[1])
        else:
            for c in coords:
                walk(c)

    walk(geom["coordinates"])
    return (min(lons), max(lons)), (min(lats), max(lats))


def main() -> None:
    session = http_session()
    db = Db.connect()
    retrieved_at = now_utc()

    datameet_source = db.ensure_source(
        name="DataMeet India AC boundaries (ECI-derived)",
        url="https://github.com/datameet/maps",
        publisher="DataMeet community",
        license="CC BY 2.5 IN",
        access_mode="bulk",
        notes=(
            "Assembly-constituency attribute table scraped from ECI delimitation data. "
            "Authority for AC→PC linkage (numeric), AC reservation, and AC polygons; "
            "district names are delimitation-era (pre-2019 splits)."
        ),
    )
    geoboundaries_source = db.ensure_source(
        name="geoBoundaries gbOpen India ADM2 (districts, 2021)",
        url="https://www.geoboundaries.org/",
        publisher="William & Mary geoLab",
        license="ODbL 1.0",
        access_mode="bulk",
        notes=(
            "Current district polygons (includes post-2019 TN splits). Used for the "
            "district browse geometry and for spatial assignment of AC districts "
            "withheld in M1 (D-009)."
        ),
    )

    # --- AC polygons ----------------------------------------------------------
    print("Loading DataMeet AC shapes…")
    ac_shapes = load_tn_ac_shapes(session)
    ac_rows = db.conn.execute(
        "SELECT id, eci_code FROM localities WHERE level = 'ac'"
    ).fetchall()
    if len(ac_rows) != 234:
        fail("run import-constituencies before import-geometries")

    for loc_id, eci_code in ac_rows:
        geom = ac_shapes[int(eci_code)]
        db.conn.execute(
            """
            UPDATE localities
            SET geom = ST_Multi(ST_CollectionExtract(
                  ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 3))
            WHERE id = %s
            """,
            (json.dumps(geom), loc_id),
        )
        db.upsert_fact(
            subject_type="locality",
            subject_id=loc_id,
            key="geometry",
            value={"kind": "polygon", "vintage": "2008 delimitation"},
            source_id=datameet_source,
            retrieved_at=retrieved_at,
            extraction_method="bulk",
            confidence=1.0,
        )

    # --- PC polygons: union of member ACs -------------------------------------
    print("Deriving PC polygons from member ACs…")
    db.conn.execute(
        """
        UPDATE localities pc
        SET geom = sub.geom
        FROM (
          SELECT parent_id, ST_Multi(ST_Union(geom)) AS geom
          FROM localities
          WHERE level = 'ac' AND geom IS NOT NULL
          GROUP BY parent_id
        ) sub
        WHERE pc.id = sub.parent_id AND pc.level = 'pc'
        """
    )
    pc_rows = db.conn.execute(
        "SELECT id FROM localities WHERE level = 'pc' AND geom IS NOT NULL"
    ).fetchall()
    for (pc_id,) in pc_rows:
        db.upsert_fact(
            subject_type="locality",
            subject_id=pc_id,
            key="geometry",
            value={"kind": "polygon", "derived": "union of member assembly constituencies"},
            source_id=datameet_source,
            retrieved_at=retrieved_at,
            extraction_method="spatial",
            confidence=1.0,
        )

    # --- District polygons -----------------------------------------------------
    print("Loading geoBoundaries district shapes…")
    district_rows = db.conn.execute(
        "SELECT id, name_en FROM localities WHERE level = 'district'"
    ).fetchall()
    district_norms = {norm_name(name): loc_id for loc_id, name in district_rows}
    district_shapes = load_district_shapes(session, set(district_norms))
    for key, geom in district_shapes.items():
        loc_id = district_norms[key]
        db.conn.execute(
            """
            UPDATE localities
            SET geom = ST_Multi(ST_CollectionExtract(
                  ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 3))
            WHERE id = %s
            """,
            (json.dumps(geom), loc_id),
        )
        db.upsert_fact(
            subject_type="locality",
            subject_id=loc_id,
            key="geometry",
            value={"kind": "polygon", "vintage": "2021"},
            source_id=geoboundaries_source,
            retrieved_at=retrieved_at,
            extraction_method="bulk",
            confidence=1.0,
        )

    # --- Validation -------------------------------------------------------------
    bad = db.conn.execute(
        """
        SELECT level, eci_code, name_en FROM localities
        WHERE geom IS NOT NULL AND NOT ST_IsValid(geom)
        """
    ).fetchall()
    if bad:
        fail(f"invalid geometries after MakeValid: {bad}")
    coverage = db.conn.execute(
        """
        SELECT level, count(*) FILTER (WHERE geom IS NOT NULL), count(*)
        FROM localities WHERE level IN ('ac','pc','district')
        GROUP BY level ORDER BY level
        """
    ).fetchall()
    for level, with_geom, total in coverage:
        if with_geom != total:
            fail(f"{level}: only {with_geom}/{total} rows have geometry")

    bbox = db.conn.execute(
        """
        SELECT min(ST_XMin(geom)), max(ST_XMax(geom)),
               min(ST_YMin(geom)), max(ST_YMax(geom))
        FROM localities WHERE level = 'ac'
        """
    ).fetchone()
    assert bbox is not None
    bbox_ok = (
        TN_LON[0] < bbox[0] and bbox[1] < TN_LON[1]
        and TN_LAT[0] < bbox[2] and bbox[3] < TN_LAT[1]
    )
    if not bbox_ok:
        fail(f"AC bbox outside Tamil Nadu bounds: {bbox}")

    # --- District assignment: audit all ACs, fill the withheld ones -------------
    print("Auditing AC↔district by majority polygon overlap…")
    overlaps = db.conn.execute(
        """
        SELECT ac.id, ac.eci_code, ac.name_en, ac.district_id,
               d.id AS spatial_district_id, d.name_en AS spatial_district,
               ST_Area(ST_Intersection(ac.geom, d.geom)) / NULLIF(ST_Area(ac.geom), 0)
                 AS share
        FROM localities ac
        JOIN LATERAL (
          SELECT d.id, d.name_en, d.geom
          FROM localities d
          WHERE d.level = 'district' AND d.geom && ac.geom
          ORDER BY ST_Area(ST_Intersection(ac.geom, d.geom)) DESC
          LIMIT 1
        ) d ON true
        WHERE ac.level = 'ac'
        """
    ).fetchall()

    filled = 0
    overridden = 0
    mismatches = []
    for ac_id, eci_code, name_en, district_id, sp_id, sp_name, share in overlaps:
        share = float(share or 0)
        if district_id is not None and eci_code in SPATIAL_OVERRIDES:
            if sp_id != district_id and share >= 0.97:
                db.conn.execute(
                    "UPDATE localities SET district_id = %s WHERE id = %s", (sp_id, ac_id)
                )
                db.upsert_fact(
                    subject_type="locality",
                    subject_id=ac_id,
                    key="district",
                    value={
                        "district": sp_name,
                        "method": "spatial adjudication of stale source (D-011)",
                        "overlap_share": round(share, 4),
                    },
                    source_id=geoboundaries_source,
                    retrieved_at=retrieved_at,
                    extraction_method="spatial",
                    confidence=round(share, 4),
                )
                overridden += 1
                print(f"  OVERRIDE (D-011): AC {eci_code} {name_en} → {sp_name} ({share:.1%})")
            continue
        if district_id is None:
            if share < 0.5:
                fail(f"AC {eci_code} {name_en}: best district overlap only {share:.0%}")
            db.conn.execute(
                "UPDATE localities SET district_id = %s WHERE id = %s", (sp_id, ac_id)
            )
            db.upsert_fact(
                subject_type="locality",
                subject_id=ac_id,
                key="district",
                value={
                    "district": sp_name,
                    "method": "majority polygon overlap (D-009 resolution)",
                    "overlap_share": round(share, 4),
                },
                source_id=geoboundaries_source,
                retrieved_at=retrieved_at,
                extraction_method="spatial",
                confidence=round(share, 4),
            )
            filled += 1
            print(f"  AC {eci_code} {name_en} → {sp_name} ({share:.1%} overlap)")
        elif sp_id != district_id and share > 0.55:
            mismatches.append(f"AC {eci_code} {name_en}: stored ≠ spatial {sp_name} ({share:.0%})")

    db.conn.commit()

    print("\n=== Geometry import report ===")
    for level, with_geom, total in coverage:
        print(f"{level}: {with_geom}/{total} geometries")
    print(f"withheld districts filled spatially: {filled}")
    print(f"stale districts adjudicated (D-011): {overridden}")
    if mismatches:
        print("AUDIT — stored district differs from spatial majority (not overwritten):")
        for m in mismatches:
            print(f"  {m}")


if __name__ == "__main__":
    main()
