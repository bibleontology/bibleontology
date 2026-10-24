# Third-party files served by the site

Served from here rather than a CDN so that a content security policy can allow
scripts, styles and fonts from this site alone (docs/LAUNCH.md, 2026-10-01). Each is pinned by
version and checksum; replace a file only by downloading the named version and
recording its new checksum here. **The scripts are also checked by the
browser**: index.html's `SRI` table carries each script's SHA-256 (base64)
and `loadScript` sets it as the tag's `integrity`, so a file whose bytes
differ is refused. Replacing a script means a new file name, a new row here
and a new `SRI` entry.

| File | Package, version | Source | SHA-256 | Licence |
|---|---|---|---|---|
| `mermaid-11.17.2.min.js` | mermaid 11.17.2, `dist/mermaid.min.js` | https://cdn.jsdelivr.net/npm/mermaid@11.17.2/dist/mermaid.min.js | `581ED7D74BD9048D0E3A91363927D72EF22942D7722546B27F7CC29E35390EB8` | MIT (https://github.com/mermaid-js/mermaid/blob/develop/LICENSE) |

Downloaded 2026-10-01 with the owner's approval. Used by the structure panel's clause diagrams (index.html,
`mermaidLib`).

## Cytoscape

| File | Package, version | Source | SHA-256 | Licence |
|---|---|---|---|---|
| `cytoscape-3.30.2.min.js` | cytoscape 3.30.2, `dist/cytoscape.min.js` | **copied from app1's `app/static/cytoscape.min.js`** (in the repo since 2026-08-09, commit 354bd30a), not downloaded again | `83E8C54A6BEC655BFD81DF07DF605649C268AF69AECA67A5EA2DA54EA42DAC81` | MIT (header of the file: The Cytoscape Consortium) |

Used by the Knowledge Graph Navigator (index.html, `kgnStart`), loaded only
when that Explore section is opened. **Checked against the published
3.30.2 on 2026-10-01** (with the owner's approval to download it and have
Fable vet it): downloaded from
`https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js`, 373,304
bytes, identical byte for byte (same SHA-256 as above). Until then nothing
recorded where app1's copy, live since August, had come from. Two calls were read for the content security
policy (2026-10-01): `Function("return this")` sits behind a check that is
true in any browser, so it never runs; and it adds one small inline
stylesheet, which `style-src 'unsafe-inline'` allows.

## Fonts: `fonts-2026-10-01/`

Spectral (300, 400, 400 italic, 600), IBM Plex Mono (400, 500) and Noto Serif
Hebrew (400), until 2026-10-01 loaded from Google Fonts on every page view.
Downloaded 2026-10-01 with the owner's approval, so that no reader's browser contacts Google and the content
security policy allows this site alone.

**How they were taken, so they can be taken again the same way.** Google's own
stylesheet for the link the page used --
`https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,300;0,400;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&family=Noto+Serif+Hebrew:wght@400&display=swap`
-- fetched with a current Chrome user agent (Google sends WOFF2 to that), and
every file it names downloaded unchanged from `fonts.gstatic.com`. `fonts.css`
is Google's stylesheet with each URL replaced by the local file name; the
per-script split and its `unicode-range` are Google's, so a browser still
fetches only the files a page's characters need. All 33 kept, including the
Cyrillic and Vietnamese files no page uses today, so behaviour is unchanged.
464 KB in all.

**To update**, take them again into a new dated folder and change the one
`<link>` in index.html: Caddy marks `/vendor/*` immutable for a year, so a
file must never change under a name already served.

**Licence.** All three are under the SIL Open Font License 1.1, which allows
redistributing them, with web pages, provided the licence goes with them. Each
font's own licence file, from its Google Fonts repository
(`https://raw.githubusercontent.com/google/fonts/main/ofl/<name>/OFL.txt`), is
in `app2/fonts-licences/`, and About credits the fonts. IBM's reserves the name
"Plex" for unmodified versions, which these are.

