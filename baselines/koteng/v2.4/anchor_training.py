"""Koteng visual point calibration on a LOCAL screenshot; no ticket-map clicks.

All coordinates refer to the top-level Edge viewport in screenshot pixels.
The calibration is deliberately tied to the saved map/layout fingerprint;
recalibration is required on meaningful browser layout changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
import shutil
from pathlib import Path

FORMAT_VERSION = 1
MAX_POINTS_PER_SECTION = 3


def screenshot_to_css(x, y, screenshot_size, viewport):
    """Map pixel position in resized/browser screenshot to Edge CSS viewport."""
    sw, sh = screenshot_size
    vw, vh = viewport
    if min(sw, sh, vw, vh) <= 0:
        raise ValueError("Ugyldig skjermbilde/viewport")
    return (x * vw / sw, y * vh / sh)


def css_to_screenshot(x, y, screenshot_size, viewport):
    """Map CSS hover position onto screenshot's native pixel geometry."""
    sw, sh = screenshot_size
    vw, vh = viewport
    if min(sw, sh, vw, vh) <= 0:
        raise ValueError("Ugyldig skjermbilde/viewport")
    return (x * sw / vw, y * sh / vh)


def stand_focus_css(region):
    """Focus on the narrow seated section strip directly above Koteng's pitch."""
    x1, y1, x2, y2 = (float(v) for v in region)
    if not (x2 > x1 and y2 > y1):
        raise ValueError("Ugyldig kartområde")
    return (x1 + .46 * (x2-x1), max(0, y1 - 15))


def validate_picks(picks: dict, expected_sections: dict, viewport: tuple[int, int]) -> dict:
    width, height = map(int, viewport)
    if width < 400 or height < 300:
        raise ValueError("Ugyldig Edge-vindusstørrelse")
    expected = set(expected_sections)
    if set(picks) != expected:
        raise ValueError("Alle seks felt må markeres, uten ukjente feltnavn")
    cleaned = {}
    for name in sorted(expected):
        points = picks[name]
        if not isinstance(points, list) or not (1 <= len(points) <= MAX_POINTS_PER_SECTION):
            raise ValueError(f"{name} må ha 1–{MAX_POINTS_PER_SECTION} markeringer")
        coords = []
        for p in points:
            if not isinstance(p, (list, tuple)) or len(p) != 2:
                raise ValueError("Punkt må ha x og y")
            x, y = p
            if not all(isinstance(v, (float, int)) and math.isfinite(v) and not isinstance(v, bool) for v in (x, y)):
                raise ValueError("Punktkoordinater må være gyldige tall")
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError(f"{name}: markeringen må være inne i Edge-bildet")
            coords.append([round(x), round(y)])
        if len({tuple(v) for v in coords}) != len(coords):
            raise ValueError(f"{name}: dobbelt punkt")
        cleaned[name] = coords
    return cleaned


def build_anchor_document(picks, profile, key, viewport, map_region, page_zoom):
    cleaned = validate_picks(picks, profile["reference_sections"], viewport)
    width, height = map(int, viewport)
    if not map_region or len(map_region) != 4:
        raise ValueError("Stadionkartets referanseområde mangler")
    return {
        "format_version": FORMAT_VERSION,
        "venue_id": "koteng_arena",
        "profile_version_at_training": profile["profile_version"],
        "training_event_key": key,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": "manual_clicks_on_local_screenshot_no_ticket_interaction",
        "reference_viewport": [width, height],
        "reference_map_region": [round(float(v), 1) for v in map_region],
        "reference_page_zoom": round(float(page_zoom), 3),
        "points": {k: [[round(x / width, 7), round(y / height, 7)] for x, y in v]
                   for k, v in cleaned.items()},
        "source_points_pixels": cleaned,
        "manual_points_only": True,
        "seat_availability_verified": False,
        "public_approved": False,
    }


