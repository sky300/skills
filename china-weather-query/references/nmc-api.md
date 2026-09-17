# nmc.cn Public JSON Endpoints

Reference for the endpoints under `https://www.nmc.cn/rest/` used by
`scripts/weather.py`. The China Meteorological Administration (中国气象局)
publishes these for its own forecast site; there is no official developer
documentation and no API key.

All measurements below were taken against the live service in September 2026
with a desktop browser `User-Agent`. Send one — requests without it may be
refused.

## 1. Province list

```
GET https://www.nmc.cn/rest/province/all
```

Returns 34 entries:

```json
[{"code": "ABJ", "name": "北京市", "url": "/publish/forecast/ABJ.html"}]
```

| Field | Meaning |
|:---|:---|
| `code` | Province code (`ABJ` Beijing, `AJS` Jiangsu, `AGD` Guangdong, ...) |
| `name` | Full province name |
| `url` | Forecast page for the province |

## 2. City list within a province

```
GET https://www.nmc.cn/rest/province/{province_code}
```

Example: `/rest/province/AJS` returns 70 Jiangsu stations:

```json
[{"code": "AhpEU", "province": "广东省", "city": "深圳",
  "url": "/publish/forecast/AJS/lianyungang.html"}]
```

| Field | Meaning |
|:---|:---|
| `code` | Station code — a short alphanumeric token, **not** the 5-digit WMO number |
| `city` | Display name |
| `province` | Owning province |
| `url` | Forecast page for the city |

Two notes that matter in practice:

- **`code` is not a WMO station id.** `54511` (the observation id for Beijing)
  returns an empty `data` body. Always use the `code` from this endpoint.
- **Duplicates exist.** The sweep yields 2529 entries but only 2528 distinct
  `(province, city)` pairs — 江苏省淮安 is listed twice, as `DXKse` and `wVmjo`.
  Only one of those codes is referenced by the city's own forecast page; the
  other returns plausible-looking but different numbers. `weather.py` resolves
  this at index-build time via `dedupe_stations()`.

## 3. Weather — observation, forecast, air quality, warnings

```
GET https://www.nmc.cn/rest/weather?stationid={station_code}
```

The single endpoint behind every displayed value. Response envelope:

```json
{"msg": "success", "code": 0, "data": {"real": {}, "predict": {}, "air": {},
 "tempchart": [], "passedchart": [], "climate": {}, "radar": {}}}
```

An unknown `stationid` returns `code: 0` and `msg: "success"` with an **empty**
`data`, so check `data` for content rather than trusting the status.

### 3.1 `real` — current observation

```json
{
  "station": {"code": "AhpEU", "province": "广东省", "city": "深圳", "url": "..."},
  "publish_time": "2026-09-16 20:30",
  "weather": {"temperature": 22.8, "temperatureDiff": 1.5, "airpressure": 9999.0,
              "humidity": 71.0, "rain": 0.0, "rcomfort": 67, "icomfort": 0,
              "info": "多云", "img": "1", "feelst": 25.1},
  "wind": {"direct": "西南风", "degree": 200.0, "power": "微风", "speed": 0.8},
  "warn": {"alert": "9999", "signaltype": "9999", "signallevel": "9999", ...},
  "sunriseSunset": {"sunrise": "2026-09-16 05:46", "sunset": "2026-09-16 18:09"}
}
```

| Field | Notes |
|:---|:---|
| `weather.temperature` | °C |
| `weather.feelst` | Apparent temperature, °C |
| `weather.humidity` | Relative humidity, % |
| `weather.rain` | Precipitation, mm |
| `weather.info` | Condition text |
| `weather.img` | Condition code — see the table below |
| `weather.temperatureDiff` | Change vs the previous hour |
| `weather.comfort` (`rcomfort`/`icomfort`) | Comfort index; undocumented, not surfaced |
| `wind.direct` / `power` / `speed` | Direction text / Beaufort band / m/s |
| `publish_time` | Observation timestamp |

`airpressure` is frequently the `9999` sentinel. The real pressure series is in
`passedchart` (`pressure`, ~1015 hPa), so use that if pressure is needed.

#### Condition codes (`weather.img`)

Verified by sampling 119 stations and cross-referencing `img` against `info`:

| Code | Condition | Code | Condition |
|:---|:---|:---|:---|
| 0 | 晴 clear | 8 | 中雨 moderate rain |
| 1 | 多云 partly cloudy | 9 | 大雨 heavy rain |
| 2 | 阴 overcast | 14 | 小雪 light snow |
| 3 | 阵雨 showers | 18 | 雾 fog |
| 4 | 雷阵雨 thunder showers | 9999 | no data |
| 6 | 雨夹雪 sleet | | |
| 7 | 小雨 light rain | | |

