"""Official Romanian source adapter — Portal Legislativ SOAP discovery.

Scope of this module: discovery and metadata only.

The SOAP service returns the act as *originally published*, not the consolidated
form currently in force. Verified on Legea 506/2004: the SOAP `Text` carries no
consolidation annotations and still refers to Legea nr. 677/2001 (repealed in
2018), while the consolidated HTML at `LinkHtml` carries 22 amendment notes and
a materially different art. 4 para. (5).

Therefore SOAP is used for: locating the act, act metadata, and — most
importantly — the `LinkHtml` URL that `fetch_ro_consolidated.py` downloads to
obtain the citable text. The SOAP `Text` is archived for provenance but must
never be parsed into provisions.

Network access is opt-in so tests/builds are reproducible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

# Values below are taken from the published WSDL, not guessed:
# https://legislatie.just.ro/apiws/FreeWebService.svc?wsdl
ENDPOINT = "https://legislatie.just.ro/apiws/FreeWebService.svc/SOAP"
WSDL = "https://legislatie.just.ro/apiws/FreeWebService.svc?wsdl"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TEMPURI = "http://tempuri.org/"
PORT_TYPE = "IFreeWebService"
DATA_CONTRACT = "http://schemas.datacontract.org/2004/07/FreeWebService"
# The portal's WAF rejects the default urllib agent with HTTP 403.
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

# `Legi` fields, in the order declared by the data contract.
LEGI_FIELDS = ("DataVigoare", "Emitent", "LinkHtml", "Numar", "Publicatie",
               "Text", "TipAct", "Titlu")


def soap_call(operation: str, body: str, timeout: int = 90) -> bytes:
    envelope = (f'<?xml version="1.0" encoding="utf-8"?>'
                f'<s:Envelope xmlns:s="{SOAP_NS}"><s:Body>{body}</s:Body></s:Envelope>')
    request = Request(
        ENDPOINT,
        data=envelope.encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"{TEMPURI}{PORT_TYPE}/{operation}",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def get_token() -> str:
    root = ET.fromstring(soap_call("GetToken", f'<GetToken xmlns="{TEMPURI}"/>'))
    for element in root.iter():
        if _local(element.tag) == "GetTokenResult" and element.text:
            return element.text.strip()
    raise RuntimeError("SOAP GetToken returned no token")


def search(token: str, year: int, number: int, *, page: int = 1,
           page_size: int = 50) -> list[dict[str, str]]:
    """Call Search. `SearchModel` is a nested complex type in its own namespace
    and its children follow the xs:sequence order declared by the contract."""
    body = (
        f'<Search xmlns="{TEMPURI}">'
        f'<SearchModel xmlns:d="{DATA_CONTRACT}">'
        f"<d:NumarPagina>{page}</d:NumarPagina>"
        f"<d:RezultatePagina>{page_size}</d:RezultatePagina>"
        f"<d:SearchAn>{year}</d:SearchAn>"
        f"<d:SearchNumar>{number}</d:SearchNumar>"
        f"</SearchModel>"
        f"<tokenKey>{token}</tokenKey>"
        f"</Search>"
    )
    root = ET.fromstring(soap_call("Search", body))
    results = []
    for item in root.iter():
        if _local(item.tag) != "Legi":
            continue
        values = {_local(child.tag): (child.text or "") for child in item}
        results.append({field: values.get(field, "") for field in LEGI_FIELDS})
    return results


def select_act(results: list[dict[str, str]], *, tip: str,
               emitent: str | None = None) -> dict[str, str]:
    """Pick the act by type. A number/year pair is NOT unique: Search(2004, 506)
    returns a HOTARARE on ballot papers, a DECRET on a military promotion and
    only then the LEGE. Never fall back to the first result."""
    candidates = [row for row in results
                  if row.get("TipAct", "").strip().upper() == tip.strip().upper()]
    if emitent:
        narrowed = [row for row in candidates
                    if emitent.strip().lower() in row.get("Emitent", "").strip().lower()]
        if narrowed:
            candidates = narrowed
    if not candidates:
        seen = sorted({row.get("TipAct", "?").strip() for row in results})
        raise SystemExit(
            f"No act of type {tip!r} in {len(results)} result(s); types returned: {seen}")
    if len(candidates) > 1:
        raise SystemExit(
            f"Ambiguous: {len(candidates)} acts of type {tip!r}; refine with --emitent")
    return candidates[0]


def _update_manifest(path: Path, key: str, entry: dict) -> None:
    manifest = (json.loads(path.read_text(encoding="utf-8")) if path.exists()
                else {"skill": "jurist", "schema_version": 1, "sources": {}, "acts": {}})
    acts = manifest.setdefault("acts", {})
    acts[key] = {**acts.get(key, {}), **entry}
    manifest.setdefault("sources", {})["legislatie_just_ro"] = {
        "method": "SOAP",
        "role": "discovery_and_metadata",
        "last_sync": entry["retrieved_at"],
        "documents": len(acts),
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover a Romanian act through the official SOAP service")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--number", type=int, required=True)
    parser.add_argument("--tip", default="LEGE",
                        help="act type as returned by the portal (LEGE, OUG, OG, HOTARARE...)")
    parser.add_argument("--emitent", default=None,
                        help="optional issuer filter when a type is still ambiguous")
    parser.add_argument("--act-id", default=None,
                        help="canonical act id used as the manifest key")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "raw")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "manifest.json")
    parser.add_argument("--network", action="store_true",
                        help="required to perform the official network call")
    args = parser.parse_args()

    if not args.network:
        print(json.dumps({"status": "DRY_RUN", "endpoint": ENDPOINT, "wsdl": WSDL,
                          "warning": "SOAP fetch disabled; no RO sources downloaded"}))
        return 0

    results = search(get_token(), args.year, args.number)
    if not results:
        raise SystemExit(f"SOAP Search returned nothing for {args.year}/{args.number}")
    act = select_act(results, tip=args.tip, emitent=args.emitent)

    link = (act.get("LinkHtml") or "").strip()
    if not link:
        raise SystemExit("Selected act carries no LinkHtml; consolidated text unreachable")

    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    original_text = act.get("Text") or ""
    key = args.act_id or f"RO:{args.tip.upper()}:{args.number}:{args.year}"

    output = args.raw_dir / "ro" / f"{args.year}-{args.number}-{args.tip.lower()}.soap.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "legislatie_just_ro",
        "role": "discovery_and_metadata",
        "endpoint": ENDPOINT,
        "retrieved_at": retrieved_at,
        "sha256_original_text": hashlib.sha256(original_text.encode("utf-8")).hexdigest(),
        "note": "SOAP Text is the originally published form, NOT the consolidated "
                "text in force. Archived for provenance only; never parse it into "
                "provisions. Use fetch_ro_consolidated.py with consolidated_url.",
        "act": act,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    entry = {
        "act_id": key,
        "soap_snapshot": str(output.relative_to(ROOT)),
        "soap_checksum": payload["sha256_original_text"],
        "consolidated_url": link,
        "retrieved_at": retrieved_at,
        "detected_at": retrieved_at,
        # Verified misleading: the portal reports the original entry into force
        # (2004-11-28 for Legea 506/2004) even for texts amended in 2012 and 2015.
        "data_vigoare_reported": act.get("DataVigoare") or None,
        "data_vigoare_is_version_date": False,
        "titlu_reported": " ".join((act.get("Titlu") or "").split()) or None,
        "emitent": act.get("Emitent") or None,
        "publicatie": act.get("Publicatie") or None,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    _update_manifest(args.manifest, key, entry)

    print(json.dumps({"status": "DISCOVERED", "act_id": key, "tip": act.get("TipAct"),
                      "titlu": entry["titlu_reported"], "consolidated_url": link,
                      "soap_snapshot": str(output), "candidates_seen": len(results),
                      "next": "scripts/fetch_ro_consolidated.py"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
