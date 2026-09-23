"""Freerouting JAR runner â€” version-aware.

Freerouting's CLI surface changed substantially between 2.1 and 2.3, and so
did its Java requirement. This adapter detects the JAR's version and emits
only the flags that version understands, so upgrading the JAR is a drop-in
operation: put the new file in `third_party/`, and the extra capabilities
turn themselves on.

What each version gives us (measured on this workspace, not assumed):

  2.1.0  Baseline. `-de/-do/-mp/-mt` only. **Its route optimizer is
         multi-threaded and upstream-broken** ("known to generate clearance
         violations"). Neither `-mt 1` nor `FREEROUTING__ROUTER__MAX_THREADS`
         reaches the optimizer â€” both were tested against tms-v3 and the log
         still reports "Starting optimization on 7 threads". On 2.1.0 the
         broken optimizer is unavoidable; re-run DRC and fix what it flags.

  2.2.x  Requires Java 25. Adds a real settings tree (`--router.*`), a DRC
         engine, and a working thread control.

  2.3.0  Requires Java 25. Adds the SMD fanout pre-pass, micro-neckdown
         fallback for failed escape paths, per-layer bend costs, strict DRC,
         and copper-to-edge clearance overrides. This is the version worth
         running for the dense fine-pitch boards in this workspace.

Required environment:
    FREEROUTING_JAR     path to the JAR; default `third_party/freerouting.jar`,
                        else the highest-versioned `freerouting-*.jar` there.
Optional:
    JAVA_BIN            default: `java` on PATH
    JAVA_25_HOME        JDK 25 home, used automatically for 2.2+ JARs
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("kicad-claude.adapters.freerouting")


class FreeroutingError(RuntimeError):
    pass


_PATTERNS = {
    "completion_pct": re.compile(r"(\d+(?:\.\d+)?)\s*% completed", re.IGNORECASE),
    "via_count": re.compile(r"(?:total of\s+)?(\d+)\s+vias", re.IGNORECASE),
    "trace_length_mm": re.compile(
        r"total\s+trace\s+length[:\s]+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE
    ),
    "duration": re.compile(r"routing took\s+(\d+:\d+:\d+)", re.IGNORECASE),
    "passes_done": re.compile(r"pass\s+#?(\d+)\s+.*?was completed", re.IGNORECASE),
    "score": re.compile(r"score of\s+(\d+(?:\.\d+)?)", re.IGNORECASE),
    "version": re.compile(r"Freerouting\s+v(\d+\.\d+\.\d+)", re.IGNORECASE),
}

# 2.2+ reports live counts on every pass: "... with the score of 983.98
# (2 unrouted and 0 violations)". The last one is the outcome.
_SCORE_COUNTS = re.compile(
    r"\((\d+)\s+unrouted\s+and\s+(\d+)\s+violations?\)", re.IGNORECASE
)
# It then names them: "Net '+3V3' (1 unrouted connection):\n    - via -> U3-13"
_UNROUTED_NET = re.compile(
    r"Net\s+'([^']+)'\s+\((\d+)\s+unrouted\s+connection", re.IGNORECASE
)
_STAGNATED = re.compile(
    r"has not improved by more than .* Stopping the auto-router", re.IGNORECASE
)


@dataclass
class RouteProfile:
    """Router tuning. Fields unsupported by the detected JAR are dropped.

    The defaults encode this workspace's house style for 2-layer JLCPCB
    boards: horizontal on the top layer, vertical on the bottom, vias made
    expensive enough that the router prefers a detour over a layer change.
    """

    passes: int = 100
    threads: int = 1
    #: Per copper layer, front to back. None = leave Freerouting's default.
    preferred_direction_horizontal: list[bool] | None = field(
        default_factory=lambda: [True, False]
    )
    via_costs: int | None = 50
    bend_penalty: int | None = None
    unrouted_net_penalty: int | None = None
    clearance_violation_penalty: int | None = None
    fanout: bool = True
    strict_drc: bool = False
    automatic_neckdown: bool = True
    optimizer_improvement_threshold: float | None = None
    ignore_net_classes: list[str] = field(default_factory=list)


def _jar_candidates(directory: Path) -> list[Path]:
    return sorted(directory.glob("freerouting-*.jar")) + [
        directory / "freerouting.jar"
    ]


def available_jars() -> list[tuple[tuple[int, int, int], Path]]:
    """Every Freerouting JAR we can see, newest first.

    FREEROUTING_JAR, when set, is the only candidate â€” an explicit override
    should never be silently ignored in favour of some other file.
    """
    env = os.environ.get("FREEROUTING_JAR")
    if env:
        p = Path(env).expanduser()
        return [(jar_version(p) or (0, 0, 0), p)] if p.is_file() else []

    repo_root = Path(__file__).resolve().parents[3]
    third_party = repo_root / "third_party"
    if not third_party.is_dir():
        return []

    found: dict[Path, tuple[int, int, int]] = {}
    for cand in _jar_candidates(third_party):
        if cand.is_file():
            found[cand.resolve()] = jar_version(cand) or (0, 0, 0)
    return sorted(((v, p) for p, v in found.items()), key=lambda t: t[0], reverse=True)


def find_freerouting_jar() -> Path | None:
    """The newest JAR present, regardless of whether its Java is installed."""
    jars = available_jars()
    return jars[0][1] if jars else None


def jar_version(jar: Path) -> tuple[int, int, int] | None:
    """Read the JAR's version. Filename first, then the build date in the
    manifest (Freerouting does not stamp Implementation-Version)."""
    m = re.search(r"freerouting-(\d+)\.(\d+)\.(\d+)\.jar$", jar.name)
    if m:
        return tuple(int(g) for g in m.groups())  # type: ignore[return-value]
    try:
        with zipfile.ZipFile(jar) as zf:
            manifest = zf.read("META-INF/MANIFEST.MF").decode("utf-8", "replace")
    except Exception:
        return None
    date = re.search(r"Build-Date:\s*(\d{4})-(\d{2})-(\d{2})", manifest)
    if not date:
        return None
    # Build dates map onto the releases we know about.
    y, mo = int(date.group(1)), int(date.group(2))
    if (y, mo) >= (2026, 8):
        return (2, 3, 0)
    if (y, mo) >= (2026, 4):
        return (2, 2, 0)
    return (2, 1, 0)


def required_java_major(version: tuple[int, int, int] | None) -> int:
    """Freerouting 2.2.0 onward is compiled for Java 25; 2.1.x for Java 21."""
    if version is None or version < (2, 2, 0):
        return 21
    return 25


def java_major(java: Path) -> int | None:
    try:
        r = subprocess.run(
            [str(java), "-version"], capture_output=True, text=True, timeout=30
        )
    except Exception:
        return None
    m = re.search(r'version "(\d+)', (r.stderr or "") + (r.stdout or ""))
    return int(m.group(1)) if m else None


def find_java(min_major: int = 21) -> Path | None:
    """Find a JRE of at least `min_major`.

    Order: JAVA_25_HOME (when 25 is needed) > JAVA_BIN > macOS java_home >
    `java` on PATH.
    """
    if min_major >= 25:
        home = os.environ.get("JAVA_25_HOME")
        if home:
            cand = Path(home) / "bin" / "java"
            if cand.is_file():
                return cand

    custom = os.environ.get("JAVA_BIN")
    if custom and Path(custom).is_file():
        if (java_major(Path(custom)) or 0) >= min_major:
            return Path(custom)

    helper = Path("/usr/libexec/java_home")
    if helper.is_file():
        try:
            r = subprocess.run(
                [str(helper), "-v", str(min_major)],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0 and r.stdout.strip():
                cand = Path(r.stdout.strip()) / "bin" / "java"
                if cand.is_file():
                    return cand
        except Exception:
            pass

    java = shutil.which("java")
    if java and (java_major(Path(java)) or 0) >= min_major:
        return Path(java)
    return None


def _ensure_environment() -> tuple[Path, Path, tuple[int, int, int] | None]:
    """Pick the newest JAR whose Java requirement is actually satisfiable.

    Dropping a 2.3 JAR into `third_party/` on a machine that only has Java 21
    must not break routing â€” we fall back to the 2.1 JAR and say so once, in
    the log, rather than failing the run.
    """
    jars = available_jars()
    if not jars:
        raise FreeroutingError(
            "freerouting.jar not found. Set FREEROUTING_JAR or download it to "
            "third_party/ (https://github.com/freerouting/freerouting/releases)"
        )

    unusable: list[str] = []
    for version, jar in jars:
        need = required_java_major(version)
        java = find_java(need)
        if java is not None:
            if unusable:
                logger.warning(
                    "falling back to %s; newer JAR(s) unusable here: %s",
                    jar.name, "; ".join(unusable),
                )
            return jar, java, version
        unusable.append(f"{jar.name} needs Java {need}")

    newest_version, newest = jars[0]
    need = required_java_major(newest_version)
    raise FreeroutingError(
        f"No usable Freerouting JAR. {'; '.join(unusable)}. "
        f"Install the JDK (macOS: `brew install --cask temurin@{need}`) or set "
        f"JAVA_25_HOME / JAVA_BIN, or keep a 2.1.x JAR in third_party/ for "
        f"Java 21."
    )


def build_args(
    version: tuple[int, int, int] | None,
    profile: RouteProfile,
    *,
    drc_report: Path | None = None,
) -> list[str]:
    """Flags supported by `version`, in that version's own syntax."""
    args: list[str] = ["-mp", str(profile.passes), "-mt", str(profile.threads), "-da"]
    if profile.ignore_net_classes:
        args += ["-inc", ",".join(profile.ignore_net_classes)]

    modern = version is not None and version >= (2, 2, 0)
    if not modern:
        # 2.1.x understands nothing below, and rejects unknown arguments.
        return args

    args.append("--gui.enabled=false")
    # 2.2+ exposes a thread control that actually reaches the optimizer.
    if profile.threads == 1:
        args.append("--feature_flags.multi_threading=false")

    if profile.preferred_direction_horizontal:
        vals = ",".join("true" if h else "false"
                        for h in profile.preferred_direction_horizontal)
        args.append(f"--router.layers.preferred_direction_horizontal={vals}")
    if profile.via_costs is not None:
        args.append(f"--router.scoring.via_costs={profile.via_costs}")
    if profile.bend_penalty is not None:
        args.append(f"--router.scoring.bend_penalty={profile.bend_penalty}")
    if profile.unrouted_net_penalty is not None:
        args.append(
            f"--router.scoring.unrouted_net_penalty={profile.unrouted_net_penalty}"
        )
    if profile.clearance_violation_penalty is not None:
        args.append(
            "--router.scoring.clearance_violation_penalty="
            f"{profile.clearance_violation_penalty}"
        )
    if profile.optimizer_improvement_threshold is not None:
        args.append(
            "--router.optimizer.improvement_threshold="
            f"{profile.optimizer_improvement_threshold}"
        )
    args.append(f"--router.fanout.enabled={'true' if profile.fanout else 'false'}")
    args.append(
        f"--router.automatic_neckdown={'true' if profile.automatic_neckdown else 'false'}"
    )
    if profile.strict_drc:
        args.append("--router.strict_drc=true")
    if drc_report is not None:
        args += ["-drc", str(drc_report)]
    return args


