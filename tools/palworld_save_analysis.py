#!/usr/bin/env python3

import argparse
import contextlib
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

CURRENT_DIR = Path(__file__).resolve().parent
VENDOR_DIR = CURRENT_DIR / "palworld_save_tools"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

from palworld_save_tools.gvas import GvasFile  # type: ignore
from palworld_save_tools.json_tools import CustomEncoder  # type: ignore
from palworld_save_tools.palsav import decompress_sav_to_gvas  # type: ignore
from palworld_save_tools.paltypes import (  # type: ignore
    DISABLED_PROPERTIES,
    PALWORLD_CUSTOM_PROPERTIES,
    PALWORLD_TYPE_HINTS,
)
from palworld_save_edit import (  # type: ignore
    apply_guild_update,
    apply_player_update,
    load_payload_file,
    read_world_option,
    write_world_option,
)

PLAYER_ITEM_GROUP_KEYS = [
    "CommonContainerId",
    "DropSlotContainerId",
    "EssentialContainerId",
    "FoodEquipContainerId",
    "PlayerEquipArmorContainerId",
    "WeaponLoadOutContainerId",
]

STATUS_POINT_NAME_MAP = {
    "最大HP": "hp",
    "最大SP": "stamina",
    "攻撃力": "attack",
    "所持重量": "weight",
    "作業速度": "workSpeed",
}


def build_custom_properties() -> dict[str, Any]:
    return {
        key: value
        for key, value in PALWORLD_CUSTOM_PROPERTIES.items()
        if key not in DISABLED_PROPERTIES
    }


def load_sav_properties(file_path: Path) -> dict[str, Any]:
    with open(file_path, "rb") as f:
        compressed = f.read()
    raw_gvas, _ = decompress_sav_to_gvas(compressed)
    with contextlib.redirect_stdout(sys.stderr):
        gvas = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, build_custom_properties())
    return simplify(gvas.properties)


def simplify(node: Any) -> Any:
    if isinstance(node, dict):
        if "type" in node and "value" in node:
            node_type = node.get("type")
            value = node.get("value")
            if node_type == "StructProperty":
                return simplify(value)
            if node_type == "ArrayProperty":
                if isinstance(value, dict) and "values" in value:
                    return [simplify(item) for item in value.get("values", [])]
                return simplify(value)
            if node_type == "MapProperty":
                return [
                    {
                        "key": simplify(entry.get("key")),
                        "value": simplify(entry.get("value")),
                    }
                    for entry in value or []
                ]
            if node_type in ("EnumProperty", "ByteProperty"):
                if isinstance(value, dict) and "value" in value:
                    return simplify(value.get("value"))
                return simplify(value)
            return simplify(value)
        return {key: simplify(value) for key, value in node.items() if key not in {"id", "struct_id"}}
    if isinstance(node, list):
        return [simplify(item) for item in node]
    if hasattr(node, "__class__") and node.__class__.__name__ == "UUID":
        return str(node)
    return node


def first_value(node: Any, keys: list[str] | tuple[str, ...]) -> Any:
    lowered = {str(key).lower() for key in keys}
    return _first_value(node, lowered)


def _first_value(node: Any, lowered_keys: set[str]) -> Any:
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in lowered_keys:
                return value
        for value in node.values():
            result = _first_value(value, lowered_keys)
            if result is not None:
                return result
    elif isinstance(node, list):
        for item in node:
            result = _first_value(item, lowered_keys)
            if result is not None:
                return result
    return None


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        for key in ("value", "Value", "guid", "Guid", "ID", "id", "static_id", "StaticId"):
            if key in value:
                result = as_text(value[key])
                if result:
                    return result
        for nested in value.values():
            result = as_text(nested)
            if result:
                return result
        return ""
    if isinstance(value, list):
        for item in value:
            result = as_text(item)
            if result:
                return result
        return ""
    return str(value)