def save_anchor_document(path: Path, document: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    os.replace(tmp, path)


def mapped_points(document, expected_sections: dict, viewport, map_region, page_zoom):
    """Return map of field -> points only for sufficiently unchanged viewport/map.

    Intentionally avoids blindly extrapolating seating-strip positions from an
    unrelated pitch/canvas bounding box (which may exclude the seat strip).
    """
    if document.get("format_version") != FORMAT_VERSION or document.get("venue_id") != "koteng_arena":
        raise ValueError("Ukjent ankerformat eller feil stadion")
    if set(document.get("points", {})) != set(expected_sections):
        raise ValueError("Ankerfilens felter stemmer ikke med Koteng-profilen")
    old = document.get("reference_viewport")
    region = document.get("reference_map_region")
    if not (isinstance(old, list) and len(old) == 2 and isinstance(region, list) and len(region) == 4):
        raise ValueError("Ufullstendig ankerfil")
    width, height = map(int, viewport)
    if any(abs(int(old[i]) - (width, height)[i]) > 8 for i in (0, 1)):
        raise ValueError("Edge-vinduet har endret størrelse. Kjør LÆR_OPP_KOTENG.bat på nytt")
    if any(abs(float(a)-float(b)) > 12 for a,b in zip(region, map_region)):
        raise ValueError("Kartet er flyttet eller skalert. Kjør LÆR_OPP_KOTENG.bat på nytt")
    if abs(float(document.get("reference_page_zoom", -1)) - float(page_zoom)) > 0.015:
        raise ValueError("Sidezoom er endret. Kjør LÆR_OPP_KOTENG.bat på nytt")
    mapped = {}
    for section in expected_sections:
        values = document["points"][section]
        if not isinstance(values, list) or not (1 <= len(values) <= MAX_POINTS_PER_SECTION):
            raise ValueError(f"Ugyldig antall punkter for {section}")
        points = []
        for raw in values:
            if not isinstance(raw, list) or len(raw) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) and not isinstance(v, bool) for v in raw):
                raise ValueError("Ugyldige ankerkoordinater")
            x,y=round(raw[0]*width), round(raw[1]*height)
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError("Anker utenfor Edge-vindu")
            points.append((x,y))
        mapped[section] = points
    return mapped


