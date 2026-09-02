# Data source probe log

Empirical access notes for sources we plan to ground the news against. Every
line records what happened when the endpoint was *requested*, not what a
landing page implied. Re-probe before planning work against any of it.

Probed 2026-09-01 from India egress.

## The distinction this file exists to record

**Reachable is not accessible.** Every endpoint below returned HTTP 200 on its
landing page; several then refused at the data layer. A survey that stops at
the landing page will plan work that cannot be built.

## Verified accessible

### HMIS (health, district level) — UNBLOCKED

The M12 blocker is gone, and the dashboard has a scriptable file API, found the
same way D-028 found UDISE's: by watching what the page itself calls.

    GET https://hmis.mohfw.gov.in/getFiles?fpath=<base64 of path>

`fpath` is base64 of the path below `BASEDIR/`. Returns a JSON array of
`{path, name, isdirectory, fileSize, lastModifiedDate}`. The walk:

    Standard Reports
      └ 9~F.1. Performance of Key HMIS Indicators(upto District Level)
          └ 2019-2020            (years run 2008-2009 .. 2019-2020)
              └ MonthUpToMarch   (also June, September, December)
                  └ Tamil Nadu
                      ALL.xls (2.18 MB), Maternal Health.xls, Child Health.xls
                      plus PDF equivalents

Caveat that changes the plan: **this report family stops at 2019-2020.** It is
an annual and quarterly archive, not the monthly current data M12 assumed.
Newer figures may sit under a different report family ("Real time Reports");
that needs its own probe before we promise freshness anywhere in the product.

### PRS Legislative Research

`prsindia.org/billtrack` answers 200. Non-partisan and well cited. Candidate
source for the legislative record.

## Blocked at the data layer

### RBI state finances — CAPTCHA

The Handbook of Statistics on Indian States publishes exactly what we need:
Table 176 state-wise composition of outstanding liabilities, 164 gross fiscal
deficit, 165 revenue deficit, 170 interest payments — all offered as XLSX.

Direct download returns an HTML page containing a captcha, and
`rbidocs.rbi.org.in` then refuses further connections. We do not work around
bot detection, so this needs a different route: a mirror (the D-004 precedent,
where LGD came via a data.gov.in mirror because the portal had a captcha), or
the printed figures entered through the curated cited-seed path.

This is the highest-value gap we have. Our own corpus carries claims of a
10 lakh crore rupee state debt and 28,000 crore borrowed in 100 days, and we
can check neither.

### Open Budgets India — 403

Republishes RBI state finances and would have been the obvious mirror. Both the
organisation page and the CKAN API return 403 to us.

### TN Finance Department — JS shell

`tnbudget.tn.gov.in` redirects to `financedept.tn.gov.in`, which returns 91
bytes: a client-rendered shell. Enumerating budget documents needs a
browser-driven fetch.

### IMD weather — IP whitelisting

`city.imd.gov.in/api/cityweather.php` answers **401, "IP needs to be
whitelisted"**. The API exists; access is an administrative request to IMD, not
an engineering problem. Worth making, since public safety is the class D-037
ranks first and weather is the one kind of grounding that matters within the
hour rather than the year.

### TN Water Resources / India-WRIS — no connection

`wrd.tn.gov.in` and `indiawris.gov.in` both failed to connect. Possibly the
TLS-fingerprint issue already recorded for ECI and MyNeta (D-006, D-019), which
we solve by shelling out to curl; worth that retry. The Amaravathi release story
shows the demand for reservoir data.

### Consumer Affairs price monitoring — no connection

Did not connect. Household prices are a D-037 ranked class; worth a retry.

## Reachable, not yet probed at the data layer

`tn.gov.in`, `elections.tn.gov.in`, `tnsec.tn.gov.in`, `assembly.tn.gov.in`,
`njdg.ecourts.gov.in`, `ncrb.gov.in`, `cea.nic.in` and `mospi.gov.in` all
answered 200 on their landing pages. None has had its data layer probed. Treat
the 200 as permission to investigate, not as availability — that is the whole
lesson of this log.
