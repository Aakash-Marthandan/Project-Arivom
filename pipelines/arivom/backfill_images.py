"""Fill in outlet images for items the analysis pipeline has not reached (D-044).

Story cards carry the outlet's own og:image, hotlinked and never copied
(D-024). Until now that image only arrived as a side effect of stage 1
extraction, so any item awaiting analysis rendered without one — which is most
of the feed most of the time, and it makes a full feed look empty.

Fetching an og:image needs no model and costs nothing, so it does not belong
behind the LLM budget. This walks recent displayable items, reads the meta tag
the outlet already publishes for social sharing, and records the URL.

Policy, unchanged from D-024: we store the outlet's URL and hotlink it. The
image is never copied, rehosted or altered, and an item without one simply
renders without one.
"""

from __future__ import annotations

import argparse

from .articles import fetch_excerpt
from .common import Db, article_session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=400,
                        help="items to attempt this run")
    parser.add_argument("--days", type=int, default=7,
                        help="how far back to look")
    args = parser.parse_args()

    db = Db.connect()
    session = article_session()

    rows = db.conn.execute(
        """
        SELECT id, url FROM news_items
        WHERE image_url IS NULL
          AND civic_class IS DISTINCT FROM 'soft'
          AND published_at > now() - make_interval(days => %s)
        ORDER BY published_at DESC
        LIMIT %s
        """,
        (args.days, args.limit),
    ).fetchall()

    found = missing = failed = 0
    for item_id, url in rows:
        excerpt, status, image = fetch_excerpt(session, url)
        if status != "fetched":
            failed += 1
            continue
        if not image:
            missing += 1
            continue
        db.conn.execute(
            "UPDATE news_items SET image_url = COALESCE(image_url, %s) WHERE id = %s",
            (image, item_id),
        )
        found += 1
        if found % 25 == 0:
            db.conn.commit()
    db.conn.commit()

    print("\n=== Image backfill ===")
    print(f"  attempted     : {len(rows)}")
    print(f"  images found  : {found}")
    print(f"  none published: {missing}")
    print(f"  fetch failed  : {failed}")

    total, with_image = db.conn.execute(
        """
        SELECT count(*), count(image_url) FROM news_items
        WHERE civic_class IS DISTINCT FROM 'soft'
          AND published_at > now() - make_interval(days => %s)
        """,
        (args.days,),
    ).fetchone()
    pct = (100 * with_image / total) if total else 0
    print(f"  coverage      : {with_image}/{total} displayable items ({pct:.0f}%)")


if __name__ == "__main__":
    main()
