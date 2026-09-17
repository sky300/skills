#!/usr/bin/env python3
"""Publish a Xianyu listing — payload assembly.

The publish call's difficulty is its payload, not its transport: ~20 nested fields
whose names and value shapes the web client decided. This file is the assembled
result of reading the upstream implementation, kept as code because it must be
byte-exact; the parts you have to supply (where the cookies are, how you POST) stay
in the moment you fire it — see below.

Full chain, in order:

  1. Upload images   (no signing; plain multipart POST)
        POST https://stream-upload.goofish.com/api/upload.api
             ?floderId=0&appkey=xy_chat&_input_charset=utf-8
        files={"file": (name, open(path,"rb"), "image/png")}
        cookies + origin/referer https://www.goofish.com
     -> {"url": ..., "pix": "1024x1024", "size": ...}

  2. ai_category(...)   mtop.taobao.idle.kgraph.property.recommend  v2.0
  3. default_location() mtop.taobao.idle.local.poi.get               v1.0
  4. build_publish_payload(...)  ->  POST mtop.idle.pc.idleitem.publish v1.0

Steps 2-4 are mtop calls: sign them with templates/mtop_request.py.

Run this file to print a sample payload and eyeball the shape; adapt the EDIT
block to your real values before firing anything. Read references/write-operations.md
first — approval, pacing and read-back rules live there.
"""
from __future__ import annotations

import json

# --------------------------------------------------------------------- EDIT block
# The three inputs below come from steps 1-3 of the chain (upload, category,
# location). Replace these samples with what those calls actually returned.
IMAGE_INFOS = [                      # from the upload step
    {"url": "https://img.alicdn.com/example.jpg", "width": 1024, "height": 1024},
]
CATEGORY_RESULT = {                  # data.categoryPredictResult
    "catId": "50025461", "catName": "路由器", "channelCatId": "50025461",
    "tbCatId": "50025461",
}
LOCATION = {                         # data.selectedPoi (or commonAddresses[0])
    "prov": "上海", "city": "上海市", "area": "徐汇区",
    "divisionId": "310104", "poi": "某某路 1 号",
    "longitude": "121.4365", "latitude": "31.1875", "poiId": "0",
}
TITLE = "小米 4A 千兆版无线路由器 二手 8-9 新"
DESC = "自用闲置，功能正常，无拆修。\n\n支持千兆端口 + 无线 1200M。"
PRICE_YUAN = 48.0                    # <= 0 means "no price set" (defaultPrice)
ORIGINAL_PRICE_YUAN = None
# The delivery literals are the API's own Chinese values — do not translate them.
DELIVERY = "无需邮寄"                 # 包邮 | 按距离计费 | 一口价 | 无需邮寄
POST_PRICE_YUAN = 0
CAN_SELF_PICKUP = True               # the UI's "支持自提"
# ----------------------------------------------------------------------------------


def image_do_list(image_infos: list[dict]) -> list[dict]:
    """The upload results in the shape both the category and publish calls want.

    Note the two different names for the same thing: the upload response says
    width/height, these payloads say widthSize/heightSize.
    """
    return [
        {
            "extraInfo": {"isH": "false", "isT": "false", "raw": "false"},
            "isQrCode": False,
            "url": img["url"],
            "heightSize": img["height"],
            "widthSize": img["width"],
            "major": True,          # one image must be the cover
            "type": 0,
            "status": "done",
        }
        for img in image_infos
    ]


def build_publish_payload(
    *,
    title: str,
    desc: str,
    image_infos: list[dict],
    price_yuan: float,
    category: dict,
    location: dict,
    original_price_yuan: float | None = None,
    delivery: str = "无需邮寄",
    post_price_yuan: float = 0,
    can_self_pickup: bool = True,
) -> dict:
    """Assemble the mtop.idle.pc.idleitem.publish payload."""
    post_fee: dict[str, object] = {
        "canFreeShipping": False, "supportFreight": False, "onlyTakeSelf": False,
    }
    if delivery == "包邮":
        post_fee["canFreeShipping"] = True
        post_fee["supportFreight"] = True
    elif delivery == "按距离计费":
        post_fee["supportFreight"] = True
        post_fee["templateId"] = "-100"
    elif delivery == "一口价":
        post_fee["supportFreight"] = True
        post_fee["postPriceInCent"] = str(int(post_price_yuan * 100))
        post_fee["templateId"] = "0"
    elif delivery == "无需邮寄":
        post_fee["templateId"] = "0"
    else:
        raise ValueError(f"unknown delivery mode: {delivery!r}")

    default_price = price_yuan <= 0
    price_dto: dict[str, str] = {}
    if not default_price:
        price_dto["priceInCent"] = str(int(price_yuan * 100))     # cents, as a string
    if original_price_yuan and original_price_yuan > 0:
        price_dto["origPriceInCent"] = str(int(original_price_yuan * 100))

    item_addr = {}
    if location.get("divisionId"):
        item_addr = {
            "area": location.get("area", ""),
            "city": location.get("city", ""),
            "divisionId": location.get("divisionId", ""),
            "gps": f"{location.get('longitude', '')},{location.get('latitude', '')}",
            "poiId": location.get("poiId", ""),
            "poiName": location.get("poi", ""),
            "prov": location.get("prov", ""),
        }

    return {
        "freebies": False,
        "itemTypeStr": "b",
        "quantity": "1",
        "simpleItem": "true",
        "imageInfoDOList": image_do_list(image_infos),
        "itemTextDTO": {"desc": desc, "title": title, "titleDescSeparate": True},
        "itemLabelExtList": [],
        "itemPriceDTO": price_dto,
        "userRightsProtocols": [{"enable": False, "serviceCode": "SKILL_PLAY_NO_MIND"}],
        "itemPostFeeDTO": post_fee,
        "itemAddrDTO": item_addr,
        "defaultPrice": default_price,
        "itemCatDTO": {
            "catId": str(category["catId"]),
            "catName": category["catName"],
            "channelCatId": str(category["channelCatId"]),
            "tbCatId": str(category["tbCatId"]),
        },
        "onlyTakeSelf": can_self_pickup,
        # Opaque tracking value carried over from the upstream implementation; its
        # provenance is unexplained. Re-derive it if the call is rejected.
        "uniqueCode": "1775897582791680",
        "sourceId": "pcMainPublish",
        "bizcode": "pcMainPublish",
        "publishScene": "pcMainPublish",
    }


def category_payload(title: str, image_infos: list[dict]) -> dict:
    """Payload for mtop.taobao.idle.kgraph.property.recommend (version 2.0)."""
    return {
        "title": title,
        "lockCpv": False,
        "multiSKU": False,
        "publishScene": "mainPublish",
        "scene": "newPublishChoice",
        "description": title,
        "imageInfos": image_do_list(image_infos),
        "uniqueCode": "1775905618164677",
    }


if __name__ == "__main__":
    payload = build_publish_payload(
        title=TITLE,
        desc=DESC,
        image_infos=IMAGE_INFOS,
        price_yuan=PRICE_YUAN,
        category=CATEGORY_RESULT,
        location=LOCATION,
        original_price_yuan=ORIGINAL_PRICE_YUAN,
        delivery=DELIVERY,
        post_price_yuan=POST_PRICE_YUAN,
        can_self_pickup=CAN_SELF_PICKUP,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    # Then: sign this with templates/mtop_request.py
    #   api=mtop.idle.pc.idleitem.publish  version=1.0  spm=a21ybx.publish.0.0
    # and read data.itemId out of the response. Re-read the listing afterwards —
    # a SUCCESS ret means accepted, not live.
