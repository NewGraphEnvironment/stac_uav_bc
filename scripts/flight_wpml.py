#!/usr/bin/env python3
# Read and write DJI WPML flight plans (.kmz) for the Mini 4 Pro (#26).
#
# A WPML mission is a zip of two files: wpmz/template.kml (mission config only --
# Map Pilot writes a stub with no polygon, which is why a flown boundary can never
# be recovered from an export) and wpmz/waylines.wpml (the waypoints the aircraft
# actually flies). This module is the reader/writer for both; the geometry that
# decides where the waypoints go lives in flight_coverage.py.
#
# Round-trip fidelity is the contract: parsing a real Map Pilot export and
# re-emitting it must reproduce it exactly, apart from the timestamps. That is
# what makes a generated mission trustworthy -- the writer is proven against
# known-good files before it is asked to invent one. Action groups are preserved
# verbatim on read rather than modelled, so an action this module does not
# understand still survives a round trip.
#
# Self-test (the gate; non-zero exit on any mismatch):
#   conda run -n dff python scripts/flight_wpml.py --roundtrip ~/Downloads/*.kmz
#
# Usage as a library:
#   from flight_wpml import Mission, Waypoint, read_kmz, write_kmz
#   m = read_kmz("/Users/airvine/Downloads/myKMZ-3.kmz")
#   write_kmz(m, "/tmp/out.kmz")
import argparse
import dataclasses
import pathlib
import re
import sys
import zipfile

# Observed constant across all five Map Pilot exports measured 2026-09-26. Kept as
# named constants so a generated mission matches what has actually flown, and so a
# future change is a visible diff rather than a silent drift.
HEADING_MODE = "followWayline"
TURN_MODE = "toPointAndStopWithDiscontinuityCurvature"
TURN_DAMPING = "1"
GIMBAL_PITCH = "-85"
TRANSITIONAL_SPEED = "9.5"
HEIGHT_MODE = "relativeToStartPoint"
FINISH_ACTION = "goHome"

# droneEnumValue 68 is what Map Pilot writes for the Mini 4 Pro. It is NOT in DJI's
# documented drone table (60/67/77/89/91) -- 68 is the Mavic 3M *payload* enum. The
# aircraft evidently accepts it, since these missions flew. Recorded as
# observed-not-understood (#26 open question); do not "correct" it without testing.
DRONE_ENUM = "68"
DRONE_SUB_ENUM = "0"

XML_DECL = '<?xml version="1.0" encoding="utf-8" standalone="no"?>'
KML_OPEN = ('<kml xmlns="http://www.opengis.net/kml/2.2" '
            'xmlns:wpml="http://www.uav.com/wpmz/1.0.2">')

T = "\t"


@dataclasses.dataclass
class Waypoint:
    lon: float
    lat: float
    height: float
    speed: float
    # Raw <wpml:actionGroup> blocks, tab-indented as they appear in the file. Held
    # as text so a round trip cannot lose an action this module does not model.
    action_xml: list = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Mission:
    waypoints: list
    auto_speed: float
    height_mode: str = HEIGHT_MODE
    finish_action: str = FINISH_ACTION
    takeoff_security_height: str = "300"
    transitional_speed: str = TRANSITIONAL_SPEED
    drone_enum: str = DRONE_ENUM
    drone_sub_enum: str = DRONE_SUB_ENUM
    distance: float = 0.0
    # Map Pilot writes 200.324 here in EVERY export regardless of mission -- it is a
    # constant, not a duration (measured across all five, #26). Carried only so a
    # round trip reproduces the source byte for byte. NEVER read it as a time; the
    # budget model computes time from distance and speed (flight_budget.py).
    duration: str = "200.324"
    template_author: str = "926894357355016192"
    template_create_time: str = "1790086802"
    template_update_time: str = "1790086802"
    template_takeoff_security_height: str = "20"


def _tag(text, name):
    m = re.search(rf"<wpml:{name}>([^<]*)</wpml:{name}>", text)
    return m.group(1) if m else None