def normalize_uid_text(value: Any) -> str:
    text = as_text(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    if re.fullmatch(r"[0-9a-f]{32}", lowered):
        return (
            f"{lowered[0:8]}-{lowered[8:12]}-{lowered[12:16]}-"
            f"{lowered[16:20]}-{lowered[20:32]}"
        )
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", lowered):
        return lowered
    return ""


def is_invalid_display_text(value: str) -> bool:
    if not value:
        return True
    if "\ufffd" in value:
        return True
    if any(ord(char) < 32 and char not in {"\t", "\n", "\r"} for char in value):
        return True
    return False


def normalize_display_text(value: Any) -> str:
    text = as_text(value).replace("\x00", "").strip()
    if is_invalid_display_text(text):
        return ""
    return text


def first_valid_display_text(*values: Any) -> str:
    for value in values:
        text = normalize_display_text(value)
        if text:
            return text
    return ""


def as_number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return value
    if isinstance(value, str):
        try:
            return float(value) if "." in value else int(value)
        except Exception:
            return None
    if isinstance(value, dict):
        for key in ("Value", "value", "Current", "current"):
            if key in value:
                result = as_number(value[key])
                if result is not None:
                    return result
        for nested in value.values():
            result = as_number(nested)
            if result is not None:
                return result
        return None
    if isinstance(value, list):
        for item in value:
            result = as_number(item)
            if result is not None:
                return result
        return None
    return None


def as_int(value: Any, default: int = 0) -> int:
    number = as_number(value)
    return default if number is None else int(number)


def as_float(value: Any, default: float = 0.0) -> float:
    number = as_number(value)
    return default if number is None else float(number)


def ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def parse_timestamp(value: Any, *, not_after: dt.datetime | None = None) -> str:
    raw = as_number(value)
    if raw is None:
        return ""
    try:
        if raw > 10**15:
            timestamp = float(raw) / 10000000 - 11644473600
        elif raw > 10**12:
            timestamp = float(raw) / 1000
        elif raw > 10**9:
            timestamp = float(raw)
        else:
            return ""
        parsed = dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc)
        if not_after and parsed > not_after:
            return ""
        return parsed.isoformat()
    except Exception:
        return ""


def file_mtime_iso(file_path: Path) -> str:
    return dt.datetime.fromtimestamp(file_path.stat().st_mtime, tz=dt.timezone.utc).isoformat()


def extract_translation(value: Any) -> dict[str, float]:
    transform = value if isinstance(value, dict) else {}
    translation = {}
    if isinstance(transform, dict):
        translation = transform.get("translation") or transform.get("Translation") or {}
    if not isinstance(translation, dict):
        return {}
    if not any(key in translation for key in ("x", "X", "y", "Y", "z", "Z")):
        return {}
    return {
        "x": as_float(translation.get("x") if "x" in translation else translation.get("X")),
        "y": as_float(translation.get("y") if "y" in translation else translation.get("Y")),
        "z": as_float(translation.get("z") if "z" in translation else translation.get("Z")),
    }


def normalize_item_slot(slot: Any, fallback_index: int) -> dict[str, Any] | None:
    raw_data = slot.get("RawData") if isinstance(slot, dict) else {}
    static_id = as_text(
        first_value(raw_data, ("static_id", "StaticId"))
        or first_value(slot, ("StaticId", "static_id", "ItemId", "item_id"))
    )
    stack_count = as_int(
        first_value(raw_data, ("count", "Count"))
        or first_value(slot, ("StackCount", "num")),
        0,
    )
    slot_index = as_int(
        first_value(raw_data, ("slot_index", "SlotIndex"))
        or first_value(slot, ("SlotIndex",)),
        fallback_index,
    )
    if not static_id and stack_count <= 0:
        return None
    return {
        "slotIndex": slot_index,
        "itemId": static_id,
        "stackCount": stack_count,
    }


