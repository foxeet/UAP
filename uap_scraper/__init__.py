"""UAP scraper — pull official US UAP/UFO disclosures from government sources.

Pure standard library (no pip install required). Targets:
  * PURSUE portal            https://www.war.gov/UFO/
  * AARO official imagery     https://www.aaro.mil/UAP-Cases/Official-UAP-Imagery/
  * NASA UAP science page     https://science.nasa.gov/uap/
  * National Archives RG 615  https://catalog.archives.gov/ (API v2)

The package is egress-aware: when it runs inside a sandbox whose network
allowlist does not include a target host, it detects the proxy's
`host_not_allowed` response and reports exactly which hosts to allowlist
instead of failing with an opaque 403.
"""

__version__ = "0.1.0"