| File | SHA-256 |
|---|---|
| `fonts.css` | `4BED7C56DB457A88A53C2A24F6B70C774430D9F3FEBAF31AF30D0EEE6E688FC5` |
| `ibm-plex-mono-400-cyrillic-ext.woff2` | `F8C22EC1804BD6966B70F43AC7C327025645B4C09597117FCA2A5A6C750106FE` |
| `ibm-plex-mono-400-cyrillic.woff2` | `7635422BD10DDBBCB0E0CAA1154B928298F5C8319B8C00B30978D4395F4783CE` |
| `ibm-plex-mono-400-vietnamese.woff2` | `62632B6375305E70DDCAFDD895218E6AE41A184FCD280A69C739460604CA00A9` |
| `ibm-plex-mono-400-latin-ext.woff2` | `6BC0F226A5B7884A8170E3F62C63D7675609D4631BDC5931B5CDAB81821F00EB` |
| `ibm-plex-mono-400-latin.woff2` | `08949F728DC52D528E69B1667D15C89A5686A4EE9A296FF90983985F99C380F7` |
| `ibm-plex-mono-500-cyrillic-ext.woff2` | `3FEBE5C7F22E4B07B4552738673C3DBE8BCED2DC5F48B866EDF7CCD9552D109A` |
| `ibm-plex-mono-500-cyrillic.woff2` | `1D89462E86CB8E87E7E9D6F6635605BD7C3081BACA6CAAECEE84916BF7B60EDC` |
| `ibm-plex-mono-500-vietnamese.woff2` | `781633D95DE88040FB77141D1E65D928C87C0144691FBC74DA5A64D137A7E910` |
| `ibm-plex-mono-500-latin-ext.woff2` | `6BB06407C97584B0867A959E05E8874693BFEB8C317DE190811C51598F2D99EA` |
| `ibm-plex-mono-500-latin.woff2` | `01D285447409C8A588692162439A038B8CBD7871309EE20267B0D2D91C6E8E22` |
| `noto-serif-hebrew-400-hebrew.woff2` | `5FD3FC127FC1B627673A85979750526B70C2AC6FEAECFADD3D2321D7DEDC8585` |
| `noto-serif-hebrew-400-latin-ext.woff2` | `D9969CB30026525CA06217EDF7F64165A9AA473C9781D46387164C24C6797D45` |
| `noto-serif-hebrew-400-latin.woff2` | `C5446F84BEC8038D6A644C83695CC8E97D2065C02504D78C42B509FACC965414` |
| `spectral-300-cyrillic-ext.woff2` | `2E6D5B649AA1678D42EF1F3F7781B966F8D3F3AEE9F05A2743BB96F27973450D` |
| `spectral-300-cyrillic.woff2` | `D3BA078AF9506DB9716D30BFEFACEE970A72814DB3DD572F7C424137FCB83CBB` |
| `spectral-300-vietnamese.woff2` | `9DEE10D047FA8BC0127025D8505B60C1D81672AFA27282D2CB07D850B6D25FA3` |
| `spectral-300-latin-ext.woff2` | `1760BEA6409F3D1A95F6C68FC3CACABC61F327753870556C826371011D998B15` |
| `spectral-300-latin.woff2` | `3FF652C63672DAC64699F04465D7E679045D8CDDDFB2A2A1A8762D28866E2891` |
| `spectral-400-cyrillic-ext.woff2` | `2063CA386DE935A6EE88DE6503CCBAA66BFD4588CA8E6516748F67F8B642122B` |
| `spectral-400-cyrillic.woff2` | `26ED02D522D35CA1630BE575F96DF8FB290882061571A87EF3AB7FC323D28F87` |
| `spectral-400-vietnamese.woff2` | `E8C68397ACD8950CA955DE46C130C6A393EA087D50E677BACE1DEF6460F44883` |
| `spectral-400-latin-ext.woff2` | `FC4B2566CCD9714A72C2137F822311CB0131296C83C8EE93848AE6F887969E85` |
| `spectral-400-latin.woff2` | `CF8DAEE3B83C1E662196C6E34E444BC41344D54BFEB4FB5351E197DE6CE94539` |
| `spectral-400i-cyrillic-ext.woff2` | `2FFE627C5122156C7D49C79D69065EA98A90685FED57271648A44EA34452A7C7` |
| `spectral-400i-cyrillic.woff2` | `800E7C4478044BD0861DDD67B822AC1BB18220E0CCB90C029FE88052262C99D4` |
| `spectral-400i-vietnamese.woff2` | `4248DC09C3FF0A927C12158F48D35B982C3686C12C0218ABEE02F56373775B73` |
| `spectral-400i-latin-ext.woff2` | `F554218B51A0EADC0709D6027E684AD9B5B21DDC4F3DFD4BA171BA2B41B0C99F` |
| `spectral-400i-latin.woff2` | `DB397149A9F73FD6A41DD2FDF3314CF8A9DAF0485134465CC268CAC578766B71` |
| `spectral-600-cyrillic-ext.woff2` | `91038132400FFCF3DB691AAB8961E83E0C49E896E14F4509B064BE49CA7822F6` |
| `spectral-600-cyrillic.woff2` | `A8297883E0F04031243B893BEE1B629EB43DD90B3957E89D61B67109D655B04F` |
| `spectral-600-vietnamese.woff2` | `84E2CC86832A0B2036BA03F00B79EF455083B3D459BAFB4C8AFAB05F728B9335` |
| `spectral-600-latin-ext.woff2` | `DEA6BD9CA650814AF1F750B7474D7205B7FE0E4C79A6B58C6F7157D90DC8815C` |
| `spectral-600-latin.woff2` | `33FACA8B5795A0DE1AF77CBC43A050A3655C4B1E03E04847FDEF4D19D2E361D2` |