def extract_item_container_slots(container_value: Any) -> list[dict[str, Any]]:
    slots_root = None
    if isinstance(container_value, dict):
        slots_root = container_value.get("Slots")
        if isinstance(slots_root, dict) and "Slots" in slots_root:
            slots_root = slots_root.get("Slots")
    slots = []
    for index, slot in enumerate(ensure_list(slots_root)):
        normalized = normalize_item_slot(slot, index)
        if normalized:
            slots.append(normalized)
    return slots


def extract_character_container_slots(container_value: Any) -> list[dict[str, Any]]:
    slots_root = None
    if isinstance(container_value, dict):
        slots_root = container_value.get("Slots")
        if isinstance(slots_root, dict) and "Slots" in slots_root:
            slots_root = slots_root.get("Slots")
    result = []
    for index, slot in enumerate(ensure_list(slots_root)):
        raw_data = slot.get("RawData") if isinstance(slot, dict) else {}
        instance_id = as_text(first_value(raw_data, ("instance_id", "InstanceId")))
        player_uid = as_text(first_value(raw_data, ("player_uid", "PlayerUId")))
        if not instance_id:
            continue
        result.append(
            {
                "slotIndex": as_int(first_value(slot, ("SlotIndex",)), index),
                "instanceId": instance_id,
                "playerUid": player_uid,
                "permissionTribeId": as_int(first_value(raw_data, ("permission_tribe_id",)), 0),
            }
        )
    return result


