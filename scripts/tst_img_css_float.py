from app.services.renderer import render

wt = """[[File:photo.png|thumb|right|A ship]]

== The Queens ==

Some text.

[[Category:Images]]
"""
atts = {"photo.png": "/api/v1/attachments/abc/photo.png"}
html = render(wt, fmt="wikitext", namespace="Main", base_url="", attachments=atts)
import re
fig = re.search(r'<figure[^>]*>', html)
cat = re.search(r'<div class="wiki-categories"', html)
print("Figure:   ", fig.group(0) if fig else "NOT FOUND")
print("Categories:", cat.group(0) if cat else "NOT FOUND")
print()
print(html)
