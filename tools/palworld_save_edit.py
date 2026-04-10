#!/usr/bin/env python3

import copy
import contextlib
import json
import os
import re
import sys
import time
import uuid
import zlib
from pathlib import Path
from typing import Any

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from palworld_save_tools.compressor import Compressor, MagicBytes, SaveType
from palworld_save_tools.paltypes import (
    DISABLED_PROPERTIES,
    PALWORLD_CUSTOM_PROPERTIES,
    PALWORLD_TYPE_HINTS,
)

PLAYER_ITEM_GROUP_KEYS = [
    "CommonContainerId",
    "DropSlotContainerId",
    "EssentialContainerId",
    "FoodEquipContainerId",
    "PlayerEquipArmorContainerId",
    "WeaponLoadOutContainerId",
]

PAL_CONTAINER_TYPE_OTOMO = "otomo"
PAL_CONTAINER_TYPE_STORAGE = "storage"
MAX_OTOMO_PALS = 5

STATUS_POINT_KEY_TO_NAME = {
    "hp": "最大HP",
    "stamina": "最大SP",
    "attack": "攻撃力",
    "weight": "所持重量",
    "workSpeed": "作業速度",
}

WORLD_OPTION_SAVE_GAME_CLASS = "/Script/Pal.PalWorldOptionSaveGame"
WORLD_OPTION_DATA_STRUCT = "PalOptionWorldSaveData"
WORLD_OPTION_SETTINGS_STRUCT = "PalOptionWorldSettings"
WORLD_OPTION_HIDDEN_CONNECT_PLATFORM_KEY = "AllowConnectPlatform"
WORLD_OPTION_DEFAULT_FILETIME = 116444736000000000

WORLD_OPTION_ENUM_TYPES = {
    "Difficulty": "EPalOptionWorldDifficulty",
    "RandomizerType": "EPalRandomizerType",
    "DeathPenalty": "EPalOptionWorldDeathPenalty",
    "LogFormatType": "EPalOptionWorldLogFormatType",
    "CrossplayPlatforms": "EPalAllowConnectPlatform",
    "DenyTechnologyList": "EPalDenyTechnology",
    WORLD_OPTION_HIDDEN_CONNECT_PLATFORM_KEY: "EPalOptionWorldAllowConnectPlatform",
}

WORLD_OPTION_DEFAULTS: dict[str, Any] = {
    "Difficulty": "None",
    "RandomizerType": "None",
    "RandomizerSeed": "",
    "bIsRandomizerPalLevelRandom": False,
    "DayTimeSpeedRate": 1.0,
    "NightTimeSpeedRate": 1.0,
    "ExpRate": 1.0,
    "PalCaptureRate": 1.0,
    "PalSpawnNumRate": 1.0,
    "PalDamageRateAttack": 1.0,
    "PalDamageRateDefense": 1.0,
    "PalStomachDecreaceRate": 1.0,
    "PalStaminaDecreaceRate": 1.0,
    "PalAutoHPRegeneRate": 1.0,
    "PalAutoHpRegeneRateInSleep": 1.0,
    "PlayerDamageRateAttack": 1.0,
    "PlayerDamageRateDefense": 1.0,
    "PlayerStomachDecreaceRate": 1.0,
    "PlayerStaminaDecreaceRate": 1.0,
    "PlayerAutoHPRegeneRate": 1.0,
    "PlayerAutoHpRegeneRateInSleep": 1.0,
    "BuildObjectHpRate": 1.0,
    "BuildObjectDamageRate": 1.0,
    "BuildObjectDeteriorationDamageRate": 1.0,
    "CollectionDropRate": 1.0,
    "CollectionObjectHpRate": 1.0,
    "CollectionObjectRespawnSpeedRate": 1.0,
    "EnemyDropItemRate": 1.0,
    "DeathPenalty": "All",
    "bEnablePlayerToPlayerDamage": False,
    "bEnableFriendlyFire": False,
    "bEnableInvaderEnemy": True,
    "EnablePredatorBossPal": True,
    "bActiveUNKO": False,
    "bEnableAimAssistPad": True,
    "bEnableAimAssistKeyboard": False,
    "DropItemMaxNum": 3000,
    "DropItemMaxNum_UNKO": 100,
    "BaseCampMaxNum": 128,
    "DropItemAliveMaxHours": 1.0,
    "GuildPlayerMaxNum": 20,
    "BaseCampMaxNumInGuild": 4,
    "BaseCampWorkerMaxNum": 15,
    "MaxBuildingLimitNum": 0,
    "bAutoResetGuildNoOnlinePlayers": False,
    "AutoResetGuildTimeNoOnlinePlayers": 72.0,
    "WorkSpeedRate": 1.0,
    "AutoSaveSpan": 1800.0,
    "SupplyDropSpan": 180,
    "ChatPostLimitPerMinute": 30,
    "PalEggDefaultHatchingTime": 72.0,
    "CoopPlayerMaxNum": 4,
    "ServerName": "Default Palworld Server",
    "ServerDescription": "",
    "AdminPassword": "",
    "ServerPassword": "",
    "PublicIP": "",
    "PublicPort": 8211,
    "ServerPlayerMaxNum": 32,
    "bIsUseBackupSaveData": True,
    "CrossplayPlatforms": ["Steam", "Xbox", "PS5", "Mac"],
    "LogFormatType": "Text",
    "bIsMultiplay": False,
    "bIsPvP": False,
    "bHardcore": False,
    "bPalLost": False,
    "bCharacterRecreateInHardcore": False,
    "bCanPickupOtherGuildDeathPenaltyDrop": False,
    "bEnableNonLoginPenalty": True,
    "bEnableFastTravel": True,
    "bEnableFastTravelOnlyBaseCamp": False,
    "bIsStartLocationSelectByMap": True,
    "bExistPlayerAfterLogout": False,
    "bEnableDefenseOtherGuildPlayer": False,
    "bInvisibleOtherGuildBaseCampAreaFX": False,
    "bBuildAreaLimit": False,
    "bShowPlayerList": False,
    "bAllowGlobalPalboxExport": True,
    "bAllowGlobalPalboxImport": False,
    "RCONEnabled": False,
    "RCONPort": 25575,
    "RESTAPIEnabled": False,
    "RESTAPIPort": 8212,
    "Region": "",
    "bUseAuth": True,
    "BanListURL": "https://b.palworldgame.com/api/banlist.txt",
    "ServerReplicatePawnCullDistance": 15000.0,
    "ItemWeightRate": 1.0,
    "EquipmentDurabilityDamageRate": 1.0,
    "ItemContainerForceMarkDirtyInterval": 1.0,
    "ItemCorruptionMultiplier": 1.0,
    "bAllowClientMod": True,
    "bIsShowJoinLeftMessage": True,
    "DenyTechnologyList": [],
    "GuildRejoinCooldownMinutes": 0,
    "BlockRespawnTime": 5.0,
    "RespawnPenaltyDurationThreshold": 0.0,
    "RespawnPenaltyTimeScale": 2.0,
    "bDisplayPvPItemNumOnWorldMap_BaseCamp": False,
    "bDisplayPvPItemNumOnWorldMap_Player": False,
    "AdditionalDropItemWhenPlayerKillingInPvPMode": "PlayerDropItem",
    "AdditionalDropItemNumWhenPlayerKillingInPvPMode": 1,
    "bAdditionalDropItemWhenPlayerKillingInPvPMode": False,
    "bAllowEnhanceStat_Health": True,
    "bAllowEnhanceStat_Attack": True,
    "bAllowEnhanceStat_Stamina": True,
    "bAllowEnhanceStat_Weight": True,
    "bAllowEnhanceStat_WorkSpeed": True,
}

WORLD_OPTION_FLOAT_KEYS = {
    "DayTimeSpeedRate",
    "NightTimeSpeedRate",
    "ExpRate",
    "PalCaptureRate",
    "PalSpawnNumRate",
    "PalDamageRateAttack",
    "PalDamageRateDefense",
    "PalStomachDecreaceRate",
    "PalStaminaDecreaceRate",
    "PalAutoHPRegeneRate",
    "PalAutoHpRegeneRateInSleep",
    "PlayerDamageRateAttack",
    "PlayerDamageRateDefense",
    "PlayerStomachDecreaceRate",
    "PlayerStaminaDecreaceRate",
    "PlayerAutoHPRegeneRate",
    "PlayerAutoHpRegeneRateInSleep",
    "BuildObjectHpRate",
    "BuildObjectDamageRate",
    "BuildObjectDeteriorationDamageRate",
    "CollectionDropRate",
    "CollectionObjectHpRate",
    "CollectionObjectRespawnSpeedRate",
    "EnemyDropItemRate",
    "DropItemAliveMaxHours",
    "AutoResetGuildTimeNoOnlinePlayers",
    "WorkSpeedRate",
    "AutoSaveSpan",
    "PalEggDefaultHatchingTime",
    "ServerReplicatePawnCullDistance",
    "ItemWeightRate",
    "EquipmentDurabilityDamageRate",
    "ItemContainerForceMarkDirtyInterval",
    "ItemCorruptionMultiplier",
    "BlockRespawnTime",
    "RespawnPenaltyDurationThreshold",
    "RespawnPenaltyTimeScale",
}

WORLD_OPTION_ARRAY_KEYS = {"CrossplayPlatforms", "DenyTechnologyList"}

WORLD_OPTION_VALID_KEYS = list(WORLD_OPTION_DEFAULTS.keys())


def build_custom_properties() -> dict[str, Any]:
    return {
        key: value
        for key, value in PALWORLD_CUSTOM_PROPERTIES.items()
        if key not in DISABLED_PROPERTIES
    }


def load_raw_sav(file_path: Path) -> tuple[GvasFile, int]:
    with open(file_path, "rb") as f:
        compressed = f.read()
    raw_gvas, save_type = decompress_sav_to_gvas(compressed)
    with contextlib.redirect_stdout(sys.stderr):
        gvas = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, build_custom_properties())
    return gvas, save_type


def write_raw_sav(file_path: Path, gvas: GvasFile, save_type: int) -> None:
    with contextlib.redirect_stdout(sys.stderr):
        raw_gvas = gvas.write(build_custom_properties())
    try:
        compressed = compress_gvas_to_sav(raw_gvas, save_type)
    except AttributeError as error:
        if save_type != SaveType.PLM or "compress" not in str(error):
            raise
        compressed_data = zlib.compress(raw_gvas)
        compressed = Compressor().build_sav(
            compressed_data,
            len(raw_gvas),
            len(compressed_data),
            MagicBytes.PLZ,
            SaveType.PLM,
        )
    temp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
    with open(temp_path, "wb") as f:
        f.write(compressed)
    os.replace(temp_path, file_path)


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if hasattr(value, "__class__") and value.__class__.__name__ == "UUID":
        return str(value)
    if isinstance(value, dict):
        if "type" in value and "value" in value:
            return as_text(value.get("value"))
        for key in ("value", "Value", "guid", "Guid", "ID", "Id", "id", "static_id", "StaticId"):
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