def extract_container_id(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("ID", "Id", "id"):
            if key in value:
                result = as_text(value[key])
                if result:
                    return result
    return as_text(value)


def parse_player_save(player_file: Path) -> dict[str, Any]:
    properties = load_sav_properties(player_file)
    save_data = properties.get("SaveData", {})
    inventory_info = first_value(save_data, ("inventoryInfo", "InventoryInfo")) or {}
    result = {
        "playerUid": as_text(first_value(save_data, ("PlayerUId", "PlayerUID"))),
        "steamId": as_text(
            first_value(
                save_data,
                ("SteamId", "steamId", "LoginPlayerId", "PlatformPlayerId", "UserId"),
            )
        ),
        "otomoContainerId": extract_container_id(
            first_value(save_data, ("OtomoCharacterContainerId", "OtomoPalContainerId"))
        ),
        "palStorageContainerId": extract_container_id(
            first_value(save_data, ("PalStorageContainerId", "PalContainerId"))
        ),
        "lastOnline": parse_timestamp(
            first_value(save_data, ("LastOnlineRealTime", "last_online_real_time"))
        ),
        "lastTransform": extract_translation(
            first_value(save_data, ("LastTransform", "Transform")) or {}
        ),
        "inventory": {},
    }
    for key in PLAYER_ITEM_GROUP_KEYS:
        result["inventory"][key] = extract_container_id(first_value(inventory_info, (key,)))
    return result


def get_status_point_entries(property_node: Any) -> list[dict[str, Any]]:
    if isinstance(property_node, list):
        return [item for item in property_node if isinstance(item, dict)]
    if isinstance(property_node, dict) and "StatusName" in property_node and "StatusPoint" in property_node:
        return [property_node]
    if not isinstance(property_node, dict) or property_node.get("type") != "ArrayProperty":
        return []
    value = property_node.get("value")
    if isinstance(value, dict):
        nested_values = value.get("values")
        if isinstance(nested_values, list):
            return [item for item in nested_values if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def parse_status_point_totals(save_parameter: dict[str, Any]) -> tuple[dict[str, int], bool]:
    totals = {
        "hp": 0,
        "stamina": 0,
        "attack": 0,
        "workSpeed": 0,
        "weight": 0,
    }
    found_any = False
    for prop_name in ("GotStatusPointList", "GotExStatusPointList"):
        entries = get_status_point_entries(save_parameter.get(prop_name))
        if not entries:
            continue
        found_any = True
        for item in entries:
            status_name = as_text(item.get("StatusName"))
            target_key = STATUS_POINT_NAME_MAP.get(status_name)
            if not target_key:
                continue
            totals[target_key] += as_int(item.get("StatusPoint"), 0)
    return totals, found_any


def normalize_status_points(save_parameter: dict[str, Any]) -> dict[str, int]:
    result = {
        "unused": as_int(first_value(save_parameter, ("UnusedStatusPoint", "RemainStatusPoint")), 0),
        "hp": as_int(first_value(save_parameter, ("AddMaxHP", "AddHP")), 0),
        "stamina": as_int(first_value(save_parameter, ("AddMaxSP", "AddSP")), 0),
        "attack": as_int(first_value(save_parameter, ("AddAttack", "AddMeleeAttack")), 0),
        "workSpeed": as_int(first_value(save_parameter, ("AddWorkSpeed",)), 0),
        "weight": as_int(first_value(save_parameter, ("AddMaxWeight",)), 0),
    }
    totals, has_status_lists = parse_status_point_totals(save_parameter)
    if has_status_lists:
        result["hp"] = totals["hp"]
        result["stamina"] = totals["stamina"]
        result["attack"] = totals["attack"]
        result["workSpeed"] = totals["workSpeed"]
        result["weight"] = totals["weight"]
    return result


def normalize_pal(entry: dict[str, Any], owner_player_uid: str) -> dict[str, Any]:
    raw_data = (entry.get("value") or {}).get("RawData") or {}
    raw_object = raw_data.get("object") or {}
    save_parameter = raw_object.get("SaveParameter") or {}
    individual_id = save_parameter.get("IndividualId") or {}
    instance_id = as_text(individual_id.get("InstanceId")) or as_text(first_value(entry.get("key"), ("InstanceId",)))
    hp = as_int(first_value(save_parameter, ("HP", "Hp")), 0)
    max_hp = as_int(first_value(save_parameter, ("MaxHP", "MaxHp")), 0)
    passive_skills = [as_text(item) for item in ensure_list(save_parameter.get("PassiveSkillList")) if as_text(item)]
    active_skills = [as_text(item) for item in ensure_list(save_parameter.get("EquipWaza")) if as_text(item)]
    active_skills.extend(
        [as_text(item) for item in ensure_list(save_parameter.get("MasteredWaza")) if as_text(item)]
    )
    dedup_active_skills = list(dict.fromkeys(active_skills))
    return {
        "instanceId": instance_id,
        "ownerPlayerUid": owner_player_uid,
        "nickname": first_valid_display_text(first_value(save_parameter, ("NickName", "Nickname"))),
        "characterId": as_text(first_value(save_parameter, ("CharacterID", "CharacterId"))),
        "containerType": "storage",
        "level": as_int(first_value(save_parameter, ("Level",)), 0),
        "exp": as_int(first_value(save_parameter, ("Exp",)), 0),
        "hp": hp,
        "maxHp": max_hp or hp,
        "gender": as_text(first_value(save_parameter, ("Gender",))),
        "rank": as_int(first_value(save_parameter, ("Rank",)), 0),
        "rankAttack": as_int(first_value(save_parameter, ("RankAttack", "Rank_Attack")), 0),
        "rankDefense": as_int(first_value(save_parameter, ("RankDefence", "RankDefense", "Rank_Defense")), 0),
        "rankCraftSpeed": as_int(
            first_value(save_parameter, ("RankCraftspeed", "RankCraftSpeed", "Rank_CraftSpeed")),
            0,
        ),
        "melee": as_int(first_value(save_parameter, ("Talent_HP", "TalentHp", "TalentMelee", "Melee")), 0),
        "ranged": as_int(first_value(save_parameter, ("Talent_Shot", "TalentShot", "Ranged")), 0),
        "defense": as_int(first_value(save_parameter, ("Talent_Defense", "TalentDefense", "Defense")), 0),
        "workSpeed": as_int(
            first_value(save_parameter, ("CraftSpeed", "TalentCraftSpeed", "Talent_WorkSpeed", "WorkSpeed")),
            0,
        ),
        "isBoss": bool(first_value(save_parameter, ("IsBoss",))),
        "isLucky": bool(first_value(save_parameter, ("IsRarePal", "IsLucky",))),
        "isTower": bool(first_value(save_parameter, ("IsTowerBoss", "IsTower",))),
        "skills": passive_skills,
        "passiveSkills": passive_skills,
        "activeSkills": dedup_active_skills,
    }


def build_analysis(level_path: Path, players_dir: Path | None) -> dict[str, Any]:
    properties = load_sav_properties(level_path)
    world_save = properties.get("worldSaveData", {})
    level_mtime = dt.datetime.fromtimestamp(level_path.stat().st_mtime, tz=dt.timezone.utc)

    player_files: dict[str, dict[str, Any]] = {}
    if players_dir and players_dir.exists():
        for player_file in sorted(players_dir.glob("*.sav")):
            parsed = parse_player_save(player_file)
            player_uid = parsed.get("playerUid") or player_file.stem
            if player_uid:
                player_files[player_uid] = parsed

    item_containers: dict[str, list[dict[str, Any]]] = {}
    for entry in ensure_list(world_save.get("ItemContainerSaveData")):
        container_id = as_text(entry.get("key"))
        if container_id:
            item_containers[container_id] = extract_item_container_slots(entry.get("value"))

    character_containers: dict[str, list[dict[str, Any]]] = {}
    for entry in ensure_list(world_save.get("CharacterContainerSaveData")):
        container_id = as_text(entry.get("key"))
        if container_id:
            character_containers[container_id] = extract_character_container_slots(entry.get("value"))

    base_camps_by_group: dict[str, list[dict[str, Any]]] = {}
    for entry in ensure_list(world_save.get("BaseCampSaveData")):
        raw_data = (entry.get("value") or {}).get("RawData") or {}
        group_id = as_text(raw_data.get("group_id_belong_to"))
        if not group_id:
            continue
        base_camps_by_group.setdefault(group_id, []).append(
            {
                "id": as_text(raw_data.get("id")),
                "name": as_text(raw_data.get("name")),
                "areaRange": as_float(raw_data.get("area_range"), 0),
                "location": extract_translation(raw_data.get("transform") or {}),
            }
        )

    player_map: dict[str, dict[str, Any]] = {}
    pal_map: dict[str, dict[str, Any]] = {}

    for entry in ensure_list(world_save.get("CharacterSaveParameterMap")):
        key_data = entry.get("key") or {}
        value_data = entry.get("value") or {}
        raw_data = value_data.get("RawData") or {}
        raw_object = raw_data.get("object") or {}
        save_parameter = raw_object.get("SaveParameter") or {}
        owner_player_uid = as_text(first_value(save_parameter, ("OwnerPlayerUId", "OwnerPlayerUid")))

        player_uid = as_text(
            first_value(save_parameter, ("PlayerUId", "PlayerUID"))
            or key_data.get("PlayerUId")
            or first_value(key_data, ("PlayerUId", "PlayerUID"))
        )

        is_player = bool(first_value(save_parameter, ("IsPlayer",))) or (
            not owner_player_uid and bool(player_files.get(player_uid))
        )
        if is_player:
            if not player_uid or player_uid == "00000000-0000-0000-0000-000000000000":
                continue
            player_file_info = player_files.get(player_uid, {})
            hp = as_int(first_value(save_parameter, ("HP", "Hp")), 0)
            max_hp = as_int(first_value(save_parameter, ("MaxHP", "MaxHp")), 0)
            shield_hp = as_int(first_value(save_parameter, ("ShieldHP", "ShieldHp")), 0)
            shield_max_hp = as_int(first_value(save_parameter, ("MaxShieldHP", "ShieldMaxHp")), 0)
            player_map[player_uid] = {
                "playerUid": player_uid,
                "nickname": first_valid_display_text(first_value(save_parameter, ("NickName", "Nickname"))),
                "level": as_int(first_value(save_parameter, ("Level",)), 0),
                "steamId": player_file_info.get("steamId", ""),
                "lastOnline": player_file_info.get("lastOnline", ""),
                "location": extract_translation(
                    first_value(save_parameter, ("Transform", "LastTransform")) or {}
                )
                or player_file_info.get("lastTransform", {}),
                "baseStats": {
                    "hp": hp,
                    "maxHp": max_hp or hp,
                    "shieldHp": shield_hp,
                    "shieldMaxHp": shield_max_hp or shield_hp,
                },
                "statusPoints": normalize_status_points(save_parameter),
                "maxStatusPoint": as_int(first_value(save_parameter, ("MaxStatusPoint",)), 0),
                "fullStomach": as_float(first_value(save_parameter, ("FullStomach",)), 0),
                "containers": player_file_info.get("inventory", {}),
                "otomoContainerId": player_file_info.get("otomoContainerId", ""),
                "palStorageContainerId": player_file_info.get("palStorageContainerId", ""),
                "pals": [],
                "items": {},
            }
            continue

        owner_player_uid = owner_player_uid or as_text(first_value(key_data, ("PlayerUId",)))
        if owner_player_uid:
            pal = normalize_pal(entry, owner_player_uid)
            if pal.get("instanceId"):
                pal_map[pal["instanceId"]] = pal

    for player_uid, player in player_map.items():
        for group_key in PLAYER_ITEM_GROUP_KEYS:
            container_id = as_text((player.get("containers") or {}).get(group_key))
            player["items"][group_key] = item_containers.get(container_id, []) if container_id else []

        ordered_pals = []
        seen_instance_ids = set()
        for container_id in (
            as_text(player.get("otomoContainerId")),
            as_text(player.get("palStorageContainerId")),
        ):
            container_type = (
                "otomo"
                if container_id and container_id == as_text(player.get("otomoContainerId"))
                else "storage"
            )
            for slot in character_containers.get(container_id, []):
                pal = pal_map.get(as_text(slot.get("instanceId")))
                if not pal or pal.get("instanceId") in seen_instance_ids:
                    continue
                ordered_pals.append(
                    {
                        **pal,
                        "containerType": container_type,
                    }
                )
                seen_instance_ids.add(pal["instanceId"])
        for pal in pal_map.values():
            if pal.get("ownerPlayerUid") == player_uid and pal.get("instanceId") not in seen_instance_ids:
                ordered_pals.append(pal)
        player["pals"] = ordered_pals

    guilds = []
    for entry in ensure_list(world_save.get("GroupSaveDataMap")):
        raw_data = (entry.get("value") or {}).get("RawData") or {}
        group_type = as_text(raw_data.get("group_type"))
        if group_type not in {
            "EPalGroupType::Guild",
            "EPalGroupType::IndependentGuild",
            "EPalGroupType::Organization",
        }:
            continue

        group_id = as_text(raw_data.get("group_id")) or as_text(entry.get("key"))
        guild_players = []
        for player_entry in ensure_list(raw_data.get("players")):
            player_uid = as_text(player_entry.get("player_uid"))
            player_info = player_entry.get("player_info") or {}
            player_last_online = player_map.get(player_uid, {}).get("lastOnline", "") or parse_timestamp(
                player_info.get("last_online_real_time"),
                not_after=level_mtime,
            )
            if player_uid in player_map and not player_map[player_uid].get("lastOnline") and player_last_online:
                player_map[player_uid]["lastOnline"] = player_last_online
            guild_players.append(
                {
                    "playerUid": player_uid,
                    "nickname": first_valid_display_text(
                        player_info.get("player_name"),
                        player_map.get(player_uid, {}).get("nickname", ""),
                    ),
                    "lastOnline": player_last_online,
                }
            )

        if not guild_players and raw_data.get("player_uid"):
            fallback_last_online = parse_timestamp(
                first_value(raw_data, ("last_online_real_time",)),
                not_after=level_mtime,
            )
            raw_player_uid = as_text(raw_data.get("player_uid"))
            if raw_player_uid in player_map and not player_map[raw_player_uid].get("lastOnline") and fallback_last_online:
                player_map[raw_player_uid]["lastOnline"] = fallback_last_online
            guild_players.append(
                {
                    "playerUid": raw_player_uid,
                    "nickname": first_valid_display_text(first_value(raw_data, ("player_name",))),
                    "lastOnline": fallback_last_online
                    or player_map.get(raw_player_uid, {}).get("lastOnline", ""),
                }
            )

        base_camps = sorted(
            base_camps_by_group.get(group_id, []),
            key=lambda item: (item.get("name") or "", item.get("id") or ""),
        )
        admin_player_uid = (
            normalize_uid_text(raw_data.get("admin_player_uid"))
            or normalize_uid_text(raw_data.get("player_uid"))
            or normalize_uid_text(raw_data.get("group_name"))
        )
        guild_name = (
            first_valid_display_text(
                raw_data.get("guild_name"),
                raw_data.get("guild_name_2"),
                raw_data.get("group_name"),
            )
            or "未命名公会"
        )
        if (
            group_type == "EPalGroupType::Organization"
            and not guild_players
            and not base_camps
            and not admin_player_uid
            and guild_name == "未命名公会"
        ):
            continue
        for guild_player in guild_players:
            guild_player["isAdmin"] = guild_player.get("playerUid") == admin_player_uid
        guilds.append(
            {
                "groupId": group_id,
                "groupType": group_type,
                "name": guild_name,
                "adminPlayerUid": admin_player_uid,
                "playerCount": len(guild_players),
                "baseCampLevel": as_int(raw_data.get("base_camp_level"), 0),
                "baseCampCount": len(base_camps),
                "players": guild_players,
                "baseCamps": base_camps,
            }
        )

    players = sorted(player_map.values(), key=lambda item: (item.get("nickname") or "", item.get("playerUid") or ""))
    guilds = sorted(guilds, key=lambda item: (item.get("name") or "", item.get("groupId") or ""))

    return {
        "meta": {
            "parsedAt": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
            "levelSavPath": str(level_path),
            "levelSavUpdatedAt": file_mtime_iso(level_path),
            "playerSaveCount": len(player_files),
        },
        "players": players,
        "guilds": guilds,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Palworld save data and output normalized JSON")
    parser.add_argument("--level", required=True, help="Absolute path to Level.sav")
    parser.add_argument("--players-dir", default="", help="Absolute path to Players directory")
    parser.add_argument(
        "--operation",
        default="analyze",
        choices=["analyze", "update-player", "update-guild", "read-world-option", "write-world-option"],
        help="运行模式"
    )
    parser.add_argument("--payload-file", default="", help="更新载荷 JSON 文件路径")
    parser.add_argument("--world-option", default="", help="WorldOption.sav 文件路径")
    args = parser.parse_args()

    level_path = Path(args.level).expanduser().resolve()
    players_dir = Path(args.players_dir).expanduser().resolve() if args.players_dir else None
    if not level_path.exists():
        raise FileNotFoundError(f"Level.sav 不存在: {level_path}")
    world_option_path = Path(args.world_option).expanduser().resolve() if args.world_option else None

    if args.operation == "analyze":
        result = build_analysis(level_path, players_dir)
    elif args.operation == "read-world-option":
        if not world_option_path:
            raise FileNotFoundError("未提供 WorldOption.sav 路径")
        result = read_world_option(level_path, world_option_path)
    else:
        payload_file = Path(args.payload_file).expanduser().resolve() if args.payload_file else None
        if not payload_file or not payload_file.exists():
            raise FileNotFoundError("未找到更新载荷文件")
        payload = load_payload_file(payload_file)
        if args.operation == "update-player":
            result = apply_player_update(level_path, players_dir, payload)
        elif args.operation == "update-guild":
            result = apply_guild_update(level_path, payload)
        else:
            if not world_option_path:
                raise FileNotFoundError("未提供 WorldOption.sav 路径")
            result = write_world_option(level_path, world_option_path, payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, cls=CustomEncoder))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