The vocabulary extends beyond these values (snow and dust codes appear in
winter); `9999` always means "no data" and must not be rendered as text.

#### Warning (`warn`)

When no warning is in force, every field holds the `9999` sentinel and
`issuetime` is `""`. When one is active:

| Field | Meaning |
|:---|:---|
| `signaltype` | Hazard type — 大雾, 暴雨, 台风, 高温, ... |
| `signallevel` | Severity colour — 蓝色 / 黄色 / 橙色 / 红色 |
| `issuecontent` | Full statement, including the issuing office |
| `fmeans` | Official guidance for the public |
| `alert` | Short headline (may duplicate `issuecontent`) |
| `issuetime` | Often empty even for an active warning — use `issuecontent` for timing |
| `url`, `pic`, `pic2` | Warning page and icon assets |

### 3.2 `predict` — multi-day forecast

```json
{
  "station": {...},
  "publish_time": "2026-09-16 20:00",
  "detail": [
    {"date": "2026-09-16", "pt": "2026-09-16 20:00",
     "day":   {"weather": {"info": "9999", "img": "9999", "temperature": "9999"},
               "wind": {"direct": "9999", "power": "9999"}},
     "night": {"weather": {"info": "阴", "img": "2", "temperature": "20"},
               "wind": {"direct": "北风", "power": "微风"}},
     "precipitation": 0.0}
  ]
}
```

- Always exactly **7 days**, starting with the current date.
- `day` covers [07:00, 19:00), `night` covers [19:00, next 07:00).
- In the first entry of the day the `day` block is usually all-`9999`, because
  that period has already passed. This is normal, not an error.
- Numeric fields inside `detail` are **strings**, unlike `real`.
- `precipitation` is the expected total for the date, in mm.

### 3.3 `air` — air quality index

```json
{"forecasttime": "2026-09-16 20:00", "aqi": 43, "aq": 1, "text": "优", "aqiCode": "..."}
```

| Field | Meaning |
|:---|:---|
| `aqi` | Index value; `9999` when unavailable |
| `text` | Band — 优 / 良 / 轻度污染 / ... |
| `forecasttime` | Update time |

**Coverage is partial.** In a random 40-station sample, 19 stations had an AQI
and 21 returned `9999`. Treat a missing AQI as normal and omit it rather than
reporting a value of 9999.

### 3.4 `passedchart` — recent hourly observations

An array of up to 24 hourly points, most recent first:

```json
[{"rain1h": 0.0, "rain24h": 9999.0, "temperature": 23.3, "humidity": 70.0,
  "pressure": 1016.0, "windDirection": 220.0, "windSpeed": 0.8,
  "time": "2026-09-16 20:00"}]
```

Useful for a trend line or for pressure, which `real` usually omits. The
`rain6h`/`rain12h`/`rain24h` accumulations are usually `9999`.

### 3.5 `climate` — 1981–2010 monthly normals

`climate.month` holds 12 entries with `maxTemp`, `minTemp`, `precipitation`.
`climate.time` is the baseline period. Useful for context ("is 30°C unusual
here"), not for forecasting. The baseline is decades old — say so if quoting it.

### 3.6 `tempchart` / `radar`

- `tempchart`: daily max/min pairs for the recent past (about 10 days).
- `radar`: `{"title", "image", "url"}` pointing at the latest radar reflectivity
  PNG. Note the image path carries a timestamp and the mosaic is regional; the
  `url` field is the human-facing page.

## Request behaviour

- **No name-based lookup exists.** `/rest/search`, `/rest/city/search` and
  `/rest/province/city` all return HTTP 400. Resolving a name to a station code
  requires fetching the province lists and matching locally — which is what the
  bundled `cities.json` avoids doing on every call, and what
  `scripts/build_index.py` does when the index is rebuilt.
- **No documented rate limit.** The free service has no published quota; keep
  requests at a human pace and cache. A full index rebuild is 35 requests, run
  concurrently by `build_index.py`.
- **Transient failures happen.** An `UNEXPECTED_EOF_WHILE_READING` SSL error was
  observed mid-sweep, so retry rather than treating one failure as absence.
- **Update cadence:** observations roll on a ~10-minute grid product (hourly for
  most stations); forecasts are published several times a day (~08/11/14/17/20)
  — read `publish_time` rather than assuming.

## Precision ceiling

Station granularity is **county/district level**. The full national list has
2528 stations, and each covers one county or district — no township or
street entries exist anywhere in the list. Names ending in 镇/乡/街道 that appear
in the list (柏乡, 天镇, 武乡, 景德镇, ...) are counties and towns whose own names
end in that character, not township-level stations.

For weather at township granularity there is no free public source; the CMA's
gridded 1 km products on `data.cma.cn` require registration and are partly paid.