def _parse_stats(combined_output: str) -> dict:
    """Pull whatever Freerouting printed into a dict. Best-effort."""
    stats: dict = {}
    last_match_keys = {"completion_pct", "passes_done", "score"}

    for key, pattern in _PATTERNS.items():
        matches = pattern.findall(combined_output)
        if not matches:
            continue
        stats[key] = matches[-1] if key in last_match_keys else matches[0]

    for k in ("via_count", "passes_done"):
        if k in stats:
            try:
                stats[k] = int(stats[k])
            except ValueError:
                pass
    for k in ("completion_pct", "trace_length_mm", "score"):
        if k in stats:
            try:
                stats[k] = float(stats[k])
            except ValueError:
                pass

    counts = _SCORE_COUNTS.findall(combined_output)
    if counts:
        stats["reported_unrouted"] = int(counts[-1][0])
        stats["reported_violations"] = int(counts[-1][1])
    else:
        # 2.1.x never prints these; absence is not evidence of a clean route.
        stats["reported_unrouted"] = None
        stats["reported_violations"] = None

    stats["unrouted_nets"] = [
        {"net": n, "connections": int(c)}
        for n, c in _UNROUTED_NET.findall(combined_output)
    ]
    stats["stagnated"] = bool(_STAGNATED.search(combined_output))
    stats["optimizer_multithreaded_warning"] = bool(
        re.search(r"Multi-threaded route optimization is broken", combined_output)
    )
    return stats