def read_kmz(path):
    """Parse a WPML .kmz into a Mission. Action groups are preserved verbatim."""
    with zipfile.ZipFile(path) as z:
        wpml = z.read("wpmz/waylines.wpml").decode("utf-8")
        try:
            template = z.read("wpmz/template.kml").decode("utf-8")
        except KeyError:
            template = ""

    waypoints = []
    for pm in re.findall(r"<Placemark>.*?</Placemark>", wpml, re.S):
        coords = re.search(r"<coordinates>([^<]+)</coordinates>", pm)
        lon, lat = (float(v) for v in coords.group(1).split(",")[:2])
        waypoints.append(Waypoint(
            lon=lon, lat=lat,
            height=float(_tag(pm, "executeHeight")),
            speed=float(_tag(pm, "waypointSpeed")),
            action_xml=re.findall(r"\t+<wpml:actionGroup>.*?</wpml:actionGroup>", pm, re.S),
        ))

    m = Mission(
        waypoints=waypoints,
        auto_speed=float(_tag(wpml, "autoFlightSpeed")),
        height_mode=_tag(wpml, "executeHeightMode") or HEIGHT_MODE,
        finish_action=_tag(wpml, "finishAction") or FINISH_ACTION,
        takeoff_security_height=_tag(wpml, "takeOffSecurityHeight") or "300",
        transitional_speed=_tag(wpml, "globalTransitionalSpeed") or TRANSITIONAL_SPEED,
        drone_enum=_tag(wpml, "droneEnumValue") or DRONE_ENUM,
        drone_sub_enum=_tag(wpml, "droneSubEnumValue") or DRONE_SUB_ENUM,
        distance=float(_tag(wpml, "distance") or 0.0),
        duration=_tag(wpml, "duration") or "200.324",
    )
    if template:
        m.template_author = _tag(template, "author") or m.template_author
        m.template_create_time = _tag(template, "createTime") or m.template_create_time
        m.template_update_time = _tag(template, "updateTime") or m.template_update_time
        m.template_takeoff_security_height = (
            _tag(template, "takeOffSecurityHeight") or m.template_takeoff_security_height)
    return m


def _mission_config(m, indent, takeoff_height):
    i = T * indent
    return "\n".join([
        f"{i}<wpml:missionConfig>",
        f"{i}{T}<wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>",
        f"{i}{T}<wpml:finishAction>{m.finish_action}</wpml:finishAction>",
        f"{i}{T}<wpml:exitOnRCLost>executeLostAction</wpml:exitOnRCLost>",
        f"{i}{T}<wpml:executeRCLostAction>goBack</wpml:executeRCLostAction>",
        f"{i}{T}<wpml:takeOffSecurityHeight>{takeoff_height}</wpml:takeOffSecurityHeight>",
        f"{i}{T}<wpml:globalTransitionalSpeed>{m.transitional_speed}</wpml:globalTransitionalSpeed>",
        f"{i}{T}<wpml:droneInfo>",
        f"{i}{T}{T}<wpml:droneEnumValue>{m.drone_enum}</wpml:droneEnumValue>",
        f"{i}{T}{T}<wpml:droneSubEnumValue>{m.drone_sub_enum}</wpml:droneSubEnumValue>",
        f"{i}{T}</wpml:droneInfo>",
        f"{i}</wpml:missionConfig>",
    ])


def render_template_kml(m):
    """The stub Map Pilot writes: mission config only, no Folder, no polygon."""
    return "\n".join([
        XML_DECL, KML_OPEN,
        f"{T}<Document>",
        f"{T}{T}<wpml:author>{m.template_author}</wpml:author>",
        f"{T}{T}<wpml:createTime>{m.template_create_time}</wpml:createTime>",
        f"{T}{T}<wpml:updateTime>{m.template_update_time}</wpml:updateTime>",
        _mission_config(m, 2, m.template_takeoff_security_height),
        f"{T}</Document>",
        "</kml>",
    ])  # no trailing newline: Map Pilot's files end at "</kml>" (measured on all five)