def teach_from_screenshot(screenshot, expected_sections, viewport, focus_map_region=None):
    """Six-click visual calibration with optional extra marks per area.

    This opens a *separate local image viewer*; the live ticket page never
    receives clicks and cannot reserve seats through this process.
    """
    try:
        import tkinter as tk
        from PIL import Image, ImageTk, ImageDraw
    except ImportError as exc:
        raise RuntimeError("Installer Pillow med INSTALLER_KOTENG.bat. Tkinter følger normalt med Python for Windows.") from exc
    source=Image.open(screenshot).convert("RGB")
    width,height=source.size
    css_width,css_height=map(int,viewport)
    names=[name for name in ("FELT-1","FELT-2","FELT-3","FELT-4","FELT-5","VIP") if name in expected_sections]
    names += [n for n in sorted(expected_sections) if n not in names]
    picks={k:[] for k in names}
    history=[]
    result={"saved":False}
    root=tk.Tk()
    root.title("Koteng Arena – merk blå/gul sittefeltstripe (ingen billettklikk)")
    root.configure(bg="#121c19")
    screen_w,screen_h=root.winfo_screenwidth(),root.winfo_screenheight()
    root.geometry(f"{min(screen_w-30,1600)}x{min(screen_h-70,980)}+0+0")

    header=tk.Label(root, text="KLIKK PÅ BLÅ/GUL FELTSTRIPE OVER BANEN – IKKE PÅ KAMPBANNERET / SPILLERBILDET.",
                    anchor="w",bg="#121c19",fg="#ffffff",font=("Segoe UI",12,"bold"),pady=10)
    header.pack(fill="x",padx=12)
    main=tk.Frame(root,bg="#121c19");main.pack(fill="both",expand=True,padx=8,pady=5)
    side=tk.Frame(main,bg="#202d29",width=230);side.pack(side="right",fill="y",padx=5)
    side.pack_propagate(False)
    area=tk.Frame(main,bg="#101715");area.pack(side="left",fill="both",expand=True)
    canvas=tk.Canvas(area,bg="#101715",cursor="crosshair",highlightthickness=0)
    canvas.grid(row=0,column=0,sticky="nsew")
    vx=tk.Scrollbar(area,orient="horizontal",command=canvas.xview)
    vy=tk.Scrollbar(area,orient="vertical",command=canvas.yview)
    vx.grid(row=1,column=0,sticky="ew");vy.grid(row=0,column=1,sticky="ns")
    canvas.configure(xscrollcommand=vx.set,yscrollcommand=vy.set)
    area.grid_columnconfigure(0,weight=1);area.grid_rowconfigure(0,weight=1)
    title=tk.Label(side,text="SITTEOMRÅDER",font=("Segoe UI",11,"bold"),bg="#202d29",fg="#ffffff",pady=12)
    title.pack()
    listbox=tk.Listbox(side,font=("Segoe UI",11),bg="#10231c",fg="#e7f8ed",selectbackground="#177d55",
                       exportselection=False,height=9)
    listbox.pack(fill="x",padx=10)
    hint=tk.Label(side, text="1 punkt per felt er nok.\nDu kan velge et felt på nytt\nog legge til opptil 3 punkter.\n\nKlikk på fargestripen til\nhvert felt, IKKE banen.\n\nIngen klikk sendes til RBK.",
                  bg="#202d29",fg="#c7d8ce",justify="left",font=("Segoe UI",10))
    hint.pack(anchor="w",padx=12,pady=16)
    # Start at a legible scale and use the scrollable canvas to show the stands.
    # An auto-fitted whole-page picture made the thin strips easy to miss.
    zoom=1.20
    imgref=[None]
    status=tk.StringVar(value="Marker FELT-1")
    tk.Label(side,textvariable=status,fg="#a8ffc9",bg="#202d29",justify="left",wraplength=205,font=("Segoe UI",10,"bold")).pack(padx=10,fill="x",pady=4)
    def redraw():
        base=source.resize((round(width*zoom),round(height*zoom)),Image.Resampling.LANCZOS)
        draw=ImageDraw.Draw(base)
        for idx,name in enumerate(names):
            for j,(x,y) in enumerate(picks[name]):
                sx,sy=css_to_screenshot(x,y,(width,height),(css_width,css_height))
                px,py=round(sx*zoom),round(sy*zoom)
                draw.ellipse((px-8,py-8,px+8,py+8),fill="#ffb02e",outline="#191919",width=2)
                draw.text((px+10,py-10),f"{name} {j+1}",fill="#ffff00",stroke_width=2,stroke_fill="#111111")
        imgref[0]=ImageTk.PhotoImage(base)
        canvas.delete("all")
        canvas.create_image(0,0,image=imgref[0],anchor="nw")
        canvas.configure(scrollregion=(0,0,base.width,base.height))
    def refresh():
        selection=listbox.curselection()
        selected=selection[0] if selection else 0
        listbox.delete(0,"end")
        for name in names:
            listbox.insert("end",f"{'✓' if picks[name] else '○'}  {name}  ({len(picks[name])})")
        listbox.selection_set(selected)
        listbox.see(selected)
        pending=[n for n in names if not picks[n]]
        status.set(("Mangler: "+", ".join(pending)) if pending else "Alle feltene merket. Trykk LAGRE eller legg til ekstra punkter.")
        save_btn.configure(state="normal" if not pending else "disabled")
        redraw()
    def mark(event):
        picked=listbox.curselection()
        if not picked:return
        name=names[picked[0]]
        if len(picks[name])>=MAX_POINTS_PER_SECTION:
            status.set(f"Maks {MAX_POINTS_PER_SECTION} punkter for {name}")
            return
        px=canvas.canvasx(event.x)/zoom;py=canvas.canvasy(event.y)/zoom
        if not (0<=px<width and 0<=py<height):return
        cx,cy=screenshot_to_css(px,py,(width,height),(css_width,css_height))
        picks[name].append([round(cx),round(cy)]);history.append(name)
        next_name=next((n for n in names if not picks[n]),None)
        refresh()
        if next_name:
            listbox.selection_clear(0,"end");listbox.selection_set(names.index(next_name));listbox.see(names.index(next_name))
    def undo():
        if history:
            name=history.pop()
            picks[name].pop()
            refresh()
            listbox.selection_clear(0,"end");listbox.selection_set(names.index(name))
    def save():
        try:validate_picks(picks,expected_sections,(css_width,css_height))
        except ValueError as e:
            status.set(str(e));return
        result["saved"]=True
        result["picks"]=picks
        root.destroy()
    def cancel():root.destroy()
    def adjust(delta):
        nonlocal zoom
        zoom=min(1.6,max(.45,round(zoom+delta,2)))
        redraw()
    def focus_on_stands():
        if focus_map_region is None:
            return
        cx,cy=stand_focus_css(focus_map_region)
        px,py=css_to_screenshot(cx,cy,(width,height),(css_width,css_height))
        canvas.update_idletasks()
        img_w,img_h=round(width*zoom),round(height*zoom)
        left=max(0,min(img_w-canvas.winfo_width(),round(px*zoom-canvas.winfo_width()*.5)))
        top=max(0,min(img_h-canvas.winfo_height(),round(py*zoom-canvas.winfo_height()*.35)))
        canvas.xview_moveto(left/max(1,img_w))
        canvas.yview_moveto(top/max(1,img_h))

    buttons=tk.Frame(side,bg="#202d29");buttons.pack(fill="x",padx=10,pady=4)
    tk.Button(buttons,text="Zoom +",command=lambda:adjust(.15)).pack(side="left",expand=True,fill="x")
    tk.Button(buttons,text="Zoom −",command=lambda:adjust(-.15)).pack(side="left",expand=True,fill="x")
    tk.Button(side,text="VIS TRIBUNEFELTENE",command=focus_on_stands,bg="#f9cb46",fg="#111111",
              font=("Segoe UI",11,"bold")).pack(fill="x",padx=10,pady=7)
    tk.Button(side,text="Angre siste punkt",command=undo).pack(fill="x",padx=10,pady=7)
    save_btn=tk.Button(side,text="LAGRE PUNKTER",command=save,bg="#2eaf70",fg="#000000",font=("Segoe UI",11,"bold"))
    save_btn.pack(fill="x",padx=10,pady=8)
    tk.Button(side,text="Avbryt",command=cancel).pack(fill="x",padx=10,pady=6)
    root.protocol("WM_DELETE_WINDOW",cancel)
    canvas.bind("<Button-1>",mark)
    listbox.selection_set(0)
    refresh()
    root.after(150,focus_on_stands)
    root.mainloop()
    if not result["saved"]:
        raise RuntimeError("Opplæring avbrutt. Ingen punkter ble lagret, og ingen skanning er godkjent.")
    return result["picks"]


def draw_anchor_overlay(screenshot: Path, anchors: dict, output: Path, viewport) -> None:
    """Local visual audit: anchor marks, not screenshot interactions."""
    from PIL import Image, ImageDraw, ImageFont
    src=Image.open(screenshot).convert("RGB")
    draw=ImageDraw.Draw(src)
    font=ImageFont.load_default()
    for field,points in anchors.items():
        for n,(x,y) in enumerate(points,1):
            px,py=css_to_screenshot(x,y,src.size,viewport)
            px,py=round(px),round(py)
            draw.ellipse((px-8,py-8,px+8,py+8),fill="#ffca45",outline="#080808",width=2)
            draw.text((px+11,py-11),f"{field} #{n}",font=font,fill="yellow",stroke_width=2,stroke_fill="#151515")
    src.save(output)
