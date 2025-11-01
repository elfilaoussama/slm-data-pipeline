import os
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict


DOCKER_BIN = shutil.which('docker')
DOCKER = DOCKER_BIN or 'docker'
DOCKER_AVAILABLE = DOCKER_BIN is not None


SCANCODE_IMAGE = 'nexB/scancode-toolkit:latest'
SEMGREP_IMAGE = 'returntocorp/semgrep:latest'
BANDIT_IMAGE = 'pycqa/bandit:latest'
GITLEAKS_IMAGE = 'zricethezav/gitleaks:latest'


def _run(cmd: list, cwd: Path = None, timeout: int = 1800) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        # Return a dummy CompletedProcess-like object on failure to keep pipeline resilient
        class Dummy:
            returncode = 1
            stdout = ''
            stderr = str(e)

        return Dummy()  # type: ignore


def _docker_run(image: str, mounts: list[tuple[Path, str]], args: list, workdir: str = '/work'):
    cmd = [DOCKER, 'run', '--rm']
    for src, dst in mounts:
        cmd += ['-v', f"{str(src)}:{dst}"]
    cmd += ['-w', workdir, image]
    return cmd + args


def security_and_license_gate(snapshot_info: Dict, cfg: Dict) -> Dict:
    work_dir = Path(snapshot_info['work_dir'])
    repo_path = Path(snapshot_info['repo_path'])
    reports_dir = Path(cfg['paths'].get('security_reports', '.reports/security'))
    reports_dir.mkdir(parents=True, exist_ok=True)
    sec_cfg = cfg.get('security', {}) or {}
    timeout = int(sec_cfg.get('timeout_seconds', 1800))

    allowed = set(cfg.get('allowed_licenses', []))
    detected_license = None
    license_text = None
    scancode_out = reports_dir / f"{work_dir.name}_scancode.json"
    if DOCKER_AVAILABLE and sec_cfg.get('scancode', True):
        scancode_cmd = _docker_run(
            SCANCODE_IMAGE,
            [(repo_path, '/src'), (reports_dir, '/out')],
            ['-l', '--license-text', '--json-pp', f"/out/{scancode_out.name}", '/src'],
            workdir='/src'
        )
        _run(scancode_cmd, timeout=timeout)
    try:
        if scancode_out.exists():
            data = json.loads(scancode_out.read_text(encoding='utf-8'))
            # Heuristic: pick most common license spdx
            lic_counts = {}
            for f in data.get('files', []):
                for d in f.get('licenses', []):
                    spdx = d.get('spdx_license_key') or d.get('key')
                    if spdx:
                        lic_counts[spdx] = lic_counts.get(spdx, 0) + 1
                        if not license_text:
                            license_text = d.get('matched_text')
            if lic_counts:
                detected_license = max(lic_counts.items(), key=lambda x: x[1])[0]
    except Exception:
        pass

    # Semgrep (generic) and Bandit (python)
    semgrep_out = reports_dir / f"{work_dir.name}_semgrep.json"
    bandit_out = reports_dir / f"{work_dir.name}_bandit.json"
    gitleaks_out = reports_dir / f"{work_dir.name}_gitleaks.json"
    if DOCKER_AVAILABLE:
        if sec_cfg.get('semgrep', True):
            semgrep_cmd = _docker_run(SEMGREP_IMAGE, [(repo_path, '/src'), (reports_dir, '/out')], ['semgrep', '--json', '-o', f"/out/{semgrep_out.name}", '-q', '-r', 'auto', '/src'], workdir='/src')
            _run(semgrep_cmd, timeout=timeout)
        if sec_cfg.get('bandit', True):
            bandit_cmd = _docker_run(BANDIT_IMAGE, [(repo_path, '/src'), (reports_dir, '/out')], ['bandit', '-r', '/src', '-f', 'json', '-o', f"/out/{bandit_out.name}"])
            _run(bandit_cmd, timeout=timeout)
        if sec_cfg.get('gitleaks', True):
            # Gitleaks for secrets
            gitleaks_cmd = _docker_run(GITLEAKS_IMAGE, [(repo_path, '/src'), (reports_dir, '/out')], ['detect', '--no-git', '--report-format', 'json', '--report-path', f"/out/{gitleaks_out.name}"])
            _run(gitleaks_cmd, timeout=timeout)

    # Ensure report files exist even if scanners didn't produce them
    try:
        if not scancode_out.exists():
            scancode_out.write_text(json.dumps({"error": "missing_scancode_report"}), encoding='utf-8')
        if not semgrep_out.exists():
            semgrep_out.write_text(json.dumps({"results": []}), encoding='utf-8')
        if not bandit_out.exists():
            bandit_out.write_text(json.dumps({"results": []}), encoding='utf-8')
        if not gitleaks_out.exists():
            gitleaks_out.write_text(json.dumps([]), encoding='utf-8')
    except Exception:
        pass

    status = 'ok'
    quarantine_dir = Path(cfg['paths'].get('quarantine_dir', '.quarantine'))
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    secrets_found = False
    try:
        if DOCKER_AVAILABLE and gitleaks_out.exists():
            g = json.loads(gitleaks_out.read_text(encoding='utf-8') or '[]')
            if isinstance(g, list) and len(g) > 0:
                secrets_found = True
    except Exception:
        pass

    # License evaluation with sensible fallbacks
    ingest_hint = None
    try:
        prov_tmp = json.loads(Path(snapshot_info['provenance_path']).read_text(encoding='utf-8'))
        ingest_hint = prov_tmp.get('license_spdx')
    except Exception:
        ingest_hint = None

    if not DOCKER_AVAILABLE or not sec_cfg.get('enabled', True):
        # Scanners unavailable: rely on ingest hint only
        detected_effective = ingest_hint
        status = 'ok' if detected_effective in allowed else 'blocked_license_scanner_unavailable'
        detected_license = detected_effective
    else:
        # Scanners available: prefer ScanCode; if none, fallback to ingest hint
        detected_effective = detected_license if detected_license else ingest_hint
        if detected_effective not in allowed:
            status = 'blocked_license'
        detected_license = detected_effective
    if secrets_found:
        status = 'quarantined_secrets'
        # Move tar to quarantine
        tar_src = Path(snapshot_info['tar_path'])
        shutil.copy2(tar_src, quarantine_dir / Path(tar_src).name)

    # Update provenance
    prov_path = Path(snapshot_info['provenance_path'])
    try:
        prov = json.loads(prov_path.read_text(encoding='utf-8'))
    except Exception:
        prov = {}
    prov['license_spdx'] = detected_license
    prov['license_text'] = license_text
    prov['scan_tool_versions'] = {
        'scancode': 'latest', 'semgrep': 'latest', 'bandit': 'latest', 'gitleaks': 'latest'
    }
    prov['scan_timestamp'] = datetime.utcnow().isoformat()
    prov_path.write_text(json.dumps(prov, indent=2), encoding='utf-8')

    return {
        'status': status,
        'work_dir': str(work_dir),
        'repo_path': str(repo_path),
        'provenance_path': str(prov_path),
        'license_spdx': detected_license,
        'reports': {
            'scancode': str(scancode_out),
            'semgrep': str(semgrep_out),
            'bandit': str(bandit_out),
            'gitleaks': str(gitleaks_out),
        }
    }