def render_waylines(m):
    out = [
        XML_DECL, KML_OPEN,
        f"{T}<Document>",
        _mission_config(m, 2, m.takeoff_security_height),
        f"{T}{T}<Folder>",
        f"{T}{T}{T}<wpml:templateId>0</wpml:templateId>",
        f"{T}{T}{T}<wpml:executeHeightMode>{m.height_mode}</wpml:executeHeightMode>",
        f"{T}{T}{T}<wpml:waylineId>0</wpml:waylineId>",
        f"{T}{T}{T}<wpml:autoFlightSpeed>{_num(m.auto_speed)}</wpml:autoFlightSpeed>",
        f"{T}{T}{T}<wpml:distance>{m.distance}</wpml:distance>",
        f"{T}{T}{T}<wpml:duration>{m.duration}</wpml:duration>",
    ]
    for idx, w in enumerate(m.waypoints):
        out.append(f"{T}{T}{T}<Placemark>")
        out.append(f"{T}{T}{T}{T}<Point>")
        out.append(f"{T}{T}{T}{T}{T}<coordinates>{w.lon:.6f},{w.lat:.6f}</coordinates>")
        out.append(f"{T}{T}{T}{T}</Point>")
        out.append(f"{T}{T}{T}{T}<wpml:index>{idx}</wpml:index>")
        out.append(f"{T}{T}{T}{T}<wpml:executeHeight>{w.height:.1f}</wpml:executeHeight>")
        out.append(f"{T}{T}{T}{T}<wpml:waypointSpeed>{w.speed:.2f}</wpml:waypointSpeed>")
        out.append(f"{T}{T}{T}{T}<wpml:waypointHeadingParam>")
        out.append(f"{T}{T}{T}{T}{T}<wpml:waypointHeadingMode>{HEADING_MODE}</wpml:waypointHeadingMode>")
        out.append(f"{T}{T}{T}{T}{T}<wpml:waypointHeadingAngle>0</wpml:waypointHeadingAngle>")
        out.append(f"{T}{T}{T}{T}{T}<wpml:waypointPoiPoint>0.000,0.0000,0.000</wpml:waypointPoiPoint>")
        out.append(f"{T}{T}{T}{T}{T}<wpml:waypointHeadingAngleEnable>0</wpml:waypointHeadingAngleEnable>")
        out.append(f"{T}{T}{T}{T}</wpml:waypointHeadingParam>")
        out.append(f"{T}{T}{T}{T}<wpml:waypointTurnParam>")
        out.append(f"{T}{T}{T}{T}{T}<wpml:waypointTurnMode>{TURN_MODE}</wpml:waypointTurnMode>")
        out.append(f"{T}{T}{T}{T}{T}<wpml:waypointTurnDampingDist>{TURN_DAMPING}</wpml:waypointTurnDampingDist>")
        out.append(f"{T}{T}{T}{T}</wpml:waypointTurnParam>")
        out.append(f"{T}{T}{T}{T}<wpml:useStraightLine>1</wpml:useStraightLine>")
        out.extend(w.action_xml)
        out.append(f"{T}{T}{T}</Placemark>")
    out.append(f"{T}{T}</Folder>")
    out.append(f"{T}</Document>")
    out.append("</kml>")
    return "\n".join(out)  # see render_template_kml: no trailing newline


def _num(v):
    """Map Pilot writes autoFlightSpeed as a bare integer when it is one."""
    return str(int(v)) if float(v).is_integer() else str(v)


def gimbal_action(group_id=0, start=0, end=1, mode="parallel", indent=4):
    i = T * indent
    return "\n".join([
        f"{i}<wpml:actionGroup>",
        f"{i}{T}<wpml:actionGroupId>{group_id}</wpml:actionGroupId>",
        f"{i}{T}<wpml:actionGroupStartIndex>{start}</wpml:actionGroupStartIndex>",
        f"{i}{T}<wpml:actionGroupEndIndex>{end}</wpml:actionGroupEndIndex>",
        f"{i}{T}<wpml:actionGroupMode>{mode}</wpml:actionGroupMode>",
        f"{i}{T}<wpml:actionTrigger>",
        f"{i}{T}{T}<wpml:actionTriggerType>betweenAdjacentPoints</wpml:actionTriggerType>",
        f"{i}{T}</wpml:actionTrigger>",
        f"{i}{T}<wpml:action>",
        f"{i}{T}{T}<wpml:actionId>0</wpml:actionId>",
        f"{i}{T}{T}<wpml:actionActuatorFunc>gimbalEvenlyRotate</wpml:actionActuatorFunc>",
        f"{i}{T}{T}<wpml:actionActuatorFuncParam>",
        f"{i}{T}{T}{T}<wpml:gimbalPitchRotateAngle>{GIMBAL_PITCH}</wpml:gimbalPitchRotateAngle>",
        f"{i}{T}{T}{T}<wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>",
        f"{i}{T}{T}</wpml:actionActuatorFuncParam>",
        f"{i}{T}</wpml:action>",
        f"{i}</wpml:actionGroup>",
    ])


