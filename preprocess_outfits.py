# -*- coding: utf-8 -*-
"""
三视图 -> 桌宠换装精灵（通用版）

用法：
    # 先出预览（棋盘格，人工检查抠图质量）
    python preprocess_outfits.py --id winter_cape --name 雪绒斗篷 ^
        --src "..\\1791106417396.jpeg" --preview --out build\\outfit_preview

    # 确认后正式生成
    python preprocess_outfits.py --id winter_cape --name 雪绒斗篷 ^
        --src "..\\1791106417396.jpeg" --out sprites\\outfits --force

产物（每套外观自包含，manifest.json 记录名字与可用视图）：
    sprites/outfits/<id>/正面.png / 侧面.png / 背面.png      # 340 高母版
    sprites/outfits/<id>/正面_187.png ... 背面_306.png       # 三档尺寸
    sprites/outfits/<id>/icon.png                            # 64 高菜单缩略图
    sprites/outfits/manifest.json

抠图方式：
    默认「白底泛洪」（沿用 preprocess.py 思路，无需任何模型，快、离线可用）；
    加 --rembg 改用 rembg 抠图（需 pip install "rembg[cpu]" 才会带上 onnxruntime 后端，
    首次运行会自动下载 u2net 模型约 170MB）。--rembg auto（默认）会在装了 rembg 时自动启用，
    失败会自动退回白底泛洪，不会中断。
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw

VIEWS = ["正面", "侧面", "背面"]
SIZES = {0.55: 187, 0.7: 238, 0.9: 306}
TARGET_H = 340
ICON_H = 64

HERE = os.path.dirname(os.path.abspath(__file__))

_rembg_session = None


def rembg_available():
    """rembg 是否可用（模块 + onnxruntime 后端都在）。"""
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        return False, "没有 onnxruntime 后端（pip install \"rembg[cpu]\"）"
    try:
        import rembg  # noqa: F401
    except Exception as e:
        return False, f"import rembg 失败：{e!r}"
    return True, "ok"


def rembg_cutout(im):
    """用 rembg 抠图，返回 RGBA（失败抛异常，由调用方决定是否回退）。"""
    global _rembg_session
    from rembg import remove, new_session
    if _rembg_session is None:
        _rembg_session = new_session("u2net")
    out = remove(im.convert("RGB"), session=_rembg_session)
    if out.mode != "RGBA":
        out = out.convert("RGBA")
    return out


# ---------------- 基础工具 ----------------
def _opaque_mask(im, alpha_thr=40):
    """返回 (h, w) 的不透明掩码，避免依赖 numpy。"""
    a = im.getchannel("A")
    return [bytearray(1 if v > alpha_thr else 0 for v in a.crop((0, y, im.width, y + 1)).tobytes())
            for y in range(im.height)]


def _ink_cols(im, d_thr=60, work_w=900):
    """按列统计「离白距离」超阈值的像素数（缩到 work_w 宽再统计，快且够用）。"""
    scale = min(1.0, work_w / im.width)
    small = im.convert("RGB")
    if scale < 1.0:
        small = small.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                             Image.BILINEAR)
    w, h = small.size
    px = small.load()
    cols = [0] * w
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if (765 - r - g - b) > d_thr:
                cols[x] += 1
    return cols, scale


def split_columns(im, name=""):
    """三视图并排 → 用列密度 k-means（k=3）定三格中线，返回 (zones, cuts, width)。

    比「找空隙极小点」稳：即使相邻两格的大波浪头发伸进同一列区间，按列质量
    分配给最近的簇中心后，切片仍落在两簇之间，不会把邻格发丝切成独立的一条。
    """
    w0 = im.width
    cols, scale = _ink_cols(im)
    w = len(cols)
    total = sum(cols) or 1
    cs = [0.0, 0.0, 0.0]
    # 初值：按像素质量的三分位
    acc, q, tgt = 0, 0, total / 3.0
    for x, v in enumerate(cols):
        acc += v
        if acc >= tgt * (q + 1) and q < 2:
            cs[q] = x
            q += 1
    cs[2] = w - 1
    if cs[0] >= cs[1] or cs[1] >= cs[2]:
        cs = [w / 6.0, w / 2.0, 5 * w / 6.0]
    for _ in range(20):
        s = [0.0, 0.0, 0.0]
        n = [0.0, 0.0, 0.0]
        for x, v in enumerate(cols):
            if v <= 0:
                continue
            k = min(range(3), key=lambda i: abs(x - cs[i]))
            s[k] += x * v
            n[k] += v
        new = [s[i] / n[i] if n[i] else cs[i] for i in range(3)]
        if max(abs(new[i] - cs[i]) for i in range(3)) < 0.5:
            cs = new
            break
        cs = new
    lo, mid, hi = sorted(cs)
    if mid - lo < w * 0.12 or hi - mid < w * 0.12:
        lo, mid, hi = w / 6.0, w / 2.0, 5 * w / 6.0
    c1, c2 = int((lo + mid) / 2), int((mid + hi) / 2)
    c1 = max(1, min(c1, w0 - 2))
    c2 = max(c1 + 1, min(c2, w0 - 1))
    inv = 1.0 / scale
    c1, c2 = int(c1 * inv), int(c2 * inv)
    zones = [(0, c1), (c1, c2), (c2, w0)]
    return zones, (c1, c2), w0


def largest_component_mask(im, alpha_thr=40, min_share=0.15):
    """保留最大的一块不透明连通域（用于切格切歪、带上邻格发丝时兜底）。"""
    mask = _opaque_mask(im, alpha_thr)
    h, w = im.height, im.width
    total = sum(sum(r) for r in mask)
    seen = [bytearray(w) for _ in range(h)]
    best = (0, 0, 0, 0, 0)
    for sy in range(h):
        row = mask[sy]
        for sx in range(w):
            if not row[sx] or seen[sy][sx]:
                continue
            stack = [(sx, sy)]
            seen[sy][sx] = 1
            area = 0
            x0 = x1 = sx
            y0 = y1 = sy
            while stack:
                x, y = stack.pop()
                area += 1
                if x < x0: x0 = x
                if x > x1: x1 = x
                if y < y0: y0 = y
                if y > y1: y1 = y
                for dy in (-1, 0, 1):
                    ny = y + dy
                    if ny < 0 or ny >= h:
                        continue
                    nrow = mask[ny]
                    srow = seen[ny]
                    for dx in (-1, 0, 1):
                        nx = x + dx
                        if nx < 0 or nx >= w or srow[nx] or not nrow[nx]:
                            continue
                        srow[nx] = 1
                        stack.append((nx, ny))
            if area > best[0]:
                best = (area, x0, y0, x1, y1)
    area, x0, y0, x1, y1 = best
    if area < total * min_share:
        return None
    out = im.copy().convert("RGBA")
    op = out.load()
    for y in range(h):
        row = mask[y]
        for x in range(w):
            if not row[x]:
                op[x, y] = (0, 0, 0, 0)
    return out.crop((x0, y0, x1 + 1, y1 + 1))


def seal_background(im, thr=40, max_seed=400):
    """从四角 / 四边中点反复泛洪，把外围白底整片抠成透明（人物内部的白不受影响）。

    比单次四角泛洪稳：即使某条边被发丝/薄纱截断，也会继续用新的边缘白点做种子。
    """
    im = im.convert("RGBA")
    w, h = im.size
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
             (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]
    used = set()
    queue = [s for s in seeds if _is_whiteish(im, s, thr)]
    n = 0
    while queue and n < max_seed:
        s = queue.pop(0)
        if s in used:
            continue
        used.add(s)
        if not _is_whiteish(im, s, thr):
            continue
        ImageDraw.floodfill(im, s, (0, 0, 0, 0), thresh=thr)
        n += 1
        # 本轮填充后，扫描四条边，找仍然偏白的点继续填（白底被截断时补种）
        for x in range(0, w, 2):
            for y in (0, h - 1):
                if (x, y) not in used and _is_whiteish(im, (x, y), thr):
                    queue.append((x, y))
        for y in range(0, h, 2):
            for x in (0, w - 1):
                if (x, y) not in used and _is_whiteish(im, (x, y), thr):
                    queue.append((x, y))
        if len(queue) > 4000:          # 安全阀，避免病态图片上无限扩散
            break
    return im


def _is_whiteish(im, xy, thr):
    px = im.load()
    x, y = xy
    if not (0 <= x < im.width and 0 <= y < im.height):
        return False
    r, g, b, a = px[x, y]
    return a > 0 and r > 255 - thr and g > 255 - thr and b > 255 - thr


def decontaminate(im):
    """边缘像素对白底去混合：pixel = fg*a + 255*(1-a) → fg = (pixel - 255*(1-a))/a"""
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if 0 < a < 255:
                if a < 40:
                    px[x, y] = (0, 0, 0, 0)
                    continue
                t = a / 255.0
                nr = (r - 255 * (1 - t)) / t
                ng = (g - 255 * (1 - t)) / t
                nb = (b - 255 * (1 - t)) / t
                px[x, y] = (int(max(0, min(255, nr))), int(max(0, min(255, ng))),
                            int(max(0, min(255, nb))), a)
    return im


def premult_resize(im, height):
    """预乘 alpha 缩放：黑底 / 白底各缩一次再解出真实颜色 + alpha。"""
    im = im.convert("RGBA")
    w0, h0 = im.size
    nw = max(1, round(w0 * height / h0))
    black = Image.alpha_composite(Image.new("RGBA", im.size, (0, 0, 0, 255)), im)
    white = Image.alpha_composite(Image.new("RGBA", im.size, (255, 255, 255, 255)), im)
    black = black.resize((nw, height), Image.LANCZOS)
    white = white.resize((nw, height), Image.LANCZOS)
    bp, wp = black.load(), white.load()
    out = Image.new("RGBA", (nw, height))
    op = out.load()
    for y in range(height):
        for x in range(nw):
            br, bg, bb, _ = bp[x, y]
            wr, wg, wb, _ = wp[x, y]
            a = 255 - max(wr - br, wg - bg, wb - bb)
            if a < 6:
                op[x, y] = (0, 0, 0, 0)
                continue
            t = a / 255.0
            op[x, y] = (int(max(0, min(255, br / t))), int(max(0, min(255, bg / t))),
                        int(max(0, min(255, bb / t))), a)
    return out


def extract_figure(im, zone, flip=False, method="flood"):
    """裁出一格 → 抠图（白底泛洪 或 rembg）→ 裁透明边 → 去白边；返回 340 高母版。

    rembg 失败会自动退回白底泛洪，不会打断整批处理。
    """
    sub = im.crop((zone[0], 0, zone[1], im.size[1])).convert("RGBA")
    if method == "rembg":
        try:
            sub = rembg_cutout(sub)
            print("    （rembg 抠图完成）")
        except Exception as e:
            print(f"    ！rembg 抠图失败，退回白底泛洪：{e!r}")
            sub = seal_background(sub)
    else:
        sub = seal_background(sub)
    bbox = sub.getbbox()
    if bbox is None:
        raise RuntimeError(f"区间 {zone} 抠图后为空")
    cropped = sub.crop(bbox)
    if cropped.width < cropped.height * 0.35:
        # 太瘦：多半是切格把邻格的发丝切了进来，改用最大连通域
        fixed = largest_component_mask(sub)
        if fixed is not None:
            print(f"    （区间 {zone} 偏瘦 {cropped.size}，改用最大连通域 {fixed.size}）")
            cropped = fixed
    if cropped.height < im.size[1] * 0.15:
        raise RuntimeError(f"区间 {zone} 抠出的图形太矮（{cropped.size}），切格可能错了")
    cropped = decontaminate(cropped)
    if flip:
        cropped = cropped.transpose(Image.FLIP_LEFT_RIGHT)
    bbox = cropped.getbbox()
    if bbox is None:
        raise RuntimeError(f"区间 {zone} 去白边后为空")
    cropped = cropped.crop(bbox)
    w2, h2 = cropped.size
    scale = TARGET_H / h2
    return cropped.resize((max(1, round(w2 * scale)), TARGET_H), Image.LANCZOS)


# ---------------- 预览 ----------------
def checkerboard(size, cell=12):
    w, h = size
    im = Image.new("RGBA", size, (255, 255, 255, 255))
    px = im.load()
    for y in range(h):
        for x in range(w):
            if ((x // cell) + (y // cell)) % 2:
                px[x, y] = (205, 210, 220, 255)
    return im


def make_preview(views, out_path, label=""):
    """三种视图 + 三种底色的合成预览，用于人工检查抠图边缘。"""
    scale = 170 / TARGET_H
    cols = []
    for name in VIEWS:
        im = views[name]
        cols.append(im.resize((max(1, round(im.width * scale)), 170), Image.LANCZOS))
    gap, pad = 14, 10
    body_w = sum(c.width for c in cols) + gap * (len(cols) - 1)
    body_h = max(c.height for c in cols)
    W = body_w + pad * 2
    H = body_h * 3 + gap * 2 + pad * 2 + 22
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    bands = [checkerboard((W, body_h + 6)), Image.new("RGBA", (W, body_h + 6), (255, 255, 255, 255)),
             Image.new("RGBA", (W, body_h + 6), (26, 28, 38, 255))]
    y = pad
    d = ImageDraw.Draw(canvas)
    for band in bands:
        canvas.alpha_composite(band, (0, y))
        x = pad
        for c in cols:
            canvas.alpha_composite(c, (x, y + 3))
            x += c.width + gap
        y += band.height + gap
    d.text((pad, y), label or "", fill=(40, 40, 60, 255))
    canvas.convert("RGB").save(out_path)
    return out_path


# ---------------- 主流程 ----------------
def build_one(src, outfit_id, name, out_root, side_index=1, flip_side=False,
              preview=False, force=False, rembg="auto"):
    im = Image.open(src)
    im.load()
    zones, cuts, w0 = split_columns(im)
    print(f"[{outfit_id}] 源图 {os.path.basename(src)} {im.size} 切线 {cuts}")

    method = "flood"
    if rembg in ("auto", "on", True):
        ok, why = rembg_available()
        if ok:
            method = "rembg"
            print("    抠图方式：rembg（首次会下载 u2net 模型）")
        elif rembg != "auto":
            print(f"    ！--rembg 指定了但不可用：{why}；退回白底泛洪")
        else:
            print(f"    抠图方式：白底泛洪（rembg 不可用：{why}）")
    else:
        print("    抠图方式：白底泛洪")

    views = {}
    for idx, vname in enumerate(VIEWS):
        is_side = (idx == side_index - 1)
        figure = extract_figure(im, zones[idx], flip=(flip_side and is_side), method=method)
        views[vname] = figure
        print(f"    {vname}: {figure.size}  宽高比 {figure.width / figure.height:.3f}")
        if not (0.40 <= figure.width / figure.height <= 0.95):
            print(f"    ! {vname} 宽高比异常，检查切格/抠图")

    if preview:
        out_dir = os.path.join(out_root, outfit_id)
        os.makedirs(out_dir, exist_ok=True)
        p = make_preview(views, os.path.join(out_dir, "preview.png"),
                         label=f"{outfit_id} / {name}  (棋盘格 / 白底 / 深底)")
        print(f"    预览 -> {p}")
        return {"id": outfit_id, "name": name, "views": list(VIEWS), "preview": os.path.relpath(p, HERE)}

    out_dir = os.path.join(out_root, outfit_id)
    os.makedirs(out_dir, exist_ok=True)
    for vname in VIEWS:
        full = os.path.join(out_dir, f"{vname}.png")
        if os.path.exists(full) and not force:
            print(f"    跳过已存在 {full}（--force 可覆盖）")
            continue
        views[vname].save(full)
        for mult, h in SIZES.items():
            views[vname].resize((max(1, round(views[vname].width * h / views[vname].height)), h),
                                Image.LANCZOS).save(os.path.join(out_dir, f"{vname}_{h}.png"))
    icon = views["正面"]
    icon.resize((max(1, round(icon.width * ICON_H / icon.height)), ICON_H),
                Image.LANCZOS).save(os.path.join(out_dir, "icon.png"))
    print(f"    已生成 -> {out_dir}")

    man_path = os.path.join(out_root, "manifest.json")
    man = {"outfits": []}
    if os.path.exists(man_path):
        try:
            with open(man_path, "r", encoding="utf-8") as f:
                man = json.load(f)
        except Exception:
            man = {"outfits": []}
    man.setdefault("outfits", [])
    man["outfits"] = [o for o in man["outfits"] if o.get("id") != outfit_id]
    man["outfits"].append({"id": outfit_id, "name": name, "views": list(VIEWS)})
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    print(f"    manifest -> {man_path}")
    return {"id": outfit_id, "name": name, "views": list(VIEWS)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="三视图 -> 桌宠换装精灵")
    ap.add_argument("--id", required=True, help="外观 id，如 winter_cape")
    ap.add_argument("--src", required=True, help="三视图原图（白底 png/jpg）")
    ap.add_argument("--name", default="", help="菜单显示名，如 雪绒斗篷")
    ap.add_argument("--out", default=os.path.join(HERE, "sprites", "outfits"),
                    help="输出根目录（默认 dafeiyu-pet/sprites/outfits）")
    ap.add_argument("--side-index", type=int, default=1, choices=[1, 2, 3],
                    help="第几格当侧面（1/2/3，默认 2）")
    ap.add_argument("--flip-side", action="store_true", help="侧面做左右镜像")
    ap.add_argument("--preview", action="store_true", help="只出棋盘格预览图，不写精灵")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的精灵")
    ap.add_argument("--rembg", choices=["auto", "on", "off"], default="auto",
                    help="抠图方式：auto=装了 rembg 就用（默认），on=强制 rembg，off=只用白底泛洪")
    a = ap.parse_args(argv)

    out_root = a.out if os.path.isabs(a.out) else os.path.join(HERE, a.out)
    src = a.src if os.path.isabs(a.src) else os.path.join(os.getcwd(), a.src)
    if not os.path.exists(src):
        src = os.path.join(HERE, a.src)
    if not os.path.exists(src):
        print(f"找不到源图：{a.src}")
        return 2
    try:
        build_one(src, a.id, a.name or a.id, out_root, side_index=a.side_index,
                  flip_side=a.flip_side, preview=a.preview, force=a.force, rembg=a.rembg)
    except Exception as e:
        print(f"处理失败：{e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
