# Terra Incognita Maps reference

Retrieved 2026-11-01 at the user's request for visual reference.

- Source: https://maps.app.goo.gl/P3JaLGLSdGcLgjqo6
- Resolved panorama ID: `CIHM0ogKEICAgIC43dfKJQ`
- Dimensions encoded in the Maps URL: 10000 × 5000 (full panorama not downloaded or verified).
- Local file: `terra-incognita-preview.jpg`, 900 × 600 perspective preview from the image URL embedded in Google's redirect.
- Capture date and photographer: unknown.
- Rights: third-party reference; no redistribution license established. Exclude from runtime exports and do not assume the repository's asset license applies.

The preview was visually inspected: illuminated wood-framed glass cabinets contain teapots, cups, and decorative figurines. It is a close view of merchandise, with insufficient wall/floor coverage to establish room dimensions or placement in the existing plan.

The user's gallery screenshot shows multiple indoor panorama entries, including book shelving, display cases, corridors/doorways, and a seating area with a carved screen. These are coverage clues; connections between viewpoints have not been verified.

Acquisition status: the short link successfully resolved using an HTTP request outside the restricted network. The linked preview downloaded successfully. `stiles/streetview-dl` was researched but not installed or executed: its documented Google Maps API key requirement is not configured (`GOOGLE_MAPS_API_KEY` absent). No full panorama or depth/mesh data has been acquired.

Project constraint confirmed by user: remote reconstruction from existing material. Next input needed for that downloader is a locally configured API key with Map Tiles API enabled and billing, followed by a single-panorama compatibility test. Do not paste credentials into this file or chat.

## Follow-up API test

The local key was subsequently configured in `.env`. The latest test successfully created a Google Map Tiles Street View session, resolving the earlier key restriction issue. `streetview-dl` was executed through `uv tool run`.

The downloader's URL parser rejected the original `!3m6!1s` URL structure; supplying the same panorama ID through its supported `panoid` query parameter passed parsing. Google then returned HTTP 404, `Not Found`, for the Street View metadata request for `CIHM0ogKEICAgIC43dfKJQ`. A separate direct metadata request confirmed that response. This establishes that the requested ID is unavailable through this API request, not that the panorama has disappeared from the Maps viewer. The reason is unconfirmed.

No full panorama was downloaded. The existing 900 × 600 preview remains the only downloaded image from this viewpoint. A current panorama link/ID or an original exported panorama is needed for the next attempt; a nearby coordinate search would not guarantee the same indoor viewpoint. Credentials and session tokens are not recorded here.

## Successful tearoom download

The subsequent user link https://maps.app.goo.gl/Mn64k4nzKEDxDQMUA resolved to Maps ID `CIHM0ogKEICAgIC43b-sKA`. Direct use of that ID also returned 404. A metadata lookup within 10 metres of its coordinates (46.4792172, 30.7409716) returned API ID `CAoSFkNJSE0wb2dLRUlDQWdJQzQzYi1zS0E.`, whose encoded payload contains the same Maps ID. Thus this result matches the requested viewpoint, rather than substituting a nearby street image.

Using that API ID with streetview-dl successfully produced:

- `../../captures/panoramas/terra-incognita-tearoom-2017-11.jpg`: 10000 × 5000 equirectangular reference, 3436103 bytes.
- `../../captures/panoramas/terra-incognita-tearoom-2017-11.json`: metadata including orientation and two adjacent panorama links; checked for credential query strings and API keys, none found.
- API date: November 2017. Attribution: From the Owner, Photo by: Cube Online Україна.

The image was opened and visually verified. It shows pink bench seating, blue chairs/sofa, round dark tables, pendant lights, a carved folding screen, a leaf-pattern feature wall, a large mirror, and an opening to illuminated tea shelving. The nadir has a stretched band and must not be treated as observed floor detail. Dimensions remain unmeasured. This is a historical reference, not evidence of the current interior.

The wrapper encountered a Windows console encoding error while printing downloader output after files had been saved; image inspection and metadata parsing confirmed successful acquisition. The earlier 404 findings above describe use of the Maps-facing IDs; they do not establish that the images are absent from the API.

## Connected tour acquired

Following the API-native neighbour links produced a complete connected set of 23 panoramas from the same November 2017 tour. All images were verified at 10000 × 5000 pixels. The initial shop panorama is recovered as `view-09`. See [the reference index](../../captures/panoramas/README.md) and [floor-plan comparison](../../floorplan/panorama-comparison.md). These supersede the earlier acquisition blockers recorded above.
