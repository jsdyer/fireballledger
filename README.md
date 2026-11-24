# Fireball Ledger

Explore the NASA/JPL CNEOS catalogue of reported fireballs, with a world map, date and energy filters, yearly counts, original source values, exports and retained catalogue comparisons. The public page works from saved data. It makes no browser requests to the JPL API and needs no API key.

<!-- coolcode:guide -->
Start with **At least 1 kt**, then select a map point or an event time in the table to inspect its source values. Change the dates or energy threshold freely; the presets are optional. Events without reported coordinates remain in the ledger but are omitted from the map. **Save capture JSON** keeps the entire selected capture and its changes; **Export filtered CSV** saves only the current results. The capture date is when the catalogue was retrieved, not when the fireball occurred. The first capture is a baseline; later weekly captures show revisions to same-time records and records newly appearing or no longer present. A changed event time can appear as both an addition and an absence because the source provides no immutable event identifier.
<!-- /coolcode:guide -->

## What is here

- Complete unfiltered response captured on 2026-11-23: **1,074 reported events**, of which **888 have coordinates**, with event dates from 1988-04-15 through 2026-10-04. The live counts are derived from the selected capture, not these initial numbers.
- Date search, date range, minimum impact energy, missing-location and geographic filters. A North America window means 5–85° N and 170–50° W, not a country boundary.
- Equirectangular world map with clickable event points. The table provides the same accessible event selection. Circle radius uses a bounded log scale; the legend uses energy bands, not physical blast size.
- Yearly counts, detailed source fields, pagination, JSON and CSV exports.
- Weekly collection with API-version, shape, numerical, count and shrinkage checks. Failures do not replace the last successful deployment.
- A capture selector and changes stored with each capture. Up to 52 captures retained by default, independently of UI filters. Git history may preserve earlier committed files but is not an archival guarantee.

## Meaning and limits

The [official CNEOS catalogue](https://cneos.jpl.nasa.gov/fireballs/) describes reports from U.S. Government sensors. It is not a complete record of every fireball, is not updated in real time, and CNEOS does not independently reanalyse the observations. Source values can be revised. Counts cannot establish changes in the true global meteor rate.

Peak brightness times are shown in UTC. Coordinates and altitude describe the peak-brightness event, not a ground impact or meteorite recovery site. Altitude is above the reference geoid. Radiated energy is in units of **10¹⁰ joules**; calculated impact energy is in **kilotons of TNT** and is an approximate inferred value. Null values stay missing. No missing location is placed at 0°, 0°.

Matching uses the source `date` field because the API has no immutable identifier. A record with the same date and different values is a field revision. An unmatched date is labelled newly appearing or no longer present, never proof that a physical event just occurred or disappeared. Date corrections can produce one record in each of those categories. Comparisons are withheld when collection parameters change. Changing the UI filters does not affect stored comparisons.

## Sources and API use

- [Fireball API v1.2 documentation](https://ssd-api.jpl.nasa.gov/doc/fireball.html)
- [SSD API fair-use policy](https://ssd-api.jpl.nasa.gov/doc/)
- [CNEOS fireball catalogue](https://cneos.jpl.nasa.gov/fireballs/)
- [Natural Earth public-domain land geometry](https://www.naturalearthdata.com/about/terms-of-use/) from the [maintainer's 1:110m data](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_land.geojson).

The collector makes **one serial request** per refresh, sends an application-specific User-Agent with a contact, validates the API version and caches results. It does not loop or retry after a failure. No JPL API is embedded in the website. This design follows the API's restriction on browser embedding and minimizes redundant requests. Weekly collection is adequate for this delayed catalogue; avoid high-frequency polling. No NASA/JPL logos or endorsement claims are used.

The map's downloaded geometry is rounded to three decimal places and contains no third-party map service requests. Its original source and license are recorded in `web/data/PROVENANCE.md`. JPL source values retain their attribution; no ownership or exclusive license over them is claimed.

## Expand or customize

Edit **`web/config.json`**:

| Setting | What it changes |
| --- | --- |
| `apiParameters` | Official JPL query fields. Default `{"vel-comp":"true"}` requests the full catalogue plus entry-velocity components. Optional `date-min`, `date-max`, `impact-e-min`, `req-loc`, `limit`, etc. must use the documented API names and units. |
| `acceptedApiVersions` | Accepted source versions. Change only after reviewing JPL's current documentation and the parser. |
| `retainCaptures` | 2–104 captures; default 52 weekly captures. |
| `minimumRecords` / `maximumRecords` | Collector safeguards, not a fixed starter list size. Default 1–10,000. A legitimate empty result is rejected to avoid replacing a useful published catalogue; broaden an overly narrow source query. |
| `maximumDropFraction` | Reject unexpected shrinkage with the same query, default 25%. Investigate any failure before relaxing it. |
| `userAgent` | Keep the product name/version and a correct maintainer contact. |
| `presets` | Additional convenient browser filters; all data remains searchable. |
| `pageSize` | Rows per page, clamped to 5–100 in the UI. |

For example, add a fifth preset without changing code:

```json
{"label":"Southern sky, 0.5 kt+","minEnergy":0.5,"region":"south"}
```

Accepted preset `region` values are `all`, `north`, `south`, `north-america`; `location` values are `all`, `known`, `missing`. `label` is displayed as text. Every preset starts with reset date/search controls. A configuration-expansion test covers adding a new preset.

To collect a narrower source window, add `"date-min":"2000-01-01"` inside `apiParameters`. Old captures remain selectable with their original scope. The next capture starts a new comparison baseline; the UI does not compare differently filtered source responses. Remove that field to restore the full catalogue.

**Editing and pushing source/config rebuilds the app but does not automatically fetch JPL.** After changing collection settings, run **Fireball Ledger · Capture, check and publish** in GitHub Actions with **refresh** checked. A weekly Monday 10:23 UTC schedule also collects and publishes; GitHub schedules may be delayed or disabled after repository inactivity. UI-only changes need only a normal push. This makes code publication and data retrieval explicit and avoids redundant source requests.

To do it locally:

```sh
python3 scripts/refresh.py
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -v
python3 scripts/build.py
```

`--input /path/to/official-response.json` validates an already-downloaded official API response without another API request. The standard build is offline. Workflow collection changes are committed only after tests and browser checks pass; failed collection/checks stop publication.

## Privacy and deployment

Filters run in browser memory and no searches are submitted to JPL. Data and map files are served from the same site. Downloads are generated locally. The shared CoolCode page counter records aggregate tool opens; it does not receive these filter values. There is no local-storage retention or private upload.

App source is under `web/`, collector/build under `scripts/`, application and collector tests under `tests/`. `dist/` is generated and ignored. GitHub Pages publishes successful main-branch builds; pull requests never deploy. No custom domain or Cloudflare Worker is needed for this app.

<!-- schedule-reliability -->
## Schedule reliability

Public GitHub repositories can have scheduled workflows disabled after 60 days of inactivity. A separate weekly [schedule guard](.github/workflows/schedule-guard.yml) calls GitHub's enable-workflow API for an explicit list of refresh workflows and itself. It can restore workflows disabled for inactivity, preserves manually disabled workflows, and runs independently of collection failures.

This is an interim mitigation, not a scheduling guarantee: GitHub does not document active-workflow renewal as a permanent exemption, and scheduled runs can be delayed or dropped. A scheduler on our own Linux server is the planned independent trigger. The guard does not collect data, create dummy commits, or change source/check timestamps; successful collection and published data freshness still need monitoring.
<!-- /schedule-reliability -->
