from __future__ import annotations

from typing import Any

from flask import after_this_request
from flask_smorest import Blueprint, abort

from src.extensions import get_db
from src.schemas.stats import (
    ActivityBucketResponse,
    ActivityQuery,
    AsnQuery,
    AsnResponse,
    AuthOutcomesResponse,
    CountriesQuery,
    CountriesResponse,
    CountryDetailPath,
    CountryDetailResponse,
    FingerprintResponse,
    HeatmapPointResponse,
    HeatmapQuery,
    MapResponse,
    OutcomeCountsResponse,
    OutcomesQuery,
    PasswordCompositionResponse,
    PasswordsByLengthQuery,
    PayloadDetailPath,
    PayloadDetailResponse,
    PayloadDownloadResponse,
    SshClientResponse,
    TcpipDestinationResponse,
    TopCountryResponse,
    TopCredentialResponse,
    TopCredentialsQuery,
    TopNQuery,
    TopPasswordResponse,
    TotalsResponse,
    TrendQuery,
    TrendResponse,
)
from src.services.stats import (
    activity,
    clients,
    countries,
    credentials,
    map_deck,
    outcomes,
    payloads,
)
from src.services.types import (
    ActivityBucketDict,
    AuthOutcomesDict,
    CountriesDict,
    CountryAsnDict,
    CountryDetailDict,
    FingerprintDict,
    HeatmapPointDict,
    MapDataDict,
    OutcomeCountsDict,
    PasswordCompositionDict,
    PayloadDetailDict,
    PayloadDownloadDict,
    SshClientDict,
    TcpipDestinationDict,
    TopCountryDict,
    TopCredentialDict,
    TopPasswordDict,
    TotalsDict,
    TrendDict,
)

stats_bp = Blueprint(
    "stats",
    "stats",
    url_prefix="/api/v1/stats",
    description="Aggregate honeypot statistics",
)


@stats_bp.route("/totals")
@stats_bp.doc(operationId="statsTotals")
@stats_bp.response(200, TotalsResponse)
@stats_bp.alt_response(500, "InternalServerError")
def stats_totals() -> TotalsDict:
    """Return headline totals (sessions, auth attempts, unique IPs)."""
    return activity.totals(get_db())