def route(
    dsn_path: Path,
    ses_path: Path,
    *,
    profile: RouteProfile | None = None,
    passes: int | None = None,
    threads: int | None = None,
    timeout_seconds: float = 600.0,
    drc_report: Path | None = None,
    extra_args: list[str] | None = None,
) -> dict:
    """Run Freerouting on `dsn_path`, writing `ses_path`.

    `passes`/`threads` override the profile for callers that only care about
    those two. Raises rather than returning a partial result when no SES is
    produced â€” a missing SES means nothing was routed, whatever the exit code.
    """
    jar, java, version = _ensure_environment()
    profile = profile or RouteProfile()
    if passes is not None:
        profile.passes = passes
    if threads is not None:
        profile.threads = threads

    dsn_path = Path(dsn_path).expanduser().resolve()
    ses_path = Path(ses_path).expanduser().resolve()
    if not dsn_path.is_file():
        raise FileNotFoundError(dsn_path)
    if ses_path.exists():
        # A stale SES from a previous run would otherwise look like success.
        ses_path.unlink()

    cmd = [str(java), "-jar", str(jar), "-de", str(dsn_path), "-do", str(ses_path)]
    cmd += build_args(version, profile, drc_report=drc_report)
    if extra_args:
        cmd += list(extra_args)

    logger.info("running freerouting: %s", " ".join(cmd))
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired as e:
        raise FreeroutingError(
            f"Freerouting timed out after {timeout_seconds}s "
            f"(consider a larger timeout, fewer passes, or a simpler design)"
        ) from e

    combined = (r.stdout or "") + "\n" + (r.stderr or "")

    if not ses_path.is_file():
        raise FreeroutingError(
            f"Freerouting did not produce {ses_path}. "
            f"rc={r.returncode}, stderr tail: {r.stderr[-400:]}"
        )

    stats = _parse_stats(combined)
    return {
        "returncode": r.returncode,
        "ses_path": str(ses_path),
        "jar": str(jar),
        "jar_version": ".".join(str(v) for v in version) if version else "unknown",
        "java": str(java),
        "args": cmd[3:],
        "stats": stats,
        "stdout_tail": (r.stdout or "")[-1000:],
        "stderr_tail": (r.stderr or "")[-400:],
    }