def photo_action(group_id=0, index=0, mode="parallel", indent=4):
    i = T * indent
    return "\n".join([
        f"{i}<wpml:actionGroup>",
        f"{i}{T}<wpml:actionGroupId>{group_id}</wpml:actionGroupId>",
        f"{i}{T}<wpml:actionGroupStartIndex>{index}</wpml:actionGroupStartIndex>",
        f"{i}{T}<wpml:actionGroupEndIndex>{index}</wpml:actionGroupEndIndex>",
        f"{i}{T}<wpml:actionGroupMode>{mode}</wpml:actionGroupMode>",
        f"{i}{T}<wpml:actionTrigger>",
        f"{i}{T}{T}<wpml:actionTriggerType>reachPoint</wpml:actionTriggerType>",
        f"{i}{T}</wpml:actionTrigger>",
        f"{i}{T}<wpml:action>",
        f"{i}{T}{T}<wpml:actionId>0</wpml:actionId>",
        f"{i}{T}{T}<wpml:actionActuatorFunc>takePhoto</wpml:actionActuatorFunc>",
        f"{i}{T}{T}<wpml:actionActuatorFuncParam>",
        f"{i}{T}{T}{T}<wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>",
        f"{i}{T}{T}</wpml:actionActuatorFuncParam>",
        f"{i}{T}</wpml:action>",
        f"{i}</wpml:actionGroup>",
    ])


def write_kmz(mission, path):
    """Write a Mission as a .kmz. Overwrites; re-running is safe and cheap."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("wpmz/template.kml", render_template_kml(mission))
        z.writestr("wpmz/waylines.wpml", render_waylines(mission))
    return path


def _roundtrip(paths):
    """Re-emit each fixture and diff against the original. This is the gate."""
    failed = 0
    for p in paths:
        p = pathlib.Path(p)
        try:
            with zipfile.ZipFile(p) as z:
                original = z.read("wpmz/waylines.wpml").decode("utf-8")
                original_tpl = z.read("wpmz/template.kml").decode("utf-8")
        except (zipfile.BadZipFile, KeyError) as e:
            print(f"FAIL  {p.name}: not a WPML kmz ({e})")
            failed += 1
            continue
        mission = read_kmz(p)
        emitted = render_waylines(mission)
        # write_kmz emits BOTH files, so both must be checked. Gating only the
        # waylines left half of what is written unverified.
        emitted_tpl = render_template_kml(mission)
        if emitted_tpl != original_tpl:
            failed += 1
            print(f"FAIL  {p.name}: template.kml differs "
                  f"({len(original_tpl)} chars original, {len(emitted_tpl)} emitted)")
            for n, (a, b) in enumerate(zip(original_tpl.splitlines(),
                                           emitted_tpl.splitlines()), 1):
                if a != b:
                    print(f"        line {n}:\n          orig: {a!r}\n          emit: {b!r}")
                    break
            continue
        if emitted == original:
            print(f"PASS  {p.name}  ({original.count('<Placemark>')} waypoints, exact)")
            continue
        failed += 1
        print(f"FAIL  {p.name}")
        o, e = original.splitlines(), emitted.splitlines()
        if len(o) != len(e):
            print(f"        line count {len(o)} original vs {len(e)} emitted")
        shown = 0
        for n, (a, b) in enumerate(zip(o, e), 1):
            if a != b:
                print(f"        line {n}:\n          orig: {a!r}\n          emit: {b!r}")
                shown += 1
                if shown >= 3:
                    print("        (further differences suppressed)")
                    break
        if not shown and len(o) == len(e):
            # The strings differ but every line matches, so the difference is in
            # bytes splitlines() discards -- a trailing newline is the usual one.
            # Without this arm the detector fires and the explainer prints nothing,
            # which reads as a broken gate rather than a real finding.
            print(f"        every line matches; differs in trailing bytes only")
            print(f"          orig ends: {original[-24:]!r} ({len(original)} chars)")
            print(f"          emit ends: {emitted[-24:]!r} ({len(emitted)} chars)")
    print()
    sys.stdout.flush()
    if failed:
        print(f"ROUNDTRIP FAILED: {failed} of {len(paths)} fixture(s)", file=sys.stderr)
        return 1
    print(f"ROUNDTRIP PASS: {len(paths)} fixture(s) re-emitted exactly")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--roundtrip", nargs="+", metavar="KMZ",
                    help="re-emit each .kmz and diff against the original (gate)")
    args = ap.parse_args()
    if not args.roundtrip:
        ap.error("nothing to do — pass --roundtrip with one or more .kmz paths")
    return _roundtrip(args.roundtrip)


if __name__ == "__main__":
    sys.exit(main())
