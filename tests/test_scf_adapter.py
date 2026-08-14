from __future__ import annotations

import httpx

from microdata_lab.adapters.scf import SCFAdapter
from microdata_lab.models import ArtifactRole

HTML = """
<html><body>
<a href="/econres/files/scf2022s.zip">Stata version</a>
<a href="/econres/files/scf2022rw1s.zip">Stata replicate weights</a>
<a href="/econres/files/scfp2022s.zip">Stata extract data</a>
<a href="/econres/files/scfp2022excel.zip">CSV extract data</a>
<a href="/econres/files/codebk2022.txt">Codebook</a>
<a href="/econres/files/2022_scf_changes.txt">Changes for 2022</a>
<a href="/econres/files/Standard_Error_Documentation.pdf">Standard Error Documentation</a>
<a href="/econres/files/bulletin.macro.txt">Variable Definitions</a>
</body></html>
"""


def test_discovers_complete_2022_release() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=HTML, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        adapter = SCFAdapter(client=client)
        release = adapter.discover(year=2022)
        years = adapter.available_years()

    assert release.year == 2022
    assert years == [2022]
    assert {artifact.role for artifact in release.artifacts} == set(ArtifactRole)
    assert all(artifact.url.host == "www.federalreserve.gov" for artifact in release.artifacts)


def test_rejects_year_missing_from_official_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=HTML, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        adapter = SCFAdapter(client=client)
        try:
            adapter.discover(year=2019)
        except ValueError as error:
            assert "2019" in str(error)
        else:
            raise AssertionError("missing release should fail")