@stats_bp.route("/top-passwords")
@stats_bp.doc(operationId="statsTopPasswords")
@stats_bp.arguments(TopNQuery, location="query")
@stats_bp.response(200, TopPasswordResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_top_passwords(query_args: dict[str, Any]) -> list[TopPasswordDict]:
    """Return the top-N attempted passwords ranked by count."""
    return credentials.top_passwords(get_db(), top_n=query_args["top_n"])


@stats_bp.route("/top-countries")
@stats_bp.doc(operationId="statsTopCountries")
@stats_bp.arguments(TopNQuery, location="query")
@stats_bp.response(200, TopCountryResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_top_countries(query_args: dict[str, Any]) -> list[TopCountryDict]:
    """Return the top-N attacking countries ranked by session count."""
    return countries.top_countries(get_db(), top_n=query_args["top_n"])


@stats_bp.route("/top-credentials")
@stats_bp.doc(operationId="statsTopCredentials")
@stats_bp.arguments(TopCredentialsQuery, location="query")
@stats_bp.response(200, TopCredentialResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_top_credentials(query_args: dict[str, Any]) -> list[TopCredentialDict]:
    """Return the top-N attempted credentials ranked by the chosen metric."""

    # Credentials polls every 30s, these are top-N aggregates over many
    # attempts. Two minutes doesn't matter much.
    @after_this_request
    def _cache(response: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
        response.headers["Cache-Control"] = "public, max-age=120"
        return response

    return credentials.top_credentials(
        get_db(),
        by=query_args["by"],
        metric=query_args["metric"],
        outcome=query_args["outcome"],
        country=query_args.get("country"),
        top_n=query_args["top_n"],
    )


@stats_bp.route("/countries")
@stats_bp.doc(operationId="statsCountries")
@stats_bp.arguments(CountriesQuery, location="query")
@stats_bp.response(200, CountriesResponse)
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_countries(query_args: dict[str, Any]) -> CountriesDict:
    """Return the per-country attack leaderboard ranked by the chosen sort."""

    # Origins polls these every 120s; the aggregates move slowly, so let the
    # browser reuse them instead of re-running the scan on every poll.
    @after_this_request
    def _cache(response: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
        response.headers["Cache-Control"] = "public, max-age=120"
        return response

    return countries.country_breakdown(
        get_db(),
        sort=query_args["sort"],
        top_n=query_args["top_n"],
        order=query_args.get("order"),
    )


@stats_bp.route("/asns")
@stats_bp.doc(operationId="statsAsns")
@stats_bp.arguments(AsnQuery, location="query")
@stats_bp.response(200, AsnResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_asns(query_args: dict[str, Any]) -> list[CountryAsnDict]:
    """Return the top-N source networks (ASN / org) by session count."""

    # Origins polls these every 120s; the aggregates move slowly, so let the
    # browser reuse them instead of re-running the scan on every poll.
    @after_this_request
    def _cache(response: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
        response.headers["Cache-Control"] = "public, max-age=120"
        return response

    return countries.country_asns(
        get_db(), country=query_args.get("country"), top_n=query_args["top_n"]
    )


@stats_bp.route("/auth-outcomes")
@stats_bp.doc(operationId="statsAuthOutcomes")
@stats_bp.response(200, AuthOutcomesResponse)
@stats_bp.alt_response(500, "InternalServerError")
def stats_auth_outcomes() -> AuthOutcomesDict:
    """Return the accept/reject split across all auth attempts."""

    @after_this_request
    def _cache(response: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
        response.headers["Cache-Control"] = "public, max-age=120"
        return response

    return credentials.auth_outcomes(get_db())


@stats_bp.route("/outcomes")
@stats_bp.doc(operationId="statsOutcomes")
@stats_bp.arguments(OutcomesQuery, location="query")
@stats_bp.response(200, OutcomeCountsResponse)
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_outcomes(query_args: dict[str, Any]) -> OutcomeCountsDict:
    """Return session counts per outcome bucket, for the Sessions Outcome filter."""
    return outcomes.outcome_counts(get_db(), country=query_args.get("country"))


@stats_bp.route("/password-composition")
@stats_bp.doc(operationId="statsPasswordComposition")
@stats_bp.response(200, PasswordCompositionResponse)
@stats_bp.alt_response(500, "InternalServerError")
def stats_password_composition() -> PasswordCompositionDict:
    """Return the password length histogram + charset-class breakdown."""

    @after_this_request
    def _cache(response: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
        response.headers["Cache-Control"] = "public, max-age=120"
        return response

    return credentials.password_composition(get_db())


@stats_bp.route("/passwords-by-length")
@stats_bp.doc(operationId="statsPasswordsByLength")
@stats_bp.arguments(PasswordsByLengthQuery, location="query")
@stats_bp.response(200, TopPasswordResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_passwords_by_length(query_args: dict[str, Any]) -> list[TopPasswordDict]:
    """Return the top-N passwords of a given length (histogram drill-down)."""

    @after_this_request
    def _cache(response: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
        response.headers["Cache-Control"] = "public, max-age=120"
        return response

    return credentials.passwords_by_length(
        get_db(), query_args["length"], top_n=query_args["top_n"]
    )


@stats_bp.route("/activity")
@stats_bp.doc(operationId="statsActivity")
@stats_bp.arguments(ActivityQuery, location="query")
@stats_bp.response(200, ActivityBucketResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_activity(query_args: dict[str, Any]) -> list[ActivityBucketDict]:
    """Return session counts grouped by bucket (hour|day|month)."""
    return activity.activity(get_db(), query_args["bucket"], query_args.get("country"))


@stats_bp.route("/trend")
@stats_bp.doc(operationId="statsTrend")
@stats_bp.arguments(TrendQuery, location="query")
@stats_bp.response(200, TrendResponse)
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_trend(query_args: dict[str, Any]) -> TrendDict:
    """Return the session-count trend over period_days vs the prior window."""
    return activity.trend(
        get_db(), query_args["period_days"], query_args.get("country")
    )


@stats_bp.route("/heatmap")
@stats_bp.doc(operationId="statsHeatmap")
@stats_bp.arguments(HeatmapQuery, location="query")
@stats_bp.response(200, HeatmapPointResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_heatmap(query_args: dict[str, Any]) -> list[HeatmapPointDict]:
    """Return session counts per (weekday, hour) cell."""
    return activity.heatmap(get_db(), query_args.get("country"))


@stats_bp.route("/map")
@stats_bp.doc(operationId="statsMap")
@stats_bp.response(200, MapResponse)
@stats_bp.alt_response(500, "InternalServerError")
def stats_map() -> MapDataDict:
    """Return one payload for the Overview map deck: choropleth + city markers."""

    @after_this_request
    def _cache(response: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
        response.headers["Cache-Control"] = "public, max-age=120"
        return response

    return map_deck.map_data(get_db())


@stats_bp.route("/countries/<a2>")
@stats_bp.doc(operationId="statsCountryDetail")
@stats_bp.arguments(CountryDetailPath, location="path")
@stats_bp.response(200, CountryDetailResponse)
@stats_bp.alt_response(404, "NotFound")
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_country_detail(_path_args: dict[str, Any], a2: str) -> CountryDetailDict:
    """Return the country intel-drawer bundle: totals, networks, credentials, trend."""
    result = countries.country_detail(get_db(), a2.upper())
    if result is None:
        abort(404, message="Country not found")

    @after_this_request
    def _cache(response: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
        response.headers["Cache-Control"] = "public, max-age=300"
        return response

    return result


@stats_bp.route("/ssh-clients")
@stats_bp.doc(operationId="statsSshClients")
@stats_bp.arguments(TopNQuery, location="query")
@stats_bp.response(200, SshClientResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_ssh_clients(query_args: dict[str, Any]) -> list[SshClientDict]:
    """Return the top-N SSH client versions ranked by session count."""

    # Origins polls these every 120s; the aggregates move slowly, so let the
    # browser reuse them instead of re-running the scan on every poll.
    @after_this_request
    def _cache(response: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
        response.headers["Cache-Control"] = "public, max-age=120"
        return response

    return clients.ssh_clients(get_db(), top_n=query_args["top_n"])


@stats_bp.route("/fingerprints")
@stats_bp.doc(operationId="statsFingerprints")
@stats_bp.arguments(TopNQuery, location="query")
@stats_bp.response(200, FingerprintResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_fingerprints(query_args: dict[str, Any]) -> list[FingerprintDict]:
    """Return the top-N SSH client public key fingerprints by distinct IP count."""

    # Origins polls these every 120s; the aggregates move slowly, so let the
    # browser reuse them instead of re-running the scan on every poll.
    @after_this_request
    def _cache(response: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
        response.headers["Cache-Control"] = "public, max-age=120"
        return response

    return clients.fingerprints(get_db(), top_n=query_args["top_n"])


@stats_bp.route("/downloads")
@stats_bp.doc(operationId="statsDownloads")
@stats_bp.arguments(TopNQuery, location="query")
@stats_bp.response(200, PayloadDownloadResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_downloads(query_args: dict[str, Any]) -> list[PayloadDownloadDict]:
    """Return the top-N downloaded payloads grouped by SHA256."""
    return payloads.downloads(get_db(), top_n=query_args["top_n"])


@stats_bp.route("/downloads/<sha256>")
@stats_bp.doc(operationId="statsDownloadDetail")
@stats_bp.arguments(PayloadDetailPath, location="path")
@stats_bp.response(200, PayloadDetailResponse)
@stats_bp.alt_response(404, "NotFound")
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_download_detail(_path_args: dict[str, Any], sha256: str) -> PayloadDetailDict:
    """Return full detail for one payload: basic info plus countries breakdown."""
    result = payloads.payload_detail(get_db(), sha256)
    if result is None:
        abort(404, message="Payload not found")
    return result


@stats_bp.route("/tcpip-destinations")
@stats_bp.doc(operationId="statsTcpipDestinations")
@stats_bp.arguments(TopNQuery, location="query")
@stats_bp.response(200, TcpipDestinationResponse(many=True))
@stats_bp.alt_response(422, "UnprocessableEntity")
@stats_bp.alt_response(500, "InternalServerError")
def stats_tcpip_destinations(query_args: dict[str, Any]) -> list[TcpipDestinationDict]:
    """Return the top-N direct-tcpip relay destinations grouped by (host, port)."""
    return payloads.tcpip_destinations(get_db(), top_n=query_args["top_n"])
