
"""RecipeLang JSON and CSV exports, plus labeled PNG charts using Pillow."""
import csv
import json
import struct
import zlib
from pathlib import Path


def export_json(result, path):
    Path(path).write_text(json.dumps(result, indent=2), encoding='utf-8')


def export_csv(result, path):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'start', 'end', 'uses'])
        writer.writeheader()
        for slot in result['schedule']['slots']:
            writer.writerow({**slot, 'uses': ', '.join(slot['uses'])})


def _png(path, width, height, rectangles):
    # Minimal standards-compliant RGB PNG writer.
    pixels = bytearray([255, 255, 255] * width * height)
    for x1, y1, x2, y2, color in rectangles:
        for y in range(max(0,y1), min(height,y2)):
            for x in range(max(0,x1), min(width,x2)):
                i = 3*(y*width+x)
                pixels[i:i+3] = bytes(color)
    raw = b''.join(b'\0' + pixels[y*width*3:(y+1)*width*3] for y in range(height))
    def chunk(tag, data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))


def _drawing(width, height):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise ImportError('PNG export requires Pillow: python3 -m pip install Pillow') from exc
    im = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(im)
    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    bold_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    try:
        font = ImageFont.truetype(font_path, 15)
        bold = ImageFont.truetype(bold_path, 16)
    except OSError:
        font = ImageFont.load_default()
        bold = font
    return im, draw, font, bold


def export_gantt_png(result, path):
    slots = result['schedule']['slots']
    maximum = max(1, result['schedule']['optimized_minutes'])
    width, height = 1250, max(260, len(slots)*58+155)
    im, draw, font, bold = _drawing(width, height)
    x0, xend = 215, width-65
    draw.text((25, 15), 'RecipeLang - resource-aware cooking timeline', fill='#172033', font=bold)
    draw.text((x0+330, 40), 'TIME (MINUTES)', fill='#334155', font=bold)
    draw.text((25, 61), 'COOKING STEP', fill='#475569', font=font)
    draw.line((x0, 67, xend, 67), fill='#64748b', width=2)
    step = max(1, (maximum+9)//10)
    for t in sorted(set(range(0, maximum+1, step)) | {maximum}):
        x = x0 + round((xend-x0)*t/maximum)
        draw.line((x, 67, x, height-42), fill='#dce3ec', width=1)
        draw.text((x-14, 49), f'{t}m', fill='#42526b', font=font)
    colors = ['#4f46e5','#0891b2','#16a34a','#d97706','#be185d','#7c3aed']
    for i, slot in enumerate(slots):
        y = 82 + i*58
        if i % 2 == 0:
            draw.rectangle((0, y-5, width, y+42), fill='#f8fafc')
        draw.text((20, y+3), slot['name'], fill='#172033', font=bold)
        draw.text((20, y+22), ', '.join(slot['uses']) or 'no resource', fill='#64748b', font=font)
        x1 = x0 + round((xend-x0)*slot['start']/maximum)
        x2 = x0 + round((xend-x0)*slot['end']/maximum)
        draw.rounded_rectangle((x1, y, max(x1+3,x2), y+33), radius=5, fill=colors[i%len(colors)])
        label = f'{slot["start"]}-{slot["end"]} min'
        if x2-x1 > 100:
            draw.text((x1+8, y+7), label, fill='white', font=font)
        else:
            draw.text((x2+6, y+7), label, fill='#172033', font=font)
    draw.text((20, height-31), f'Final schedule: {maximum} min | Sequential baseline: {result["schedule"]["sequential_minutes"]} min', fill='#334155', font=font)
    im.save(path, format='PNG')


def export_dag_png(result, path):
    import math
    from collections import defaultdict
    steps = result['ast']['steps']
    edges = result['ir']['edges']
    levels = {}
    def level(n):
        if n not in levels:
            levels[n] = max((level(d)+1 for d in steps[n]['needs']), default=0)
        return levels[n]
    for n in steps: level(n)
    groups = defaultdict(list)
    for n, depth in levels.items(): groups[depth].append(n)
    width = max(720, 255*(max(groups)+1)+90)
    height = max(430, 125*max(len(g) for g in groups.values())+205)
    im, draw, font, bold = _drawing(width, height)
    draw.text((22, 15), 'RecipeLang - dependency graph', fill='#172033', font=bold)
    draw.text((22, 39), 'Arrows point from prerequisite to dependent step', fill='#475569', font=font)
    pos = {}
    for depth, names in groups.items():
        for i, n in enumerate(names):
            pos[n] = (110+depth*255, 105+(i+1)*(height-190)/(len(names)+1))
    for depth in sorted(groups):
        label = 'START - no prerequisites' if depth == 0 else f'STAGE {depth+1} - after prerequisites'
        draw.text((35+depth*255, 70), label, fill='#475569', font=font)
    critical = set(result['critical_path_nodes'])
    for a,b in edges:
        x1,y1=pos[a]; x2,y2=pos[b]
        start=(x1+82,y1); end=(x2-82,y2)
        color='#dc2626' if a in critical and b in critical else '#64748b'
        draw.line((*start,*end),fill=color,width=3)
        angle=math.atan2(end[1]-start[1],end[0]-start[0])
        wing=11
        points=[end,(end[0]-wing*math.cos(angle-.48),end[1]-wing*math.sin(angle-.48)),(end[0]-wing*math.cos(angle+.48),end[1]-wing*math.sin(angle+.48))]
        draw.polygon(points,fill=color)
    for n,(x,y) in pos.items():
        active=n in critical
        draw.rounded_rectangle((x-82,y-38,x+82,y+38),radius=6,fill='#fee2e2' if active else '#e0e7ff',outline='#dc2626' if active else '#4338ca',width=3 if active else 2)
        draw.text((x-75,y-30),n,fill='#172033',font=bold)
        draw.text((x-75,y-7),f'{steps[n]["duration"]} min',fill='#334155',font=font)
        draw.text((x-75,y+14),', '.join(steps[n]['uses']) or 'no resource',fill='#64748b',font=font)
    draw.rectangle((22, height-39, 38, height-23), fill='#fee2e2', outline='#dc2626', width=2)
    draw.text((46, height-41), 'critical path', fill='#334155', font=font)
    draw.rectangle((180, height-39, 196, height-23), fill='#e0e7ff', outline='#4338ca', width=2)
    draw.text((204, height-41), 'regular step', fill='#334155', font=font)
    im.save(path,format='PNG')

def export_all(result, directory):
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    export_json(result,directory/'compilation.json')
    export_json(result['tokens'],directory/'tokens.json')
    export_json(result['ast'],directory/'ast.json')
    export_json(result['ir'],directory/'dependency_graph.json')
    export_json(result['schedule'],directory/'schedule.json')
    export_csv(result,directory/'timeline.csv')
    export_gantt_png(result,directory/'gantt.png')
    export_dag_png(result,directory/'dependency_graph.png')
    return directory
