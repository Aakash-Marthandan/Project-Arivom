"""Weekly editorial QA sample (D-026).

Prints a random sample of currently displayed news content — Arivom
titles beside the outlets' originals, classifications, and any checked
summaries — for a HUMAN read. The editorial standard stays a standard
only if someone looks: this is that look. Detection only; fixing a bad
title or class happens through the pipeline, never by hand-editing rows.
"""

from __future__ import annotations

from .common import Db

SAMPLE = 20


def main() -> None:
    db = Db.connect()

    rows = db.conn.execute(
        """
        SELECT outlet, lang, civic_class, civic_priority,
               headline_orig, title_clean_en, title_clean_ta
        FROM news_items
        WHERE (civic_class IS NULL OR civic_class <> 'soft')
          AND published_at > now() - interval '7 days'
        ORDER BY random()
        LIMIT %s
        """,
        (SAMPLE,),
    ).fetchall()

    print(f"=== Editorial QA sample — {len(rows)} displayed items ===\n")
    for outlet, lang, cls, priority, headline, ten, tta in rows:
        print(f"[{outlet} · {lang} · class={cls or 'unclassified'}"
              f" · priority={priority or '-'}]")
        print(f"  original : {headline[:110]}")
        if ten:
            print(f"  arivom en: {ten[:110]}")
        if tta:
            print(f"  arivom ta: {tta[:110]}")
        print()

    clusters = db.conn.execute(
        """
        SELECT id, title_en, title_ta, summary_en, sources_disagree
        FROM news_clusters
        WHERE summary_en IS NOT NULL
        ORDER BY random() LIMIT 5
        """
    ).fetchall()
    if clusters:
        print(f"=== Checked summaries — {len(clusters)} sampled clusters ===\n")
        for cid, ten, tta, summary, disagree in clusters:
            print(f"[cluster {cid}{' · sources differ' if disagree else ''}]")
            print(f"  en: {ten}")
            print(f"  ta: {tta}")
            print(f"  summary: {(summary or '')[:220]}")
            print()

    unclassified = db.conn.execute(
        "SELECT count(*) FROM news_items WHERE civic_class IS NULL "
        "AND published_at > now() - interval '7 days'"
    ).fetchone()
    assert unclassified is not None
    print(f"unclassified items in window (await pipeline/key): {unclassified[0]}")
    print("Read the sample above. A bad title or class is pipeline feedback, "
          "not a row edit (D-026).")


if __name__ == "__main__":
    main()
