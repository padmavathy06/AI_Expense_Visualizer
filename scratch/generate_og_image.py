import os
from PIL import Image, ImageDraw, ImageFont

os.makedirs("static/img", exist_ok=True)
width, height = 1200, 630
image = Image.new("RGB", (width, height), color="#080c14")
draw = ImageDraw.Draw(image)

# Draw radial / gradient glow shapes
for r in range(350, 0, -5):
    alpha = int((350 - r) * 0.12)
    draw.ellipse((100 - r, 80 - r, 100 + r, 80 + r), fill=(99, 102, 241, alpha))

for r in range(300, 0, -5):
    alpha = int((300 - r) * 0.08)
    draw.ellipse((1100 - r, 500 - r, 1100 + r, 500 + r), fill=(6, 182, 212, alpha))

# Card border
draw.rounded_rectangle((30, 30, width - 30, height - 30), radius=24, outline="#1e293b", width=2)

# Load fonts or default
try:
    font_title = ImageFont.truetype("arialbd.ttf", 64)
    font_tagline = ImageFont.truetype("arial.ttf", 32)
    font_pill = ImageFont.truetype("arialbd.ttf", 22)
    font_badge = ImageFont.truetype("seguiemj.ttf", 54)
except Exception:
    font_title = ImageFont.load_default()
    font_tagline = ImageFont.load_default()
    font_pill = ImageFont.load_default()
    font_badge = ImageFont.load_default()

# Icon badge box
draw.rounded_rectangle((100, 100, 190, 190), radius=20, fill="#4f46e5", outline="#6366f1", width=2)
draw.text((125, 115), "$", fill="#ffffff", font=font_title)

# Brand Name
draw.text((220, 115), "AI Expense Visualizer", fill="#f8fafc", font=font_title)

# Tagline
draw.text((100, 230), "Track, analyze and understand your expenses with AI.", fill="#94a3b8", font=font_tagline)

# Separator line
draw.line((100, 310, 1100, 310), fill="#1e293b", width=2)

# Feature Badges
badges = [
    ("AI Smart Parsing", 100, 360, "#1e293b", "#818cf8"),
    ("12-Month Analytics", 360, 360, "#1e293b", "#38bdf8"),
    ("Multi-Account Banking", 650, 360, "#1e293b", "#34d399"),
    ("Financial Goals & Pots", 100, 440, "#1e293b", "#fbbf24"),
    ("100% Private & Persistent", 440, 440, "#1e293b", "#f472b6")
]

for label, bx, by, bg, text_color in badges:
    bbox = font_pill.getbbox(label)
    bw = bbox[2] - bbox[0] + 36
    bh = 46
    draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=12, fill=bg, outline="#334155", width=1)
    draw.text((bx + 18, by + 10), label, fill=text_color, font=font_pill)

# Footer domain
draw.text((100, 540), "https://expense-visualizer-app.onrender.com", fill="#64748b", font=font_tagline)

output_path = "static/img/og-preview.png"
image.save(output_path, "PNG")
print(f"Generated OG image at: {output_path}")