def as_bool(value: Any) -> bool:
    if isinstance(value, dict) and "type" in value and "value" in value:
        return as_bool(value.get("value"))
    return bool(value)


def as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, dict) and "type" in value and "value" in value:
        return as_int(value.get("value"), default)
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except Exception:
            return default
    return default


def as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, dict) and "type" in value and "value" in value:
        return as_float(value.get("value"), default)
    if value is None:
        return default
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except Exception:
            return default
    return default


def normalize_uid_text(value: Any) -> str:
    text = as_text(value).strip().lower()
    if not text:
        return ""
    if re.fullmatch(r"[0-9a-f]{32}", text):
        return (
            f"{text[0:8]}-{text[8:12]}-{text[12:16]}-"
            f"{text[16:20]}-{text[20:32]}"
        )
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text):
        return text
    return ""


def compact_uid_text(value: Any) -> str:
    normalized = normalize_uid_text(value)
    if not normalized:
        return ""
    return normalized.replace("-", "").upper()


def make_new_uid() -> str:
    return str(uuid.uuid4())


def normalize_pal_container_type(value: Any) -> str:
    container_type = str(value or "").strip().lower()
    if container_type == PAL_CONTAINER_TYPE_OTOMO:
        return PAL_CONTAINER_TYPE_OTOMO
    return PAL_CONTAINER_TYPE_STORAGE


def get_struct_value(property_node: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(property_node, dict) or property_node.get("type") != "StructProperty":
        raise ValueError("目标字段不是结构体")
    value = property_node.get("value")
    if not isinstance(value, dict):
        raise ValueError("目标结构体内容无效")
    return value


def find_property(properties: dict[str, Any], names: list[str] | tuple[str, ...]) -> tuple[str, dict[str, Any]]:
    for name in names:
        if name in properties:
            value = properties[name]
            if isinstance(value, dict):
                return name, value
    raise ValueError(f"未找到字段: {' / '.join(names)}")


def get_optional_property(properties: dict[str, Any], names: list[str] | tuple[str, ...]) -> tuple[str, dict[str, Any]] | None:
    for name in names:
        value = properties.get(name)
        if isinstance(value, dict):
            return name, value
    return None


def first_value_like(properties: dict[str, Any], names: list[str] | tuple[str, ...]) -> Any:
    property_entry = get_optional_property(properties, names)
    if not property_entry:
        return None
    return property_entry[1]


def set_text_property(properties: dict[str, Any], names: list[str] | tuple[str, ...], value: Any) -> None:
    _, property_node = find_property(properties, names)
    set_text_value(property_node, value)


def set_int_property(properties: dict[str, Any], names: list[str] | tuple[str, ...], value: Any) -> None:
    _, property_node = find_property(properties, names)
    set_int_value(property_node, value)


def set_float_property(properties: dict[str, Any], names: list[str] | tuple[str, ...], value: Any) -> None:
    _, property_node = find_property(properties, names)
    set_float_value(property_node, value)


def try_set_text_property(properties: dict[str, Any], names: list[str] | tuple[str, ...], value: Any) -> bool:
    property_entry = get_optional_property(properties, names)
    if not property_entry:
        return False
    set_text_value(property_entry[1], value)
    return True


def try_set_int_property(properties: dict[str, Any], names: list[str] | tuple[str, ...], value: Any) -> bool:
    property_entry = get_optional_property(properties, names)
    if not property_entry:
        return False
    set_int_value(property_entry[1], value)
    return True


def try_set_float_property(properties: dict[str, Any], names: list[str] | tuple[str, ...], value: Any) -> bool:
    property_entry = get_optional_property(properties, names)
    if not property_entry:
        return False
    set_float_value(property_entry[1], value)
    return True


def build_uint16_property(value: Any) -> dict[str, Any]:
    normalized = max(0, min(65535, int(as_int(value, 0))))
    return {
        "id": None,
        "type": "UInt16Property",
        "value": normalized,
    }


def build_string_property(value: Any) -> dict[str, Any]:
    return {
        "id": None,
        "type": "StrProperty",
        "value": str(value or ""),
    }


def build_name_property(value: Any) -> dict[str, Any]:
    return {
        "id": None,
        "type": "NameProperty",
        "value": str(value or ""),
    }


def build_name_array_property(values: list[Any]) -> dict[str, Any]:
    return {
        "id": None,
        "type": "ArrayProperty",
        "array_type": "NameProperty",
        "value": {
            "prop_name": "NameProperty",
            "prop_type": "NameProperty",
            "type_name": "NameProperty",
            "id": "00000000-0000-0000-0000-000000000000",
            "values": [str(item or "") for item in values],
        },
    }


def build_byte_property(value: Any) -> dict[str, Any]:
    normalized = max(0, min(255, int(as_int(value, 0))))
    return {
        "id": None,
        "type": "ByteProperty",
        "value": {
            "type": "None",
            "value": normalized,
        },
    }


def build_int64_property(value: Any) -> dict[str, Any]:
    return {
        "id": None,
        "type": "Int64Property",
        "value": int(as_int(value, 0)),
    }


def build_fixed_point64_property(value: Any) -> dict[str, Any]:
    return {
        "struct_type": "FixedPoint64",
        "struct_id": "00000000-0000-0000-0000-000000000000",
        "id": None,
        "type": "StructProperty",
        "value": {
            "Value": build_int64_property(value),
        },
    }


def has_any_property(properties: dict[str, Any], names: list[str] | tuple[str, ...]) -> bool:
    return get_optional_property(properties, names) is not None


def set_text_value(property_node: dict[str, Any], value: Any) -> None:
    property_type = property_node.get("type")
    if property_type == "StructProperty":
        struct_value = get_struct_value(property_node)
        nested_entry = get_optional_property(struct_value, ("Value", "value"))
        if not nested_entry:
            raise ValueError("目标文本结构缺少 Value 字段")
        set_text_value(nested_entry[1], value)
        return
    if property_type in ("EnumProperty", "ByteProperty") and isinstance(property_node.get("value"), dict):
        property_node["value"]["value"] = str(value or "")
        return
    property_node["value"] = str(value or "")


def set_int_value(property_node: dict[str, Any], value: Any) -> None:
    property_type = property_node.get("type")
    if property_type == "StructProperty":
        struct_value = get_struct_value(property_node)
        nested_entry = get_optional_property(struct_value, ("Value", "value", "Current", "current"))
        if not nested_entry:
            raise ValueError("目标数值结构缺少 Value 字段")
        set_int_value(nested_entry[1], value)
        return
    if property_type in ("EnumProperty", "ByteProperty") and isinstance(property_node.get("value"), dict):
        property_node["value"]["value"] = int(as_int(value, 0))
        return
    property_node["value"] = int(as_int(value, 0))


def set_float_value(property_node: dict[str, Any], value: Any) -> None:
    property_type = property_node.get("type")
    if property_type == "StructProperty":
        struct_value = get_struct_value(property_node)
        nested_entry = get_optional_property(struct_value, ("Value", "value", "Current", "current"))
        if not nested_entry:
            raise ValueError("目标浮点结构缺少 Value 字段")
        set_float_value(nested_entry[1], value)
        return
    if property_type in ("EnumProperty", "ByteProperty") and isinstance(property_node.get("value"), dict):
        property_node["value"]["value"] = float(as_float(value, 0.0))
        return
    property_node["value"] = float(as_float(value, 0.0))


def set_transform_translation(properties: dict[str, Any], names: list[str] | tuple[str, ...], location: dict[str, Any]) -> None:
    _, transform_prop = find_property(properties, names)
    transform_value = get_struct_value(transform_prop)
    translation_entry = get_optional_property(transform_value, ("translation", "Translation"))
    if not translation_entry:
        raise ValueError("未找到坐标结构")
    _, translation_prop = translation_entry
    translation_value = get_struct_value(translation_prop)
    translation_value["x"] = float(as_float(location.get("x"), 0.0))
    translation_value["y"] = float(as_float(location.get("y"), 0.0))
    translation_value["z"] = float(as_float(location.get("z"), 0.0))


def try_set_transform_translation(
    properties: dict[str, Any], names: list[str] | tuple[str, ...], location: dict[str, Any]
) -> bool:
    transform_entry = get_optional_property(properties, names)
    if not transform_entry:
        return False
    _, transform_prop = transform_entry
    if transform_prop.get("type") != "StructProperty":
        return False
    transform_value = get_struct_value(transform_prop)
    translation_entry = get_optional_property(transform_value, ("translation", "Translation"))
    if not translation_entry:
        return False
    _, translation_prop = translation_entry
    if translation_prop.get("type") != "StructProperty":
        return False
    translation_value = get_struct_value(translation_prop)
    translation_value["x"] = float(as_float(location.get("x"), 0.0))
    translation_value["y"] = float(as_float(location.get("y"), 0.0))
    translation_value["z"] = float(as_float(location.get("z"), 0.0))
    return True


def get_array_struct_entries(property_node: Any) -> list[dict[str, Any]]:
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


def append_array_struct_entry(property_node: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    value = property_node.get("value")
    if isinstance(value, dict):
        nested_values = value.get("values")
        if isinstance(nested_values, list):
            nested_values.append(entry)
            return entry
    if isinstance(value, list):
        value.append(entry)
        return entry
    raise ValueError("目标数组结构无效")


def replace_array_items(property_node: dict[str, Any], entries: list[Any]) -> None:
    value = property_node.get("value")
    if isinstance(value, dict):
        nested_values = value.get("values")
        if isinstance(nested_values, list):
            nested_values[:] = entries
            return
    if isinstance(value, list):
        value[:] = entries
        return
    raise ValueError("目标数组结构无效")


def build_status_point_entry(status_name: str, value: Any) -> dict[str, Any]:
    return {
        "StatusName": {
            "id": None,
            "type": "NameProperty",
            "value": status_name,
        },
        "StatusPoint": {
            "id": None,
            "type": "IntProperty",
            "value": int(as_int(value, 0)),
        },
    }


def find_status_point_entry(property_node: Any, status_name: str) -> dict[str, Any] | None:
    for entry in get_array_struct_entries(property_node):
        if as_text(entry.get("StatusName")) == status_name:
            return entry
    return None


def ensure_status_point_entry(
    properties: dict[str, Any], prop_name: str, status_name: str
) -> dict[str, Any] | None:
    property_node = properties.get(prop_name)
    if not isinstance(property_node, dict) or property_node.get("type") != "ArrayProperty":
        return None
    entry = find_status_point_entry(property_node, status_name)
    if entry:
        return entry
    return append_array_struct_entry(property_node, build_status_point_entry(status_name, 0))


def update_status_point_total(save_parameter: dict[str, Any], target_key: str, desired_total: Any) -> bool:
    status_name = STATUS_POINT_KEY_TO_NAME.get(target_key)
    if not status_name:
        return False
    main_entry = ensure_status_point_entry(save_parameter, "GotStatusPointList", status_name)
    ex_entry = ensure_status_point_entry(save_parameter, "GotExStatusPointList", status_name)
    if not main_entry and not ex_entry:
        return False
    normalized_total = max(0, int(as_int(desired_total, 0)))
    current_ex = as_int((ex_entry or {}).get("StatusPoint"), 0)
    new_ex = min(current_ex, normalized_total)
    new_main = normalized_total - new_ex
    if main_entry:
        set_int_value(main_entry["StatusPoint"], new_main)
    if ex_entry:
        set_int_value(ex_entry["StatusPoint"], new_ex)
    return True


def set_array_values(properties: dict[str, Any], names: list[str] | tuple[str, ...], values: list[Any]) -> None:
    _, property_node = find_property(properties, names)
    if property_node.get("type") != "ArrayProperty":
        raise ValueError(f"字段 {' / '.join(names)} 不是数组")
    if not isinstance(property_node.get("value"), dict):
        raise ValueError(f"字段 {' / '.join(names)} 数组结构无效")
    property_node["value"]["values"] = [str(item or "") for item in values]


def get_array_items(property_node: Any) -> list[Any]:
    if isinstance(property_node, dict):
        if property_node.get("type") == "ArrayProperty":
            values = property_node.get("value", {}).get("values", [])
            return values if isinstance(values, list) else []
        if property_node.get("type") == "StructProperty":
            struct_value = get_struct_value(property_node)
            nested_array = struct_value.get("Slots")
            if isinstance(nested_array, dict) and nested_array.get("type") == "ArrayProperty":
                values = nested_array.get("value", {}).get("values", [])
                return values if isinstance(values, list) else []
        if "Slots" in property_node:
            return get_array_items(property_node.get("Slots"))
    if isinstance(property_node, list):
        return property_node
    return []


def get_world_save(gvas: GvasFile) -> dict[str, Any]:
    world_save = gvas.properties.get("worldSaveData")
    if not isinstance(world_save, dict):
        raise ValueError("未找到 worldSaveData")
    return get_struct_value(world_save)


def get_save_parameter_from_character_entry(entry: dict[str, Any]) -> dict[str, Any]:
    raw_data_prop = entry.get("RawData")
    if not isinstance(raw_data_prop, dict):
        raise ValueError("角色数据缺少 RawData")
    raw_data = raw_data_prop.get("value")
    if not isinstance(raw_data, dict):
        raise ValueError("角色 RawData 结构无效")
    raw_object = raw_data.get("object")
    if not isinstance(raw_object, dict):
        raise ValueError("角色对象数据无效")
    save_parameter_prop = raw_object.get("SaveParameter")
    if not isinstance(save_parameter_prop, dict):
        raise ValueError("角色缺少 SaveParameter")
    return get_struct_value(save_parameter_prop)


def get_map_entries(world_save: dict[str, Any], property_name: str) -> list[dict[str, Any]]:
    prop = world_save.get(property_name)
    if not isinstance(prop, dict) or prop.get("type") != "MapProperty":
        raise ValueError(f"未找到映射字段: {property_name}")
    values = prop.get("value")
    if not isinstance(values, list):
        raise ValueError(f"映射字段 {property_name} 结构无效")
    return values


def extract_player_uid_from_entry(map_entry: dict[str, Any]) -> str:
    entry_value = map_entry.get("value")
    if not isinstance(entry_value, dict):
        return ""
    try:
        save_parameter = get_save_parameter_from_character_entry(entry_value)
    except Exception:
        return ""
    player_uid = normalize_uid_text(
        (get_optional_property(save_parameter, ("PlayerUId", "PlayerUID")) or ("", {}))[1]
    )
    if player_uid:
        return player_uid
    entry_key = map_entry.get("key")
    if isinstance(entry_key, dict):
        player_uid = normalize_uid_text(entry_key.get("PlayerUId") or entry_key.get("PlayerUID"))
        if player_uid:
            return player_uid
    return ""


def extract_owner_player_uid(save_parameter: dict[str, Any]) -> str:
    result = get_optional_property(save_parameter, ("OwnerPlayerUId", "OwnerPlayerUid"))
    if not result:
        return ""
    return normalize_uid_text(result[1])


def extract_pal_instance_id(save_parameter: dict[str, Any], map_entry: dict[str, Any]) -> str:
    individual = get_optional_property(save_parameter, ("IndividualId",))
    if individual:
        individual_value = get_struct_value(individual[1])
        instance_prop = get_optional_property(individual_value, ("InstanceId",))
        if instance_prop:
            return normalize_uid_text(instance_prop[1])
    entry_key = map_entry.get("key")
    if isinstance(entry_key, dict):
        instance_value = entry_key.get("InstanceId")
        if instance_value:
            return normalize_uid_text(instance_value)
    return ""


def extract_character_instance_id(map_entry: dict[str, Any]) -> str:
    entry_key = map_entry.get("key")
    if isinstance(entry_key, dict):
        instance_value = entry_key.get("InstanceId")
        if instance_value:
            return normalize_uid_text(
                instance_value.get("value") if isinstance(instance_value, dict) else instance_value
            )
    return ""


def find_player_character_entry(world_save: dict[str, Any], player_uid: str) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_uid = normalize_uid_text(player_uid)
    for entry in get_map_entries(world_save, "CharacterSaveParameterMap"):
        entry_value = entry.get("value")
        if not isinstance(entry_value, dict):
            continue
        try:
            save_parameter = get_save_parameter_from_character_entry(entry_value)
        except Exception:
            continue
        if extract_owner_player_uid(save_parameter):
            continue
        if extract_player_uid_from_entry(entry) == normalized_uid:
            return entry_value, save_parameter
    raise ValueError("未找到指定玩家")


def find_player_character_map_entry(world_save: dict[str, Any], player_uid: str) -> dict[str, Any]:
    normalized_uid = normalize_uid_text(player_uid)
    for entry in get_map_entries(world_save, "CharacterSaveParameterMap"):
        entry_value = entry.get("value")
        if not isinstance(entry_value, dict):
            continue
        try:
            save_parameter = get_save_parameter_from_character_entry(entry_value)
        except Exception:
            continue
        if extract_owner_player_uid(save_parameter):
            continue
        if extract_player_uid_from_entry(entry) == normalized_uid:
            return entry
    raise ValueError("未找到指定玩家")


def find_pal_character_entry(world_save: dict[str, Any], owner_player_uid: str, instance_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_owner_uid = normalize_uid_text(owner_player_uid)
    normalized_instance_id = normalize_uid_text(instance_id)
    for entry in get_map_entries(world_save, "CharacterSaveParameterMap"):
        entry_value = entry.get("value")
        if not isinstance(entry_value, dict):
            continue
        try:
            save_parameter = get_save_parameter_from_character_entry(entry_value)
        except Exception:
            continue
        if extract_owner_player_uid(save_parameter) != normalized_owner_uid:
            continue
        if extract_pal_instance_id(save_parameter, entry) == normalized_instance_id:
            return entry_value, save_parameter
    raise ValueError(f"未找到帕鲁实例: {instance_id}")


def find_character_container_entry(world_save: dict[str, Any], container_id: str) -> dict[str, Any]:
    normalized_container_id = normalize_uid_text(container_id)
    for entry in get_map_entries(world_save, "CharacterContainerSaveData"):
        entry_key = entry.get("key")
        current_container_id = ""
        if isinstance(entry_key, dict):
            id_value = entry_key.get("ID")
            current_container_id = normalize_uid_text(
                id_value.get("value") if isinstance(id_value, dict) else id_value
            )
        else:
            current_container_id = normalize_uid_text(entry_key)
        if current_container_id == normalized_container_id:
            entry_value = entry.get("value")
            if isinstance(entry_value, dict):
                return entry_value
    raise ValueError(f"未找到帕鲁容器: {container_id}")


def find_player_save_file(players_dir: Path | None, player_uid: str) -> Path:
    if not players_dir or not players_dir.exists():
        raise ValueError("未找到玩家存档目录")
    normalized_uid = normalize_uid_text(player_uid)
    for player_file in sorted(players_dir.glob("*.sav")):
        try:
            player_gvas, _ = load_raw_sav(player_file)
            save_data = get_struct_value(player_gvas.properties.get("SaveData") or {})
            current_uid = normalize_uid_text(
                (get_optional_property(save_data, ("PlayerUId", "PlayerUID")) or ("", {}))[1]
            )
            if current_uid == normalized_uid:
                return player_file
        except Exception:
            continue
    raise ValueError("未找到对应的玩家存档文件")


def parse_player_inventory_container_ids(player_file: Path) -> dict[str, str]:
    player_gvas, _ = load_raw_sav(player_file)
    save_data_prop = player_gvas.properties.get("SaveData")
    if not isinstance(save_data_prop, dict):
        raise ValueError("玩家存档缺少 SaveData")
    save_data = get_struct_value(save_data_prop)
    inventory_info_prop = save_data.get("InventoryInfo")
    if not isinstance(inventory_info_prop, dict):
        inventory_info_prop = save_data.get("inventoryInfo")
    if not isinstance(inventory_info_prop, dict):
        raise ValueError("玩家存档缺少 InventoryInfo")
    inventory_info = get_struct_value(inventory_info_prop)
    result: dict[str, str] = {}
    for key in PLAYER_ITEM_GROUP_KEYS:
        prop_entry = get_optional_property(inventory_info, (key,))
        if not prop_entry:
            continue
        container_value = prop_entry[1]
        if container_value.get("type") == "StructProperty":
            struct_value = get_struct_value(container_value)
            result[key] = normalize_uid_text(
                struct_value.get("ID") or struct_value.get("Id") or struct_value.get("id")
            )
        else:
            result[key] = normalize_uid_text(container_value)
    return result


def parse_player_pal_container_ids(player_file: Path) -> dict[str, str]:
    player_gvas, _ = load_raw_sav(player_file)
    save_data_prop = player_gvas.properties.get("SaveData")
    if not isinstance(save_data_prop, dict):
        raise ValueError("玩家存档缺少 SaveData")
    save_data = get_struct_value(save_data_prop)
    result: dict[str, str] = {}
    container_fields = {
        "otomo": ("OtomoCharacterContainerId", "OtomoPalContainerId"),
        "storage": ("PalStorageContainerId", "PalContainerId"),
    }
    for target_key, field_names in container_fields.items():
        prop_entry = get_optional_property(save_data, field_names)
        if not prop_entry:
            continue
        container_value = prop_entry[1]
        if container_value.get("type") == "StructProperty":
            struct_value = get_struct_value(container_value)
            result[target_key] = normalize_uid_text(
                struct_value.get("ID") or struct_value.get("Id") or struct_value.get("id")
            )
        else:
            result[target_key] = normalize_uid_text(container_value)
    return result


def update_player_save_file_location(players_dir: Path | None, player_uid: str, location: dict[str, Any]) -> None:
    player_file = find_player_save_file(players_dir, player_uid)
    player_gvas, save_type = load_raw_sav(player_file)
    save_data_prop = player_gvas.properties.get("SaveData")
    if not isinstance(save_data_prop, dict):
        raise ValueError("玩家存档缺少 SaveData")
    save_data = get_struct_value(save_data_prop)
    if not try_set_transform_translation(save_data, ("LastTransform", "Transform"), location):
        raise ValueError("未找到玩家存档坐标字段")
    write_raw_sav(player_file, player_gvas, save_type)


def find_item_container_entry(world_save: dict[str, Any], container_id: str) -> dict[str, Any]:
    normalized_container_id = normalize_uid_text(container_id)
    for entry in get_map_entries(world_save, "ItemContainerSaveData"):
        entry_key = normalize_uid_text(entry.get("key"))
        if entry_key == normalized_container_id:
            entry_value = entry.get("value")
            if isinstance(entry_value, dict):
                return entry_value
    raise ValueError(f"未找到物品容器: {container_id}")


def find_item_slot(entry_value: dict[str, Any], slot_index: int) -> dict[str, Any]:
    slots_prop = entry_value.get("Slots")
    if slots_prop is None:
        raise ValueError("物品容器缺少 Slots")
    slot_items = get_array_items(slots_prop)
    if not isinstance(slot_items, list) or len(slot_items) == 0:
        raise ValueError("物品容器槽位列表无效")
    for slot in slot_items:
        if not isinstance(slot, dict):
            continue
        raw_data_prop = slot.get("RawData")
        if not isinstance(raw_data_prop, dict):
            continue
        raw_data = raw_data_prop.get("value")
        if not isinstance(raw_data, dict):
            continue
        current_slot_index = as_int(raw_data.get("slot_index"), as_int(slot.get("SlotIndex"), -1))
        if current_slot_index == slot_index:
            return slot
        current_slot_index = as_int(slot.get("slot_index"), as_int(slot.get("SlotIndex"), -1))
        if current_slot_index == slot_index:
            return slot
    raise ValueError(f"未找到背包槽位: {slot_index}")


def create_item_slot(entry_value: dict[str, Any], slot_index: int) -> dict[str, Any]:
    slots_prop = entry_value.get("Slots")
    if slots_prop is None:
        raise ValueError("物品容器缺少 Slots")
    slot_items = get_array_items(slots_prop)
    if not isinstance(slot_items, list) or len(slot_items) == 0:
        raise ValueError("物品容器缺少可复用的槽位模板")

    template_slot = next((slot for slot in slot_items if isinstance(slot, dict)), None)
    if not isinstance(template_slot, dict):
        raise ValueError("物品容器槽位模板无效")

    new_slot = copy.deepcopy(template_slot)
    raw_data_prop = new_slot.get("RawData")
    if not isinstance(raw_data_prop, dict):
        raise ValueError("槽位模板缺少 RawData")
    raw_data = raw_data_prop.get("value")
    if not isinstance(raw_data, dict):
        raise ValueError("槽位模板 RawData 无效")

    raw_data["slot_index"] = slot_index
    raw_data["count"] = 0
    raw_data["item"] = {
        "static_id": "",
        "dynamic_id": {
            "created_world_id": "00000000-0000-0000-0000-000000000000",
            "local_id_in_created_world": "00000000-0000-0000-0000-000000000000",
        },
    }

    if isinstance(raw_data.get("trailing_bytes"), list):
        raw_data["trailing_bytes"] = [0 for _ in raw_data["trailing_bytes"]]

    append_array_struct_entry(slots_prop, new_slot)
    return new_slot


def ensure_item_slot(entry_value: dict[str, Any], slot_index: int) -> dict[str, Any]:
    try:
        return find_item_slot(entry_value, slot_index)
    except ValueError:
        return create_item_slot(entry_value, slot_index)


def prune_item_slots(entry_value: dict[str, Any], keep_slot_indices: set[int]) -> None:
    slots_prop = entry_value.get("Slots")
    if slots_prop is None:
        raise ValueError("物品容器缺少 Slots")
    slot_items = get_array_items(slots_prop)
    if not isinstance(slot_items, list):
        raise ValueError("物品容器槽位列表无效")

    next_slots: list[Any] = []
    for slot in slot_items:
        if not isinstance(slot, dict):
            continue
        raw_data_prop = slot.get("RawData")
        if not isinstance(raw_data_prop, dict):
            continue
        raw_data = raw_data_prop.get("value")
        if not isinstance(raw_data, dict):
            continue
        current_slot_index = as_int(raw_data.get("slot_index"), as_int(slot.get("SlotIndex"), -1))
        if current_slot_index in keep_slot_indices:
            next_slots.append(slot)

    replace_array_items(slots_prop, next_slots)


def extract_character_slot_instance_id(slot: dict[str, Any]) -> str:
    raw_data_prop = slot.get("RawData")
    if isinstance(raw_data_prop, dict):
        raw_data = raw_data_prop.get("value")
        if isinstance(raw_data, dict):
            return normalize_uid_text(
                raw_data.get("instance_id")
                or raw_data.get("InstanceId")
                or raw_data.get("instanceId")
            )
    return ""


def update_character_slot(slot: dict[str, Any], slot_index: int, instance_id: str) -> dict[str, Any]:
    slot_index_prop = slot.get("SlotIndex")
    if isinstance(slot_index_prop, dict):
        slot_index_prop["value"] = int(slot_index)
    else:
        slot["SlotIndex"] = {
            "id": None,
            "type": "IntProperty",
            "value": int(slot_index),
        }

    raw_data_prop = slot.get("RawData")
    if not isinstance(raw_data_prop, dict):
        raise ValueError("帕鲁槽位缺少 RawData")
    raw_data = raw_data_prop.get("value")
    if not isinstance(raw_data, dict):
        raise ValueError("帕鲁槽位 RawData 无效")
    raw_data["player_uid"] = "00000000-0000-0000-0000-000000000000"
    raw_data["instance_id"] = normalize_uid_text(instance_id)
    raw_data["permission_tribe_id"] = int(as_int(raw_data.get("permission_tribe_id"), 0))
    return slot


def prune_character_slots(entry_value: dict[str, Any], keep_instance_ids: set[str]) -> set[str]:
    slots_prop = entry_value.get("Slots")
    if slots_prop is None:
        raise ValueError("帕鲁容器缺少 Slots")
    slot_items = get_array_items(slots_prop)
    if not isinstance(slot_items, list):
        raise ValueError("帕鲁容器槽位列表无效")

    removed_instance_ids: set[str] = set()
    next_slots: list[Any] = []
    for slot in slot_items:
        if not isinstance(slot, dict):
            continue
        instance_id = extract_character_slot_instance_id(slot)
        if not instance_id or instance_id in keep_instance_ids:
            next_slots.append(slot)
            continue
        removed_instance_ids.add(instance_id)

    replace_array_items(slots_prop, next_slots)
    return removed_instance_ids


def find_character_slot(entry_value: dict[str, Any], slot_index: int) -> dict[str, Any]:
    slots_prop = entry_value.get("Slots")
    if slots_prop is None:
        raise ValueError("帕鲁容器缺少 Slots")
    slot_items = get_array_items(slots_prop)
    if not isinstance(slot_items, list) or len(slot_items) == 0:
        raise ValueError("帕鲁容器槽位列表无效")
    for slot in slot_items:
        if not isinstance(slot, dict):
            continue
        current_slot_index = as_int(slot.get("SlotIndex"), -1)
        if current_slot_index == slot_index:
            return slot
    raise ValueError(f"未找到帕鲁槽位: {slot_index}")


def find_character_slot_template(
    world_save: dict[str, Any] | None, preferred_container_ids: list[str] | None = None
) -> dict[str, Any] | None:
    normalized_preferred_ids = [
        normalize_uid_text(container_id)
        for container_id in (preferred_container_ids or [])
        if normalize_uid_text(container_id)
    ]

    def extract_template_from_entry(entry_value: Any) -> dict[str, Any] | None:
        if not isinstance(entry_value, dict):
            return None
        slots_prop = entry_value.get("Slots")
        slot_items = get_array_items(slots_prop)
        if not isinstance(slot_items, list):
            return None
        return next((copy.deepcopy(slot) for slot in slot_items if isinstance(slot, dict)), None)

    if world_save and normalized_preferred_ids:
        for container_id in normalized_preferred_ids:
            try:
                entry_value = find_character_container_entry(world_save, container_id)
            except Exception:
                continue
            template_slot = extract_template_from_entry(entry_value)
            if template_slot:
                return template_slot

    if world_save:
        for entry in get_map_entries(world_save, "CharacterContainerSaveData"):
            template_slot = extract_template_from_entry(entry.get("value"))
            if template_slot:
                return template_slot
    return None


def create_character_slot(
    entry_value: dict[str, Any],
    slot_index: int,
    instance_id: str,
    world_save: dict[str, Any] | None = None,
    preferred_template_container_ids: list[str] | None = None,
) -> dict[str, Any]:
    slots_prop = entry_value.get("Slots")
    if slots_prop is None:
        raise ValueError("帕鲁容器缺少 Slots")
    slot_items = get_array_items(slots_prop)
    template_slot = next((slot for slot in slot_items if isinstance(slot, dict)), None) if isinstance(slot_items, list) else None
    if not isinstance(template_slot, dict):
        template_slot = find_character_slot_template(world_save, preferred_template_container_ids)
    if not isinstance(template_slot, dict):
        raise ValueError("帕鲁容器缺少可复用的槽位模板")

    new_slot = copy.deepcopy(template_slot)
    update_character_slot(new_slot, slot_index, instance_id)
    append_array_struct_entry(slots_prop, new_slot)
    return new_slot


def ensure_character_slot(
    entry_value: dict[str, Any],
    slot_index: int,
    instance_id: str,
    world_save: dict[str, Any] | None = None,
    preferred_template_container_ids: list[str] | None = None,
) -> dict[str, Any]:
    try:
        slot = find_character_slot(entry_value, slot_index)
    except ValueError:
        return create_character_slot(
            entry_value,
            slot_index,
            instance_id,
            world_save=world_save,
            preferred_template_container_ids=preferred_template_container_ids,
        )
    return update_character_slot(slot, slot_index, instance_id)


def build_guild_player_entry(player_uid: str, nickname: str, last_online_real_time: int = 0) -> dict[str, Any]:
    return {
        "player_uid": normalize_uid_text(player_uid),
        "player_info": {
            "last_online_real_time": int(as_int(last_online_real_time, 0)),
            "player_name": str(nickname or ""),
        },
    }


def ensure_guild_character_handle(
    guild_raw_data: dict[str, Any], player_uid: str, instance_id: str, allow_zero_guid: bool = False
) -> None:
    normalized_player_uid = normalize_uid_text(player_uid)
    normalized_instance_id = normalize_uid_text(instance_id)
    if not normalized_instance_id:
        return
    handles = guild_raw_data.get("individual_character_handle_ids")
    if not isinstance(handles, list):
        guild_raw_data["individual_character_handle_ids"] = []
        handles = guild_raw_data["individual_character_handle_ids"]
    for handle in handles:
        if not isinstance(handle, dict):
            continue
        if normalize_uid_text(handle.get("instance_id")) == normalized_instance_id:
            handle["guid"] = (
                "00000000-0000-0000-0000-000000000000"
                if allow_zero_guid
                else normalized_player_uid
            )
            handle["instance_id"] = normalized_instance_id
            return
    handles.append(
        {
            "guid": "00000000-0000-0000-0000-000000000000" if allow_zero_guid else normalized_player_uid,
            "instance_id": normalized_instance_id,
        }
    )


def find_player_guild_entry(world_save: dict[str, Any], player_uid: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    normalized_player_uid = normalize_uid_text(player_uid)
    for entry in get_map_entries(world_save, "GroupSaveDataMap"):
        entry_value = entry.get("value")
        if not isinstance(entry_value, dict):
            continue
        raw_data_prop = entry_value.get("RawData")
        if not isinstance(raw_data_prop, dict):
            continue
        raw_data = raw_data_prop.get("value")
        if not isinstance(raw_data, dict):
            continue
        for player_entry in raw_data.get("players") or []:
            if normalize_uid_text((player_entry or {}).get("player_uid")) == normalized_player_uid:
                return entry_value, raw_data
    return None


def prune_guild_character_handles(guild_raw_data: dict[str, Any], removed_instance_ids: set[str]) -> None:
    if not removed_instance_ids:
        return
    handles = guild_raw_data.get("individual_character_handle_ids")
    if not isinstance(handles, list):
        return
    guild_raw_data["individual_character_handle_ids"] = [
        handle
        for handle in handles
        if not isinstance(handle, dict)
        or normalize_uid_text(handle.get("instance_id")) not in removed_instance_ids
    ]


def resolve_target_pal_container_id(container_ids: dict[str, str], container_type: Any) -> str:
    normalized_container_type = normalize_pal_container_type(container_type)
    if normalized_container_type == PAL_CONTAINER_TYPE_OTOMO:
        return container_ids.get(PAL_CONTAINER_TYPE_OTOMO) or container_ids.get(PAL_CONTAINER_TYPE_STORAGE) or ""
    return container_ids.get(PAL_CONTAINER_TYPE_STORAGE) or container_ids.get(PAL_CONTAINER_TYPE_OTOMO) or ""


def set_pal_slot_binding(save_parameter: dict[str, Any], container_id: str, slot_index: int) -> None:
    slot_id_prop = get_optional_property(save_parameter, ("SlotId",))
    if not slot_id_prop:
        return
    slot_id_value = get_struct_value(slot_id_prop[1])
    container_id_prop = get_optional_property(slot_id_value, ("ContainerId",))
    if container_id_prop:
        container_struct = get_struct_value(container_id_prop[1])
        id_prop = get_optional_property(container_struct, ("ID", "Id", "id"))
        if id_prop:
            id_prop[1]["value"] = normalize_uid_text(container_id)
    slot_index_prop = get_optional_property(slot_id_value, ("SlotIndex",))
    if slot_index_prop:
        slot_index_prop[1]["value"] = int(slot_index)


def sync_player_pal_containers(
    world_save: dict[str, Any],
    players_dir: Path | None,
    player_uid: str,
    payload_pals: list[Any],
) -> None:
    normalized_player_uid = normalize_uid_text(player_uid)
    player_file = find_player_save_file(players_dir, normalized_player_uid)
    container_ids = parse_player_pal_container_ids(player_file)
    otomo_container_id = container_ids.get(PAL_CONTAINER_TYPE_OTOMO)
    storage_container_id = container_ids.get(PAL_CONTAINER_TYPE_STORAGE)
    if not otomo_container_id and not storage_container_id:
        raise ValueError("玩家缺少帕鲁容器绑定")

    current_container_type_by_instance_id: dict[str, str] = {}
    target_instances_by_type: dict[str, list[str]] = {
        PAL_CONTAINER_TYPE_OTOMO: [],
        PAL_CONTAINER_TYPE_STORAGE: [],
    }
    target_instance_ids: set[str] = set()
    current_slot_map: dict[str, dict[str, Any]] = {}
    container_entries: dict[str, dict[str, Any]] = {}
    for container_type, container_id in (
        (PAL_CONTAINER_TYPE_OTOMO, otomo_container_id),
        (PAL_CONTAINER_TYPE_STORAGE, storage_container_id),
    ):
        if not container_id:
            continue
        container_entry = find_character_container_entry(world_save, container_id)
        container_entries[container_type] = container_entry
        for slot in get_array_items(container_entry.get("Slots")):
            if not isinstance(slot, dict):
                continue
            instance_id = extract_character_slot_instance_id(slot)
            if not instance_id:
                continue
            current_slot_map[instance_id] = copy.deepcopy(slot)
            current_container_type_by_instance_id[instance_id] = container_type

    for pal_payload in payload_pals:
        if not isinstance(pal_payload, dict):
            continue
        instance_id = normalize_uid_text(pal_payload.get("instanceId"))
        if not instance_id or instance_id in target_instance_ids:
            continue
        target_instance_ids.add(instance_id)
        requested_container_type = str(pal_payload.get("containerType") or "").strip().lower()
        if requested_container_type not in {PAL_CONTAINER_TYPE_OTOMO, PAL_CONTAINER_TYPE_STORAGE}:
            requested_container_type = current_container_type_by_instance_id.get(instance_id, PAL_CONTAINER_TYPE_STORAGE)
        effective_container_type = normalize_pal_container_type(requested_container_type)
        if effective_container_type == PAL_CONTAINER_TYPE_OTOMO and not otomo_container_id and storage_container_id:
            effective_container_type = PAL_CONTAINER_TYPE_STORAGE
        if effective_container_type == PAL_CONTAINER_TYPE_STORAGE and not storage_container_id and otomo_container_id:
            effective_container_type = PAL_CONTAINER_TYPE_OTOMO
        target_instances_by_type[effective_container_type].append(instance_id)

    if len(target_instances_by_type[PAL_CONTAINER_TYPE_OTOMO]) > MAX_OTOMO_PALS:
        raise ValueError(f"随身帕鲁最多只能设置 {MAX_OTOMO_PALS} 只")

    preferred_template_container_ids = [
        container_id
        for container_id in [otomo_container_id, storage_container_id]
        if container_id
    ]

    for container_type, container_id in (
        (PAL_CONTAINER_TYPE_OTOMO, otomo_container_id),
        (PAL_CONTAINER_TYPE_STORAGE, storage_container_id),
    ):
        if not container_id:
            continue
        container_entry = container_entries.get(container_type)
        if not container_entry:
            continue
        next_slots: list[dict[str, Any]] = []
        for slot_index, instance_id in enumerate(target_instances_by_type[container_type]):
            slot = copy.deepcopy(current_slot_map.get(instance_id)) if current_slot_map.get(instance_id) else None
            if not isinstance(slot, dict):
                slot = find_character_slot_template(world_save, preferred_template_container_ids)
            if not isinstance(slot, dict):
                raise ValueError("未找到可复用的帕鲁槽位模板")
            next_slots.append(update_character_slot(slot, slot_index, instance_id))
            _, pal_save_parameter = find_pal_character_entry(world_save, normalized_player_uid, instance_id)
            set_pal_slot_binding(pal_save_parameter, container_id, slot_index)
        slots_prop = container_entry.get("Slots")
        if slots_prop is None:
            raise ValueError("帕鲁容器缺少 Slots")
        replace_array_items(slots_prop, next_slots)

    removed_instance_ids: set[str] = set()
    character_entries = get_map_entries(world_save, "CharacterSaveParameterMap")
    next_character_entries: list[dict[str, Any]] = []
    for entry in character_entries:
        entry_value = entry.get("value")
        if not isinstance(entry_value, dict):
            next_character_entries.append(entry)
            continue
        try:
            save_parameter = get_save_parameter_from_character_entry(entry_value)
        except Exception:
            next_character_entries.append(entry)
            continue
        if extract_owner_player_uid(save_parameter) != normalized_player_uid:
            next_character_entries.append(entry)
            continue
        instance_id = extract_pal_instance_id(save_parameter, entry)
        if not instance_id or instance_id in target_instance_ids:
            next_character_entries.append(entry)
            continue
        removed_instance_ids.add(instance_id)
    character_entries[:] = next_character_entries

    player_guild = find_player_guild_entry(world_save, normalized_player_uid)
    if player_guild:
        _, guild_raw_data = player_guild
        prune_guild_character_handles(guild_raw_data, removed_instance_ids)


def build_new_pal_payload(template_save_parameter: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    next_payload = {
        "nickname": payload.get("nickname") or "",
        "level": payload.get("level", 1),
        "exp": payload.get("exp", 0),
        "hp": payload.get("hp", as_int(first_value_like(template_save_parameter, ("HP", "Hp")), 0)),
        "maxHp": payload.get("maxHp", as_int(first_value_like(template_save_parameter, ("MaxHP", "MaxHp")), 0)),
        "rank": payload.get("rank", 0),
        "rankAttack": payload.get("rankAttack", 0),
        "rankDefense": payload.get("rankDefense", 0),
        "rankCraftSpeed": payload.get("rankCraftSpeed", 0),
        "melee": payload.get("melee", as_int(first_value_like(template_save_parameter, ("Talent_HP", "TalentHp", "TalentMelee", "Melee")), 0)),
        "ranged": payload.get("ranged", as_int(first_value_like(template_save_parameter, ("Talent_Shot", "TalentShot", "Ranged")), 0)),
        "defense": payload.get("defense", as_int(first_value_like(template_save_parameter, ("Talent_Defense", "TalentDefense", "Defense")), 0)),
        "workSpeed": payload.get("workSpeed", as_int(first_value_like(template_save_parameter, ("CraftSpeed", "TalentCraftSpeed", "Talent_WorkSpeed", "WorkSpeed")), 0)),
        "passiveSkills": payload.get("passiveSkills") or [],
        "activeSkills": payload.get("activeSkills") or [],
    }
    return next_payload

def update_player_items(world_save: dict[str, Any], players_dir: Path | None, player_uid: str, payload_items: dict[str, Any]) -> None:
    if not payload_items:
        return
    player_file = find_player_save_file(players_dir, player_uid)
    container_map = parse_player_inventory_container_ids(player_file)
    for group_key, items in payload_items.items():
        if group_key not in PLAYER_ITEM_GROUP_KEYS:
            continue
        container_id = container_map.get(group_key)
        if not container_id:
            raise ValueError(f"玩家背包分组缺少容器绑定: {group_key}")
        container_entry = find_item_container_entry(world_save, container_id)
        if not isinstance(items, list):
            continue
        keep_slot_indices = {
            max(0, as_int((item or {}).get("slotIndex"), -1))
            for item in items
            if as_int((item or {}).get("slotIndex"), -1) >= 0
        }
        prune_item_slots(container_entry, keep_slot_indices)
        for item in items:
            slot_index = as_int((item or {}).get("slotIndex"), -1)
            if slot_index < 0:
                raise ValueError("背包槽位索引无效")
            slot = ensure_item_slot(container_entry, slot_index)
            raw_data_prop = slot.get("RawData")
            if not isinstance(raw_data_prop, dict):
                raise ValueError(f"背包槽位缺少 RawData: {slot_index}")
            raw_data = raw_data_prop.get("value")
            if not isinstance(raw_data, dict):
                raise ValueError(f"背包槽位 RawData 无效: {slot_index}")

            raw_data["slot_index"] = slot_index
            raw_data["count"] = int(as_int(item.get("stackCount"), 0))
            item_id = str(item.get("itemId") or "")
            if isinstance(raw_data.get("item"), dict):
                raw_data["item"]["static_id"] = item_id
            elif "static_id" in raw_data:
                raw_data["static_id"] = item_id
            elif "StaticId" in raw_data:
                raw_data["StaticId"] = item_id
            else:
                raw_data["item"] = {
                    "static_id": item_id,
                    "dynamic_id": {
                        "created_world_id": "00000000-0000-0000-0000-000000000000",
                        "local_id_in_created_world": "00000000-0000-0000-0000-000000000000",
                    },
                }


def update_player_core_fields(save_parameter: dict[str, Any], payload: dict[str, Any]) -> None:
    if "nickname" in payload:
        try_set_text_property(save_parameter, ("NickName", "Nickname"), payload.get("nickname"))
    if "level" in payload:
        try_set_int_property(save_parameter, ("Level",), payload.get("level"))
    base_stats = payload.get("baseStats")
    if isinstance(base_stats, dict):
        try_set_int_property(save_parameter, ("HP", "Hp"), base_stats.get("hp"))
        try_set_int_property(save_parameter, ("MaxHP", "MaxHp"), base_stats.get("maxHp"))
        try_set_int_property(save_parameter, ("ShieldHP", "ShieldHp"), base_stats.get("shieldHp"))
        try_set_int_property(save_parameter, ("MaxShieldHP", "ShieldMaxHp"), base_stats.get("shieldMaxHp"))
    status_points = payload.get("statusPoints")
    if isinstance(status_points, dict):
        if not try_set_int_property(
            save_parameter, ("UnusedStatusPoint", "RemainStatusPoint"), status_points.get("unused")
        ) and "unused" in status_points:
            save_parameter["UnusedStatusPoint"] = build_uint16_property(status_points.get("unused"))
        legacy_status_fields = {
            "hp": ("AddMaxHP", "AddHP"),
            "stamina": ("AddMaxSP", "AddSP"),
            "attack": ("AddAttack", "AddMeleeAttack"),
            "workSpeed": ("AddWorkSpeed",),
            "weight": ("AddMaxWeight",),
        }
        for key, names in legacy_status_fields.items():
            try_set_int_property(save_parameter, names, status_points.get(key))
            update_status_point_total(save_parameter, key, status_points.get(key))
    if "maxStatusPoint" in payload:
        try_set_int_property(save_parameter, ("MaxStatusPoint",), payload.get("maxStatusPoint"))
    if "fullStomach" in payload:
        try_set_float_property(save_parameter, ("FullStomach",), payload.get("fullStomach"))


def update_player_location(save_parameter: dict[str, Any], players_dir: Path | None, player_uid: str, location: dict[str, Any]) -> None:
    if try_set_transform_translation(save_parameter, ("Transform", "LastTransform"), location):
        return
    update_player_save_file_location(players_dir, player_uid, location)


def update_pal_fields(
    save_parameter: dict[str, Any],
    payload: dict[str, Any],
    allow_create_missing_core_fields: bool = False,
) -> None:
    should_create_missing_core_fields = allow_create_missing_core_fields or not (
        has_any_property(save_parameter, ("Level",))
        and has_any_property(save_parameter, ("Exp",))
        and has_any_property(save_parameter, ("HP", "Hp"))
    )
    if "characterId" in payload:
        if (
            not try_set_text_property(save_parameter, ("CharacterID", "CharacterId"), payload.get("characterId"))
            and should_create_missing_core_fields
        ):
            save_parameter["CharacterID"] = build_name_property(payload.get("characterId"))
    if "nickname" in payload:
        if not try_set_text_property(save_parameter, ("NickName", "Nickname"), payload.get("nickname")):
            nickname = str(payload.get("nickname") or "").strip()
            if nickname and should_create_missing_core_fields:
                save_parameter["NickName"] = build_string_property(nickname)
    if "level" in payload:
        if not try_set_int_property(save_parameter, ("Level",), payload.get("level")) and should_create_missing_core_fields:
            save_parameter["Level"] = build_byte_property(payload.get("level"))
    if "exp" in payload:
        if not try_set_int_property(save_parameter, ("Exp",), payload.get("exp")) and should_create_missing_core_fields:
            save_parameter["Exp"] = build_int64_property(payload.get("exp"))
    if "hp" in payload:
        if (
            not try_set_int_property(save_parameter, ("HP", "Hp"), payload.get("hp"))
            and should_create_missing_core_fields
        ):
            save_parameter["Hp"] = build_fixed_point64_property(payload.get("hp"))
    if "maxHp" in payload:
        try_set_int_property(save_parameter, ("MaxHP", "MaxHp"), payload.get("maxHp"))
    if "rank" in payload:
        try_set_int_property(save_parameter, ("Rank",), payload.get("rank"))
    if "rankAttack" in payload:
        try_set_int_property(save_parameter, ("RankAttack", "Rank_Attack"), payload.get("rankAttack"))
    if "rankDefense" in payload:
        try_set_int_property(
            save_parameter,
            ("RankDefence", "RankDefense", "Rank_Defense"),
            payload.get("rankDefense"),
        )
    if "rankCraftSpeed" in payload:
        try_set_int_property(
            save_parameter,
            ("RankCraftspeed", "RankCraftSpeed", "Rank_CraftSpeed"),
            payload.get("rankCraftSpeed"),
        )
    if "melee" in payload:
        if not try_set_int_property(
            save_parameter,
            ("Talent_HP", "TalentHp", "TalentMelee", "Melee"),
            payload.get("melee"),
        ) and should_create_missing_core_fields:
            save_parameter["Talent_HP"] = build_byte_property(payload.get("melee"))
    if "ranged" in payload:
        if not try_set_int_property(
            save_parameter,
            ("Talent_Shot", "TalentShot", "Ranged"),
            payload.get("ranged"),
        ) and should_create_missing_core_fields:
            save_parameter["Talent_Shot"] = build_byte_property(payload.get("ranged"))
    if "defense" in payload:
        if not try_set_int_property(
            save_parameter,
            ("Talent_Defense", "TalentDefense", "Defense"),
            payload.get("defense"),
        ) and should_create_missing_core_fields:
            save_parameter["Talent_Defense"] = build_byte_property(payload.get("defense"))
    if "workSpeed" in payload:
        try_set_int_property(
            save_parameter,
            ("CraftSpeed", "TalentCraftSpeed", "Talent_WorkSpeed", "WorkSpeed"),
            payload.get("workSpeed"),
        )
    if isinstance(payload.get("passiveSkills"), list):
        set_array_values(save_parameter, ("PassiveSkillList",), payload.get("passiveSkills") or [])
    if isinstance(payload.get("activeSkills"), list):
        active_skills = [str(item or "") for item in payload.get("activeSkills") or []]
        equip_prop_entry = get_optional_property(save_parameter, ("EquipWaza",))
        mastered_prop_entry = get_optional_property(save_parameter, ("MasteredWaza",))
        equip_count = 0
        if equip_prop_entry and isinstance(equip_prop_entry[1].get("value"), dict):
            equip_count = len(equip_prop_entry[1]["value"].get("values", []))
        if equip_count <= 0 and active_skills:
            equip_count = 1
        equip_values = active_skills[:equip_count]
        mastered_values = active_skills[equip_count:]
        if not equip_prop_entry and active_skills:
            if mastered_prop_entry and isinstance(mastered_prop_entry[1], dict):
                save_parameter["EquipWaza"] = copy.deepcopy(mastered_prop_entry[1])
                equip_prop_entry = ("EquipWaza", save_parameter["EquipWaza"])
            else:
                save_parameter["EquipWaza"] = build_name_array_property([])
                equip_prop_entry = ("EquipWaza", save_parameter["EquipWaza"])
        if not mastered_prop_entry and mastered_values:
            if equip_prop_entry and isinstance(equip_prop_entry[1], dict):
                save_parameter["MasteredWaza"] = copy.deepcopy(equip_prop_entry[1])
                mastered_prop_entry = ("MasteredWaza", save_parameter["MasteredWaza"])
            else:
                save_parameter["MasteredWaza"] = build_name_array_property([])
                mastered_prop_entry = ("MasteredWaza", save_parameter["MasteredWaza"])
        if equip_prop_entry:
            equip_value = equip_prop_entry[1].get("value")
            if not isinstance(equip_value, dict):
                equip_prop_entry[1]["value"] = {"values": []}
                equip_value = equip_prop_entry[1]["value"]
            equip_value["values"] = equip_values
        if mastered_prop_entry:
            mastered_value = mastered_prop_entry[1].get("value")
            if not isinstance(mastered_value, dict):
                mastered_prop_entry[1]["value"] = {"values": []}
                mastered_value = mastered_prop_entry[1]["value"]
            mastered_value["values"] = mastered_values


def find_pal_template_entry(world_save: dict[str, Any], owner_player_uid: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    normalized_owner_uid = normalize_uid_text(owner_player_uid)
    fallback_template: tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None = None
    for entry in get_map_entries(world_save, "CharacterSaveParameterMap"):
        entry_value = entry.get("value")
        if not isinstance(entry_value, dict):
            continue
        try:
            save_parameter = get_save_parameter_from_character_entry(entry_value)
        except Exception:
            continue
        current_owner_uid = extract_owner_player_uid(save_parameter)
        if not current_owner_uid:
            continue
        if current_owner_uid == normalized_owner_uid:
            return entry, entry_value, save_parameter
        if fallback_template is None:
            fallback_template = (entry, entry_value, save_parameter)
    if fallback_template:
        return fallback_template
    raise ValueError("未找到可复用的帕鲁模板")


def create_pal_character_entry(
    world_save: dict[str, Any],
    players_dir: Path | None,
    player_uid: str,
    payload: dict[str, Any],
) -> str:
    player_file = find_player_save_file(players_dir, player_uid)
    container_ids = parse_player_pal_container_ids(player_file)
    target_container_id = resolve_target_pal_container_id(container_ids, payload.get("containerType"))
    if not target_container_id:
        raise ValueError("玩家缺少帕鲁容器绑定")
    template_container_candidates = [
        container_id for container_id in [container_ids.get("storage"), container_ids.get("otomo")] if container_id
    ]

    template_map_entry, _, template_save_parameter = find_pal_template_entry(world_save, player_uid)
    new_map_entry = copy.deepcopy(template_map_entry)
    new_instance_id = make_new_uid()

    new_key = new_map_entry.get("key")
    if not isinstance(new_key, dict):
        raise ValueError("帕鲁模板映射键无效")
    instance_key = new_key.get("InstanceId")
    if isinstance(instance_key, dict):
        instance_key["value"] = new_instance_id
    else:
        new_key["InstanceId"] = {
            "struct_type": "Guid",
            "struct_id": "00000000-0000-0000-0000-000000000000",
            "id": None,
            "value": new_instance_id,
            "type": "StructProperty",
        }
    player_key = new_key.get("PlayerUId")
    if isinstance(player_key, dict):
        player_key["value"] = "00000000-0000-0000-0000-000000000000"

    new_save_parameter = get_save_parameter_from_character_entry(new_map_entry.get("value") or {})
    try_set_text_property(new_save_parameter, ("CharacterID", "CharacterId"), payload.get("characterId"))
    try_set_text_property(new_save_parameter, ("NickName", "Nickname"), payload.get("nickname"))
    owner_prop = get_optional_property(new_save_parameter, ("OwnerPlayerUId", "OwnerPlayerUid"))
    if owner_prop:
        owner_prop[1]["value"] = normalize_uid_text(player_uid)

    old_owner_prop = get_optional_property(new_save_parameter, ("OldOwnerPlayerUIds",))
    if old_owner_prop and isinstance(old_owner_prop[1].get("value"), dict):
        old_owner_prop[1]["value"]["values"] = [normalize_uid_text(player_uid)]

    slot_id_prop = get_optional_property(new_save_parameter, ("SlotId",))
    next_slot_index = 0
    if slot_id_prop:
        slot_id_value = get_struct_value(slot_id_prop[1])
        container_id_prop = get_optional_property(slot_id_value, ("ContainerId",))
        if container_id_prop:
            container_struct = get_struct_value(container_id_prop[1])
            id_prop = get_optional_property(container_struct, ("ID", "Id", "id"))
            if id_prop:
                id_prop[1]["value"] = normalize_uid_text(target_container_id)
        slot_index_prop = get_optional_property(slot_id_value, ("SlotIndex",))
        if slot_index_prop:
            target_container_entry = find_character_container_entry(world_save, target_container_id)
            current_slots = get_array_items(target_container_entry.get("Slots"))
            next_slot_index = (
                max(
                    [as_int((slot or {}).get("SlotIndex"), -1) for slot in current_slots if isinstance(slot, dict)],
                    default=-1,
                )
                + 1
            )
            slot_index_prop[1]["value"] = int(next_slot_index)

    initial_payload = build_new_pal_payload(template_save_parameter, payload)
    initial_payload["characterId"] = payload.get("characterId")
    update_pal_fields(new_save_parameter, initial_payload, allow_create_missing_core_fields=True)

    character_map = world_save.get("CharacterSaveParameterMap")
    if not isinstance(character_map, dict):
        raise ValueError("未找到 CharacterSaveParameterMap")
    append_array_struct_entry(character_map, new_map_entry)

    target_container_entry = find_character_container_entry(world_save, target_container_id)
    if next_slot_index <= 0:
        current_slots = get_array_items(target_container_entry.get("Slots"))
        next_slot_index = (
            max(
                [as_int((slot or {}).get("SlotIndex"), -1) for slot in current_slots if isinstance(slot, dict)],
                default=-1,
            )
            + 1
        )
    ensure_character_slot(
        target_container_entry,
        next_slot_index,
        new_instance_id,
        world_save=world_save,
        preferred_template_container_ids=template_container_candidates,
    )

    player_guild = find_player_guild_entry(world_save, player_uid)
    if player_guild:
        _, guild_raw_data = player_guild
        ensure_guild_character_handle(
            guild_raw_data,
            "00000000-0000-0000-0000-000000000000",
            new_instance_id,
            allow_zero_guid=True,
        )
    return new_instance_id


def find_guild_entry(world_save: dict[str, Any], group_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_group_id = normalize_uid_text(group_id)
    for entry in get_map_entries(world_save, "GroupSaveDataMap"):
        entry_value = entry.get("value")
        if not isinstance(entry_value, dict):
            continue
        raw_data_prop = entry_value.get("RawData")
        if not isinstance(raw_data_prop, dict):
            continue
        raw_data = raw_data_prop.get("value")
        if not isinstance(raw_data, dict):
            continue
        current_group_id = normalize_uid_text(raw_data.get("group_id") or entry.get("key"))
        if current_group_id == normalized_group_id:
            return entry_value, raw_data
    raise ValueError("未找到指定公会")


def find_base_camp_entry(world_save: dict[str, Any], camp_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_camp_id = normalize_uid_text(camp_id)
    for entry in get_map_entries(world_save, "BaseCampSaveData"):
        entry_value = entry.get("value")
        if not isinstance(entry_value, dict):
            continue
        raw_data_prop = entry_value.get("RawData")
        if not isinstance(raw_data_prop, dict):
            continue
        raw_data = raw_data_prop.get("value")
        if not isinstance(raw_data, dict):
            continue
        current_id = normalize_uid_text(raw_data.get("id"))
        if current_id == normalized_camp_id:
            return entry_value, raw_data
    raise ValueError(f"未找到基地: {camp_id}")


def update_guild_fields(raw_data: dict[str, Any], payload: dict[str, Any]) -> None:
    name = str(payload.get("name") or "")
    if name:
        if "guild_name" in raw_data:
            raw_data["guild_name"] = name
        elif "guild_name_2" in raw_data:
            raw_data["guild_name_2"] = name
        elif "group_name" in raw_data and not normalize_uid_text(raw_data.get("group_name")):
            raw_data["group_name"] = name
        if "guild_name_2" in raw_data:
            raw_data["guild_name_2"] = name
    if "baseCampLevel" in payload and "base_camp_level" in raw_data:
        raw_data["base_camp_level"] = int(as_int(payload.get("baseCampLevel"), 0))


def update_guild_players(world_save: dict[str, Any], guild_raw_data: dict[str, Any], payload_players: list[Any]) -> None:
    if not isinstance(payload_players, list):
        return
    normalized_payload_players = [item for item in payload_players if isinstance(item, dict)]
    admin_players = [
        normalize_uid_text(item.get("playerUid"))
        for item in normalized_payload_players
        if item.get("isAdmin")
    ]
    admin_players = [item for item in admin_players if item]
    if normalized_payload_players and len(admin_players) != 1:
        raise ValueError("公会必须且只能有一名会长")
    admin_player_uid = admin_players[0] if admin_players else ""

    existing_player_entries = {}
    for player_entry in guild_raw_data.get("players") or []:
        if not isinstance(player_entry, dict):
            continue
        existing_player_entries[normalize_uid_text(player_entry.get("player_uid"))] = copy.deepcopy(player_entry)

    next_players: list[dict[str, Any]] = []
    for payload_player in normalized_payload_players:
        player_uid = normalize_uid_text(payload_player.get("playerUid"))
        if not player_uid:
            continue
        nickname = str(payload_player.get("nickname") or "").strip()
        current_entry = existing_player_entries.get(player_uid)
        if current_entry:
            player_info = current_entry.get("player_info")
            if not isinstance(player_info, dict):
                player_info = {}
                current_entry["player_info"] = player_info
            player_info["player_name"] = nickname or str(player_info.get("player_name") or "")
            current_entry["player_uid"] = player_uid
            next_players.append(current_entry)
        else:
            next_players.append(build_guild_player_entry(player_uid, nickname))

        player_map_entry = find_player_character_map_entry(world_save, player_uid)
        player_instance_id = extract_character_instance_id(player_map_entry)
        if player_instance_id:
            ensure_guild_character_handle(guild_raw_data, player_uid, player_instance_id)

    guild_raw_data["players"] = next_players
    if admin_player_uid:
        guild_raw_data["admin_player_uid"] = admin_player_uid
        if "player_uid" in guild_raw_data:
            guild_raw_data["player_uid"] = admin_player_uid
        if "group_name" in guild_raw_data:
            guild_raw_data["group_name"] = compact_uid_text(admin_player_uid)


def update_base_camp_fields(raw_data: dict[str, Any], payload: dict[str, Any]) -> None:
    if "name" in payload:
        raw_data["name"] = str(payload.get("name") or "")
    if "areaRange" in payload:
        raw_data["area_range"] = float(as_float(payload.get("areaRange"), 0.0))
    location = payload.get("location")
    if isinstance(location, dict):
        transform = raw_data.get("transform")
        if not isinstance(transform, dict):
            raise ValueError("基地变换结构无效")
        translation = transform.get("translation")
        if not isinstance(translation, dict):
            raise ValueError("基地坐标结构无效")
        translation["x"] = float(as_float(location.get("x"), 0.0))
        translation["y"] = float(as_float(location.get("y"), 0.0))
        translation["z"] = float(as_float(location.get("z"), 0.0))


def apply_player_update(level_path: Path, players_dir: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    player_uid = normalize_uid_text(payload.get("playerUid"))
    if not player_uid:
        raise ValueError("玩家 UID 无效")
    gvas, save_type = load_raw_sav(level_path)
    world_save = get_world_save(gvas)
    _, save_parameter = find_player_character_entry(world_save, player_uid)
    update_player_core_fields(save_parameter, payload)
    if isinstance(payload.get("location"), dict):
        update_player_location(save_parameter, players_dir, player_uid, payload["location"])

    for pal_payload in payload.get("pals") or []:
        if not isinstance(pal_payload, dict):
            continue
        if pal_payload.get("isNew"):
            new_instance_id = create_pal_character_entry(world_save, players_dir, player_uid, pal_payload)
            if new_instance_id:
                pal_payload["instanceId"] = new_instance_id
                pal_payload["isNew"] = False
            continue
        instance_id = normalize_uid_text(pal_payload.get("instanceId"))
        if not instance_id:
            continue
        _, pal_save_parameter = find_pal_character_entry(world_save, player_uid, instance_id)
        update_pal_fields(pal_save_parameter, pal_payload)
    sync_player_pal_containers(world_save, players_dir, player_uid, payload.get("pals") or [])

    items_payload = payload.get("items")
    if isinstance(items_payload, dict):
        update_player_items(world_save, players_dir, player_uid, items_payload)

    write_raw_sav(level_path, gvas, save_type)
    return {"ok": True, "playerUid": player_uid}


def apply_guild_update(level_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    group_id = normalize_uid_text(payload.get("groupId"))
    if not group_id:
        raise ValueError("公会 ID 无效")
    gvas, save_type = load_raw_sav(level_path)
    world_save = get_world_save(gvas)
    _, guild_raw_data = find_guild_entry(world_save, group_id)
    update_guild_fields(guild_raw_data, payload)
    update_guild_players(world_save, guild_raw_data, payload.get("players") or [])

    for camp_payload in payload.get("baseCamps") or []:
        if not isinstance(camp_payload, dict):
            continue
        camp_id = normalize_uid_text(camp_payload.get("id"))
        if not camp_id:
            continue
        _, base_camp_raw_data = find_base_camp_entry(world_save, camp_id)
        update_base_camp_fields(base_camp_raw_data, camp_payload)

    write_raw_sav(level_path, gvas, save_type)
    return {"ok": True, "groupId": group_id}


def load_payload_file(payload_file: Path) -> dict[str, Any]:
    with open(payload_file, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("更新载荷格式无效")
    return payload


def build_bool_property(value: Any) -> dict[str, Any]:
    return {
        "id": None,
        "type": "BoolProperty",
        "value": as_bool(value),
    }


def build_int_property(value: Any) -> dict[str, Any]:
    return {
        "id": None,
        "type": "IntProperty",
        "value": int(as_int(value, 0)),
    }


def build_float_property(value: Any) -> dict[str, Any]:
    return {
        "id": None,
        "type": "FloatProperty",
        "value": float(as_float(value, 0.0)),
    }


def build_enum_property(enum_type: str, value: Any) -> dict[str, Any]:
    return {
        "id": None,
        "type": "EnumProperty",
        "value": {
            "type": enum_type,
            "value": f"{enum_type}::{str(value or '').strip() or 'None'}",
        },
    }


def build_enum_array_property(enum_type: str, values: list[str]) -> dict[str, Any]:
    return {
        "id": None,
        "type": "ArrayProperty",
        "array_type": "EnumProperty",
        "value": {
            "values": [f"{enum_type}::{item}" for item in values],
        },
    }


def build_datetime_property(value: int) -> dict[str, Any]:
    return {
        "struct_type": "DateTime",
        "struct_id": "00000000-0000-0000-0000-000000000000",
        "id": None,
        "type": "StructProperty",
        "value": value,
    }


def build_struct_property(struct_type: str, value: dict[str, Any]) -> dict[str, Any]:
    return {
        "struct_type": struct_type,
        "struct_id": "00000000-0000-0000-0000-000000000000",
        "id": None,
        "type": "StructProperty",
        "value": value,
    }


def current_filetime() -> int:
    return int(time.time() * 10000000) + WORLD_OPTION_DEFAULT_FILETIME


def clone_world_option_default(key: str) -> Any:
    value = WORLD_OPTION_DEFAULTS[key]
    if isinstance(value, list):
        return list(value)
    return value


def strip_enum_prefix(value: Any) -> str:
    text = as_text(value).strip()
    if "::" in text:
        return text.split("::", 1)[1]
    return text


def normalize_world_option_array(value: Any, fallback: list[str]) -> list[str]:
    raw_items = value if isinstance(value, list) else str(value or "").split(",")
    result: list[str] = []
    for item in raw_items:
        normalized = strip_enum_prefix(item).strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result if result else list(fallback)


def normalize_world_option_value(key: str, value: Any) -> Any:
    fallback = clone_world_option_default(key)

    if key == "AutoSaveSpan":
        return 1800.0

    if key in WORLD_OPTION_ARRAY_KEYS:
        return normalize_world_option_array(value, fallback if isinstance(fallback, list) else [])

    if key in WORLD_OPTION_ENUM_TYPES and key not in WORLD_OPTION_ARRAY_KEYS:
        text = strip_enum_prefix(value)
        return text or str(fallback)

    if isinstance(fallback, bool):
        return as_bool(value) if value is not None else fallback

    if isinstance(fallback, int) and key not in WORLD_OPTION_FLOAT_KEYS:
        return as_int(value, fallback)

    if isinstance(fallback, float) or key in WORLD_OPTION_FLOAT_KEYS:
        return as_float(value, float(fallback))

    text = as_text(value).strip()
    return text or str(fallback)


def create_default_world_option_values() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in WORLD_OPTION_VALID_KEYS:
        result[key] = clone_world_option_default(key)
    result["AutoSaveSpan"] = 1800.0
    return result


def get_simple_world_option_settings(properties: dict[str, Any]) -> dict[str, Any]:
    option_world_data = properties.get("OptionWorldData")
    if not isinstance(option_world_data, dict):
        return {}
    settings = option_world_data.get("Settings")
    return settings if isinstance(settings, dict) else {}


def read_world_option(level_path: Path, world_option_path: Path) -> dict[str, Any]:
    values = create_default_world_option_values()
    if world_option_path.exists():
        properties = simplify_raw_node(load_raw_sav(world_option_path)[0].properties)
        settings = get_simple_world_option_settings(properties)
        for key in WORLD_OPTION_VALID_KEYS:
            if key in settings:
                values[key] = normalize_world_option_value(key, settings[key])
        if "CrossplayPlatforms" not in settings and WORLD_OPTION_HIDDEN_CONNECT_PLATFORM_KEY in settings:
            values["CrossplayPlatforms"] = normalize_world_option_array(
                [settings[WORLD_OPTION_HIDDEN_CONNECT_PLATFORM_KEY]],
                values["CrossplayPlatforms"],
            )
    return {
        "exists": world_option_path.exists(),
        "values": values,
    }


def simplify_raw_node(node: Any) -> Any:
    if isinstance(node, dict):
        if "type" in node and "value" in node:
            node_type = node.get("type")
            value = node.get("value")
            if node_type == "StructProperty":
                return simplify_raw_node(value)
            if node_type == "ArrayProperty":
                if isinstance(value, dict) and "values" in value:
                    return [simplify_raw_node(item) for item in value.get("values", [])]
                return simplify_raw_node(value)
            if node_type in ("EnumProperty", "ByteProperty"):
                if isinstance(value, dict) and "value" in value:
                    return simplify_raw_node(value.get("value"))
                return simplify_raw_node(value)
            return simplify_raw_node(value)
        return {
            key: simplify_raw_node(value)
            for key, value in node.items()
            if key not in {"id", "struct_id"}
        }
    if isinstance(node, list):
        return [simplify_raw_node(item) for item in node]
    return node


def get_struct_properties(property_node: Any) -> dict[str, Any]:
    if not isinstance(property_node, dict) or property_node.get("type") != "StructProperty":
        raise ValueError("目标字段不是结构体")
    value = property_node.get("value")
    if not isinstance(value, dict):
        raise ValueError("结构体内容无效")
    return value


def get_or_create_world_option_settings_properties(gvas: GvasFile) -> dict[str, Any]:
    option_world_data = gvas.properties.get("OptionWorldData")
    if not isinstance(option_world_data, dict) or option_world_data.get("type") != "StructProperty":
        option_world_data = build_struct_property(WORLD_OPTION_DATA_STRUCT, {})
        gvas.properties["OptionWorldData"] = option_world_data

    option_world_value = get_struct_properties(option_world_data)
    settings = option_world_value.get("Settings")
    if not isinstance(settings, dict) or settings.get("type") != "StructProperty":
        settings = build_struct_property(WORLD_OPTION_SETTINGS_STRUCT, {})
        option_world_value["Settings"] = settings

    return get_struct_properties(settings)


def build_world_option_property(key: str, value: Any, existing_node: Any = None) -> dict[str, Any]:
    if key in WORLD_OPTION_ARRAY_KEYS:
        normalized_array = normalize_world_option_array(value, [])
        if key == "CrossplayPlatforms":
            return build_enum_array_property(WORLD_OPTION_ENUM_TYPES[key], normalized_array)
        if isinstance(existing_node, dict) and existing_node.get("type") == "ArrayProperty":
            return build_enum_array_property(WORLD_OPTION_ENUM_TYPES[key], normalized_array)
        return build_string_property(",".join(normalized_array))

    if key in WORLD_OPTION_ENUM_TYPES:
        return build_enum_property(WORLD_OPTION_ENUM_TYPES[key], normalize_world_option_value(key, value))

    fallback = WORLD_OPTION_DEFAULTS[key]
    if isinstance(fallback, bool):
        return build_bool_property(value)
    if isinstance(fallback, int) and key not in WORLD_OPTION_FLOAT_KEYS:
        return build_int_property(value)
    if isinstance(fallback, float) or key in WORLD_OPTION_FLOAT_KEYS:
        return build_float_property(value)
    return build_string_property(value)


def load_or_create_world_option(level_path: Path, world_option_path: Path) -> tuple[GvasFile, int]:
    if world_option_path.exists():
        return load_raw_sav(world_option_path)

    base_gvas, save_type = load_raw_sav(level_path)
    gvas = GvasFile()
    gvas.header = copy.deepcopy(base_gvas.header)
    gvas.header.save_game_class_name = WORLD_OPTION_SAVE_GAME_CLASS
    gvas.properties = {
        "Version": build_int_property(100),
        "Timestamp": build_datetime_property(current_filetime()),
        "OptionWorldData": build_struct_property(
            WORLD_OPTION_DATA_STRUCT,
            {
                "Settings": build_struct_property(WORLD_OPTION_SETTINGS_STRUCT, {}),
            },
        ),
    }
    gvas.trailer = b"\x00\x00\x00\x00"
    return gvas, save_type


def write_world_option(level_path: Path, world_option_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    raw_values = payload.get("values")
    if not isinstance(raw_values, dict):
        raise ValueError("WorldOption.sav 配置数据无效")

    values = create_default_world_option_values()
    for key in WORLD_OPTION_VALID_KEYS:
        if key in raw_values:
            values[key] = normalize_world_option_value(key, raw_values[key])

    gvas, save_type = load_or_create_world_option(level_path, world_option_path)
    save_type = SaveType.PLM
    settings_properties = get_or_create_world_option_settings_properties(gvas)

    for key in WORLD_OPTION_VALID_KEYS:
        settings_properties[key] = build_world_option_property(key, values[key], settings_properties.get(key))

    selected_platforms = normalize_world_option_array(
        values.get("CrossplayPlatforms"),
        WORLD_OPTION_DEFAULTS["CrossplayPlatforms"],
    )
    settings_properties[WORLD_OPTION_HIDDEN_CONNECT_PLATFORM_KEY] = build_enum_property(
        WORLD_OPTION_ENUM_TYPES[WORLD_OPTION_HIDDEN_CONNECT_PLATFORM_KEY],
        selected_platforms[0] if selected_platforms else "Steam",
    )

    gvas.properties["Version"] = build_int_property(100)
    gvas.properties["Timestamp"] = build_datetime_property(current_filetime())
    world_option_path.parent.mkdir(parents=True, exist_ok=True)
    write_raw_sav(world_option_path, gvas, save_type)
    return {
        "exists": True,
        "values": values,
    }
